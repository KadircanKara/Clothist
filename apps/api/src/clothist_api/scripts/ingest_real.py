"""Real-product ingest: drive every enabled Shopify adapter, upsert into the
products table, bump taxonomy_version.

NOTE: On a fresh prod DB, run

    psql "$DATABASE_URL" -c "DELETE FROM products WHERE retailer = 'seed';"

before the first real ingest. Otherwise the catalog will mix demo seed and
real retailer products.

Usage:
    uv run python -m clothist_api.scripts.ingest_real \\
        [--source allbirds,ald,rothys,princess_polly_us,kith] \\
        [--limit-per-source 500] \\
        [--dry-run]

Per spec plans/scraping/senior_dev_v2.md §4a.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from dataclasses import asdict
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from clothist_api.db.session import SessionLocal
from clothist_api.scrapers import IngestCounters, ScraperContext, ShopifyAdapter
from clothist_api.scrapers.sources import SOURCES
from clothist_api.services.ingest_common import build_upsert_stmt, to_row

logger = logging.getLogger(__name__)

# Postgres advisory-lock key. Stops concurrent ingest_real + seed runs from
# racing on taxonomy_version.
INGEST_LOCK_KEY = 0xC107C107


async def _acquire_lock(session: AsyncSession) -> bool:
    row = await session.execute(
        text("SELECT pg_try_advisory_lock(:k)").bindparams(k=INGEST_LOCK_KEY)
    )
    return bool(row.scalar_one())


async def _release_lock(session: AsyncSession) -> None:
    await session.execute(
        text("SELECT pg_advisory_unlock(:k)").bindparams(k=INGEST_LOCK_KEY)
    )


async def _bump_taxonomy_version(session: AsyncSession) -> None:
    await session.execute(text("UPDATE meta SET taxonomy_version = taxonomy_version + 1"))


async def _flush_batch(
    session: AsyncSession, rows: list[dict[str, Any]], *, dry_run: bool
) -> int:
    if not rows:
        return 0
    if dry_run:
        for row in rows:
            logger.info(
                "dry_run_would_upsert retailer=%s id=%s title=%r",
                row["retailer"], row["retailer_product_id"], row["title"][:60],
            )
        return len(rows)
    stmt = build_upsert_stmt(rows)
    await session.execute(stmt)
    await session.commit()
    return len(rows)


async def _ingest_one_source(
    adapter: ShopifyAdapter,
    ctx: ScraperContext,
    session: AsyncSession,
    *,
    limit: int,
    dry_run: bool,
) -> IngestCounters:
    counters = IngestCounters()

    if not await adapter.check_robots_allowed(ctx.client):
        logger.error(
            "robots_disallowed source=%s — skipping source",
            adapter.retailer_slug,
        )
        return counters

    batch: list[dict[str, Any]] = []
    async for raw in adapter.iter_products(ctx, limit=limit, counters=counters):
        product = adapter.to_product(raw, counters=counters)
        if product is None:
            continue
        try:
            row = to_row(product)
        except RuntimeError as e:
            logger.warning(
                "to_row_failed source=%s id=%s err=%s",
                adapter.retailer_slug, product["retailer_product_id"], e,
            )
            continue
        batch.append(row)
        if len(batch) >= 50:
            n = await _flush_batch(session, batch, dry_run=dry_run)
            counters.upserted += n
            logger.info(
                "batch_committed source=%s n=%d running_total=%d",
                adapter.retailer_slug, n, counters.upserted,
            )
            batch = []

    if batch:
        n = await _flush_batch(session, batch, dry_run=dry_run)
        counters.upserted += n

    logger.info(
        "source_summary slug=%s counters=%s",
        adapter.retailer_slug, json.dumps(asdict(counters)),
    )
    return counters


async def ingest(
    *, source_slugs: list[str], limit: int, dry_run: bool
) -> dict[str, IngestCounters]:
    unknown = [s for s in source_slugs if s not in SOURCES]
    if unknown:
        raise SystemExit(
            f"Unknown source slug(s): {unknown}. "
            f"Valid: {sorted(SOURCES)}"
        )

    summary: dict[str, IngestCounters] = {}

    async with SessionLocal() as session:
        if not await _acquire_lock(session):
            logger.error("ingest_lock_held — another ingest run is in progress")
            raise SystemExit(2)

        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                sem = asyncio.Semaphore(5)
                ctx = ScraperContext(client=client, semaphore=sem)
                for slug in source_slugs:
                    adapter_cls = SOURCES[slug]
                    adapter = adapter_cls()
                    logger.info(
                        "source_starting slug=%s base_url=%s limit=%d",
                        slug, adapter.base_url, limit,
                    )
                    counters = await _ingest_one_source(
                        adapter, ctx, session,
                        limit=limit, dry_run=dry_run,
                    )
                    summary[slug] = counters

            # Bump taxonomy_version only when ≥1 source actually upserted ≥1
            # row in a real (non-dry) run. Pure-failure runs and dry runs skip.
            any_success = any(c.upserted > 0 for c in summary.values())
            if not dry_run and any_success:
                await _bump_taxonomy_version(session)
                await session.commit()
                logger.info("taxonomy_version_bumped")
            else:
                logger.info(
                    "taxonomy_version_not_bumped dry_run=%s any_success=%s",
                    dry_run, any_success,
                )
        finally:
            await _release_lock(session)
            await session.commit()

    return summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ingest real product data from Shopify storefronts.",
        epilog=(
            "NOTE: On a fresh prod DB, run "
            "'DELETE FROM products WHERE retailer = \\'seed\\';' before the "
            "first real ingest. Otherwise the catalog will mix demo and real "
            "products."
        ),
    )
    parser.add_argument(
        "--source",
        default=",".join(sorted(SOURCES)),
        help=f"Comma-separated retailer slugs. Default: all enabled "
             f"({sorted(SOURCES)}).",
    )
    parser.add_argument(
        "--limit-per-source",
        type=int,
        default=500,
        help="Hard cap on products fetched per source. Default 500.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and validate but do not upsert. Does not bump "
             "taxonomy_version. Logs every parsed row as "
             "event=\"dry_run_would_upsert\".",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    slugs = [s.strip() for s in args.source.split(",") if s.strip()]
    summary = asyncio.run(
        ingest(source_slugs=slugs, limit=args.limit_per_source, dry_run=args.dry_run)
    )

    print("\n=== Per-source summary ===")
    for slug, c in summary.items():
        print(f"  [{slug}] {json.dumps(asdict(c))}")
    total_upserted = sum(c.upserted for c in summary.values())
    print(f"\nTotal upserted: {total_upserted}")
    print("Dry run — no DB writes." if args.dry_run else "")
    return 0


if __name__ == "__main__":
    sys.exit(main())
