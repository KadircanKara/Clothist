"""Post-ingest CV classifier — walk the DB, run CLIP zero-shot, patch rows.

Per spec plans/cv_classify/senior_dev_v2.md §4c.

Usage:
    uv run python -m clothist_api.scripts.classify_products
        [--limit N]
        [--retailer slug]
        [--force]                # re-classify even if cv_classified_at is set
        [--dry-run]              # log verdicts, no DB writes
        [--batch-size 16]
        [--model openai/clip-vit-base-patch32]
        [--ignore-skip-until]    # bypass §3g back-off
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from clothist_api.cv.reconcile import reconcile
from clothist_api.cv.types import CVVerdict
from clothist_api.db.session import SessionLocal
from clothist_api.models import Product
from clothist_api.scrapers.normalize import normalize_category
from clothist_api.services.text_categorize import categorize_by_text, EXCLUDED_CATEGORY

logger = logging.getLogger(__name__)

# 0xC1A55157 ≈ "CLASSIFY" in leet — distinct from the ingest lock 0xC107C107.
CV_LOCK_KEY = 0xC1A55157
INGEST_LOCK_KEY = 0xC107C107


async def _try_lock(session: AsyncSession, key: int) -> bool:
    row = await session.execute(text("SELECT pg_try_advisory_lock(:k)").bindparams(k=key))
    return bool(row.scalar_one())


async def _release_lock(session: AsyncSession, key: int) -> None:
    await session.execute(text("SELECT pg_advisory_unlock(:k)").bindparams(k=key))


def _build_discovery_sql(
    *, force: bool, retailer: str | None, ignore_skip_until: bool, limit: int | None,
) -> tuple[str, dict[str, Any]]:
    parts = ["image_url IS NOT NULL"]
    params: dict[str, Any] = {}
    if not force:
        parts.append("attributes ->> 'cv_classified_at' IS NULL")
    if not ignore_skip_until:
        parts.append(
            "(attributes ->> 'cv_skip_until' IS NULL "
            "OR (attributes ->> 'cv_skip_until')::timestamptz < now())"
        )
    if retailer:
        parts.append("retailer = :p_retailer")
        params["p_retailer"] = retailer
    where = " AND ".join(parts)
    sql = (
        "SELECT id, image_url, category, gender, colors, attributes, "
        "title, brand, description "
        f"FROM products WHERE {where} ORDER BY scraped_at DESC"
    )
    if limit:
        sql += f" LIMIT {int(limit)}"
    return sql, params


async def _download_image(client: httpx.AsyncClient, url: str) -> bytes | None:
    try:
        r = await client.get(url, timeout=15, follow_redirects=True)
        r.raise_for_status()
        if len(r.content) < 1000:
            return None
        return r.content
    except httpx.HTTPError as e:
        logger.warning("cv_image_fetch_failed url=%s err=%s", url[:80], e)
        return None


async def _bump_fetch_failure(session: AsyncSession, product_id: str) -> None:
    """Per §3g: +1 to cv_fetch_failures; at >=3 set cv_skip_until = now() + 30d."""
    await session.execute(
        text(
            """
            UPDATE products
            SET attributes = attributes || jsonb_build_object(
                'cv_fetch_failures', COALESCE((attributes ->> 'cv_fetch_failures')::int, 0) + 1,
                'cv_skip_until', CASE
                    WHEN COALESCE((attributes ->> 'cv_fetch_failures')::int, 0) + 1 >= 3
                        THEN (now() + interval '30 days')::text
                    ELSE attributes ->> 'cv_skip_until'
                END
            )
            WHERE id = :pid
            """
        ).bindparams(pid=product_id)
    )


def _verdict_to_jsonb(
    verdict: CVVerdict,
    *,
    scraper_previous: dict,
    colors_previous: list[str] | None,
    category_source: dict,
) -> dict:
    return {
        # CV's image-derived category guess. Kept for audit only — the
        # writeback no longer uses it; vendor product_type is the single
        # source of truth for category as of 2026-05-25.
        "category_cv_audit": {
            "value": verdict.category,
            "confidence": round(verdict.category_confidence, 4),
            "runner_up": (
                [verdict.category_runner_up[0], round(verdict.category_runner_up[1], 4)]
                if verdict.category_runner_up else None
            ),
        },
        "gender": {
            "value": verdict.gender,
            "confidence": round(verdict.gender_confidence, 4),
            "runner_up": (
                [verdict.gender_runner_up[0], round(verdict.gender_runner_up[1], 4)]
                if verdict.gender_runner_up else None
            ),
        },
        "colors": [
            {"value": name, "confidence": round(conf, 4), "source": "pillow+clip"}
            for name, conf in verdict.colors
        ],
        "category_source": category_source,
        "scraper_previous": scraper_previous,
        "colors_previous": colors_previous,
    }


async def classify(
    *,
    limit: int | None,
    retailer: str | None,
    force: bool,
    dry_run: bool,
    batch_size: int,
    model_id: str,
    ignore_skip_until: bool,
) -> dict[str, int]:
    """Returns a counters dict for the summary line."""
    counters = {
        "fetched": 0, "image_fetch_failed": 0, "classified": 0,
        # Category events — exactly one fires per product.
        "category_vendor": 0,         # vendor product_type mapped
        "category_non_clothing": 0,   # title flagged non-clothing → excluded
        "category_uncategorized": 0,  # neither — fallback bucket
        # Gender (2-way scraper-vs-CV).
        "cv_gender_corroborated": 0, "cv_gender_override": 0,
        "cv_gender_below_threshold": 0, "cv_gender_filled_gap": 0,
        "cv_gender_gap_unfilled": 0, "cv_gender_flatlay_guard": 0,
        "cv_gender_both_unknown": 0,
        # Color (2-way scraper-vs-CV).
        "cv_color_replaced": 0, "cv_color_kept": 0,
    }

    async with SessionLocal() as session:
        # 1. Acquire BOTH locks — see §4c step 1.
        if not await _try_lock(session, INGEST_LOCK_KEY):
            logger.error("ingest_lock_held — refuse to run mid-ingest")
            raise SystemExit(2)
        if not await _try_lock(session, CV_LOCK_KEY):
            await _release_lock(session, INGEST_LOCK_KEY)
            logger.error("cv_lock_held — another classifier is in progress")
            raise SystemExit(2)
        try:
            # 2. Discover rows.
            sql, params = _build_discovery_sql(
                force=force, retailer=retailer,
                ignore_skip_until=ignore_skip_until, limit=limit,
            )
            rows = (await session.execute(text(sql), params)).mappings().all()
            counters["fetched"] = len(rows)
            logger.info("cv_discovery rows=%d", counters["fetched"])
            if not rows:
                return counters

            # 3. Lazy-init model — AFTER lock acquisition (§4c step 3).
            from PIL import Image as PILImage
            from clothist_api.cv.classifier import CLIPClassifier
            clf = CLIPClassifier(model_id=model_id)

            # 4. Iterate in batches.
            async with httpx.AsyncClient(follow_redirects=True) as client:
                for start in range(0, len(rows), batch_size):
                    chunk = rows[start:start + batch_size]

                    # 4a. Image download. LLM is no longer called for
                    #     category — vendor product_type carries that
                    #     (services/text_categorize is now query-only).
                    image_bytes = await asyncio.gather(
                        *[_download_image(client, r["image_url"]) for r in chunk],
                        return_exceptions=False,
                    )

                    # 4b. Group: only CV-classify rows whose image_bytes is not None.
                    images: list["PILImage.Image"] = []
                    urls: list[str] = []
                    byte_list: list[bytes] = []
                    keepers: list[dict] = []
                    for r, b in zip(chunk, image_bytes, strict=True):
                        if not b:
                            counters["image_fetch_failed"] += 1
                            await _bump_fetch_failure(session, r["id"])
                            continue
                        try:
                            img = PILImage.open(__import__("io").BytesIO(b)).convert("RGB")
                            images.append(img)
                            urls.append(r["image_url"])
                            byte_list.append(b)
                            keepers.append(r)
                        except Exception as e:
                            logger.warning("cv_image_decode_failed id=%s err=%s", r["id"], e)
                            counters["image_fetch_failed"] += 1
                            await _bump_fetch_failure(session, r["id"])

                    if not images:
                        await session.commit()
                        continue

                    verdicts = clf.classify_batch(images, urls, byte_list)

                    # 5. Reconcile + write per row.
                    for r, v in zip(keepers, verdicts, strict=True):
                        existing_attrs = r["attributes"] or {}

                        # Vendor product_type — the only category signal we
                        # use. `raw_category` is the literal string from
                        # /products.json ("Swimwear", "Sweatshirts", "Mini
                        # dresses"). normalize_category maps it to a canonical
                        # token or returns None for generic tags like
                        # "Apparel". When None, we check the title for non-
                        # clothing tokens (homewares / decor) → excluded;
                        # else uncategorized.
                        raw_cat = existing_attrs.get("raw_category")
                        vendor_category = normalize_category(raw_cat)
                        non_clothing_alias: str | None = None
                        if vendor_category is None:
                            tv = categorize_by_text(title=r["title"], brand=r["brand"])
                            if tv.category == EXCLUDED_CATEGORY:
                                non_clothing_alias = tv.matched_alias

                        decision = reconcile(
                            scraper_category=r["category"],
                            scraper_gender=r["gender"],
                            scraper_colors=r["colors"],
                            verdict=v,
                            vendor_category=vendor_category,
                            title=r["title"],
                            non_clothing_alias=non_clothing_alias,
                        )
                        counters[decision.category_event] += 1
                        counters[decision.gender_event] += 1
                        counters[decision.color_event] += 1
                        counters["classified"] += 1

                        cv_jsonb = _verdict_to_jsonb(
                            v,
                            scraper_previous=decision.scraper_previous,
                            colors_previous=(
                                r["colors"] if decision.color_event == "cv_color_replaced" else None
                            ),
                            category_source=decision.category_source,
                        )
                        merge_payload = {
                            "cv_verdict": cv_jsonb,
                            "cv_classified_at": datetime.now(timezone.utc).isoformat(),
                            "cv_model": model_id,
                            "cv_fetch_failures": 0,
                            "cv_skip_until": None,
                        }
                        if dry_run:
                            logger.info(
                                "dry_run_would_update id=%s "
                                "cat=%s→%s(%s) gen=%s→%s(%s) cols=%s",
                                r["id"], r["category"], decision.category,
                                decision.category_event,
                                r["gender"], decision.gender,
                                decision.gender_event,
                                decision.color_event,
                            )
                            continue

                        # Write top-level columns + merge JSONB.
                        await session.execute(
                            text(
                                """
                                UPDATE products
                                SET category = :cat,
                                    gender   = :gen,
                                    colors   = :cols,
                                    attributes = attributes || CAST(:cv_payload AS jsonb)
                                WHERE id = :pid
                                """
                            ).bindparams(
                                cat=decision.category,
                                gen=decision.gender,
                                cols=decision.colors,
                                cv_payload=json.dumps(merge_payload),
                                pid=r["id"],
                            )
                        )
                    await session.commit()
                    logger.info(
                        "cv_batch_committed start=%d size=%d classified=%d",
                        start, len(chunk), counters["classified"],
                    )
        finally:
            await _release_lock(session, CV_LOCK_KEY)
            await _release_lock(session, INGEST_LOCK_KEY)
            await session.commit()

    return counters


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Post-ingest CV classifier (CLIP zero-shot).",
        epilog=(
            "NOTE: Run `verify_cv_model.py` once after `uv sync --extra cv` "
            "to pre-fetch the model. Then run this script after every "
            "`ingest_real.py`. The locks make concurrent ingest+CV impossible."
        ),
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--retailer", default=None)
    parser.add_argument("--force", action="store_true",
                        help="Re-classify rows that already have cv_classified_at set.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Log verdicts; no DB writes.")
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--model", default="openai/clip-vit-base-patch32")
    parser.add_argument("--ignore-skip-until", action="store_true",
                        help="Bypass the §3g 30-day back-off on dead-image products.")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    started = time.perf_counter()
    counters = asyncio.run(classify(
        limit=args.limit,
        retailer=args.retailer,
        force=args.force,
        dry_run=args.dry_run,
        batch_size=args.batch_size,
        model_id=args.model,
        ignore_skip_until=args.ignore_skip_until,
    ))

    print("\n=== CV classifier summary ===")
    print(json.dumps(counters, indent=2))
    print(f"Wall-clock: {time.perf_counter() - started:.1f}s")
    print("Dry run — no DB writes." if args.dry_run else "")
    return 0


if __name__ == "__main__":
    sys.exit(main())
