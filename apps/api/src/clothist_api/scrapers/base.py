"""ShopifyAdapter — base class for every Shopify `/products.json` source.

Hits the public storefront endpoint, paginates, throttles, and maps each raw
Shopify product through `to_product()` into the canonical Clothist row shape
that `services.ingest_common.to_row()` consumes.

Per-store adapters subclass this and override the tag-namespace mappers
(`gender_for`, `category_for`, `feature_tags_for`) where vendor conventions
differ.
"""
from __future__ import annotations

import asyncio
import logging
import urllib.robotparser
from dataclasses import dataclass
from typing import Any, AsyncIterator

import httpx

from clothist_api.scrapers.normalize import (
    CATEGORY_IMPLIED_GENDER,
    Gender,
    normalize_category,
    normalize_color,
    normalize_gender,
    strip_html,
)

logger = logging.getLogger(__name__)


USER_AGENT = "Clothist-Ingest/0.1 (+research, contact: lior@cherry-host.es)"


@dataclass(slots=True)
class IngestCounters:
    """Per-source counters returned at end of run for the summary log."""

    fetched: int = 0
    upserted: int = 0
    skipped_no_variants: int = 0
    skipped_no_images: int = 0
    skipped_no_color_image: int = 0
    skipped_bad_currency: int = 0
    skipped_unmapped_category: int = 0
    gender_inferred_from_fallback: int = 0
    rate_limit_backoffs: int = 0


@dataclass(slots=True)
class ScraperContext:
    """Shared HTTP client + concurrency semaphore for a single ingest run."""

    client: httpx.AsyncClient
    semaphore: asyncio.Semaphore  # global in-flight ceiling


class ShopifyAdapter:
    """Base class — subclass per source, override the tag-namespace bits.

    Required class attributes:
      `base_url`            — e.g. "https://www.allbirds.com"
      `retailer_slug`       — primary key namespace (e.g. "allbirds")
      `currency`            — ISO code; locked store-wide per spec §3
      `image_hostname`      — for `next.config.mjs` validation (all current Tier-1 = "cdn.shopify.com")

    Optional class attributes:
      `assume_gender`       — fallback when tag scan yields nothing (§3b)
      `page_size`           — Shopify accepts up to 250 (default)
      `products_endpoint`   — defaults to "/products.json"
      `throttle_seconds`    — per-source sleep between page fetches (default 1.5)
    """

    base_url: str = ""
    retailer_slug: str = ""
    currency: str = "USD"
    image_hostname: str = "cdn.shopify.com"
    assume_gender: Gender | None = None
    page_size: int = 250
    products_endpoint: str = "/products.json"
    throttle_seconds: float = 1.5

    # -----------------------------------------------------------------
    # robots.txt
    # -----------------------------------------------------------------

    async def check_robots_allowed(self, client: httpx.AsyncClient) -> bool:
        """Return False if the source's robots.txt disallows `/products.json`
        for either the wildcard `*` user-agent OR the literal Clothist UA.
        More-specific match wins — if a `User-Agent: Clothist-Ingest/0.1`
        block exists, its rules override the `*` block (RFC 9309).
        """
        robots_url = self.base_url.rstrip("/") + "/robots.txt"
        try:
            r = await client.get(robots_url, timeout=10)
        except httpx.HTTPError as e:
            logger.warning("robots_fetch_failed source=%s err=%s", self.retailer_slug, e)
            return True
        if r.status_code != 200:
            return True
        parser = urllib.robotparser.RobotFileParser()
        parser.parse(r.text.splitlines())
        path = self.products_endpoint
        try:
            explicit = parser.can_fetch(USER_AGENT, path)
        except Exception:
            explicit = True
        try:
            wildcard = parser.can_fetch("*", path)
        except Exception:
            wildcard = True
        return explicit and wildcard

    # -----------------------------------------------------------------
    # Pagination
    # -----------------------------------------------------------------

    async def fetch_page(
        self, ctx: ScraperContext, page: int
    ) -> tuple[list[dict], int]:
        url = (
            f"{self.base_url.rstrip('/')}{self.products_endpoint}"
            f"?limit={self.page_size}&page={page}"
        )
        async with ctx.semaphore:
            r = await ctx.client.get(
                url,
                headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
                timeout=20,
            )
        if r.status_code != 200:
            return ([], r.status_code)
        try:
            data = r.json()
        except ValueError:
            return ([], 0)
        return (list(data.get("products") or []), 200)

    async def iter_products(
        self,
        ctx: ScraperContext,
        *,
        limit: int | None = None,
        counters: IngestCounters,
    ) -> AsyncIterator[dict]:
        yielded = 0
        page = 1
        consecutive_403 = 0
        empty_retry_used = False

        while True:
            products, status = await self.fetch_page(ctx, page)
            counters.fetched += len(products)

            if status == 429 or status >= 500:
                counters.rate_limit_backoffs += 1
                logger.warning(
                    "rate_limit_backoff source=%s page=%d status=%d",
                    self.retailer_slug, page, status,
                )
                await asyncio.sleep(min(self.throttle_seconds * 4, 8))
                products, status = await self.fetch_page(ctx, page)

            if status == 403 or status == 430:
                consecutive_403 += 1
                logger.error(
                    "source_403 source=%s page=%d streak=%d",
                    self.retailer_slug, page, consecutive_403,
                )
                if consecutive_403 >= 2:
                    logger.error(
                        "source_disabled_403_streak source=%s — aborting source",
                        self.retailer_slug,
                    )
                    return
                await asyncio.sleep(self.throttle_seconds * 2)
                continue
            consecutive_403 = 0

            if status != 200:
                logger.error(
                    "non_200_terminating source=%s page=%d status=%d",
                    self.retailer_slug, page, status,
                )
                return

            if not products:
                if page == 1:
                    logger.warning("source_empty_first_page source=%s", self.retailer_slug)
                    return
                if not empty_retry_used:
                    empty_retry_used = True
                    await asyncio.sleep(2.0)
                    continue
                logger.warning(
                    "walk_terminated_mid_paginate source=%s page=%d prior=%d",
                    self.retailer_slug, page, yielded,
                )
                return

            empty_retry_used = False

            for p in products:
                yield p
                yielded += 1
                if limit is not None and yielded >= limit:
                    return

            page += 1
            await asyncio.sleep(self.throttle_seconds)

    # -----------------------------------------------------------------
    # Mapping helpers — overridable per source
    # -----------------------------------------------------------------

    def gender_for(self, raw: dict, *, counters: IngestCounters) -> Gender:
        """Default impl: scan tags for known gender phrases; fall back to
        `assume_gender` (if declared) then "unisex". Override per-source for
        vendor-specific tag namespaces.
        """
        tags = raw.get("tags") or []
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",")]
        for t in tags:
            g = normalize_gender(t)
            if g:
                return g
        if self.assume_gender is not None:
            counters.gender_inferred_from_fallback += 1
            return self.assume_gender
        return "unisex"

    def category_for(self, raw: dict) -> tuple[str | None, str | None]:
        product_type = raw.get("product_type") or ""
        canonical = normalize_category(product_type)
        return (canonical, product_type or None)

    def color_axis_index(self, options: list[dict]) -> int | None:
        for i, opt in enumerate(options or []):
            if (opt.get("name") or "").strip().lower() == "color":
                return i + 1
        return None

    def features_for(self, raw: dict) -> list[str]:
        """Default: empty. Vision plan (when it ships) will populate
        `features_meta` with provenance. Subclasses may mine tags here.
        """
        return []

    def best_image_for_variant(
        self,
        variant: dict,
        color_value: str | None,
        images: list[dict],
        *,
        is_only_color: bool,
    ) -> tuple[str | None, bool]:
        """Spec §3a fallback chain. Returns (image_url, image_inferred).

        Steps 1-3 are color-disambiguating lookups. Step 4 differs by context:
        - If this is the ONLY color in the product (single-color product or
          no Color option axis), there is no ambiguity to introduce — fall
          back to images[0] as the hero. image_inferred stays False.
        - If multiple colors exist for the product, return (None, False) and
          let the caller drop the color (per §3a strict rule — never show
          one color's photo as another color's variant).
        """
        fi = variant.get("featured_image")
        if fi and isinstance(fi, dict) and fi.get("src"):
            return (fi["src"], False)

        variant_id = variant.get("id")
        step2 = [
            img for img in images
            if variant_id is not None and variant_id in (img.get("variant_ids") or [])
            and img.get("src")
        ]
        if step2:
            step2.sort(key=lambda i: i.get("position") or 9999)
            return (step2[0]["src"], False)

        if color_value:
            needle = color_value.lower()
            step3 = [
                img for img in images
                if img.get("src") and (img.get("alt") or "").lower().find(needle) >= 0
            ]
            if step3:
                step3.sort(key=lambda i: i.get("position") or 9999)
                return (step3[0]["src"], False)

        # Step 4 — single-color products: images[0] is the right hero (no
        # other color to confuse it with). Multi-color products: drop.
        if is_only_color and images:
            sorted_imgs = sorted(images, key=lambda i: i.get("position") or 9999)
            for img in sorted_imgs:
                if img.get("src"):
                    return (img["src"], False)
        return (None, False)

    # -----------------------------------------------------------------
    # to_product — canonical raw → ingest-row mapper
    # -----------------------------------------------------------------

    def to_product(
        self, raw: dict, *, counters: IngestCounters
    ) -> dict | None:
        rpid = str(raw.get("id") or "")
        handle = raw.get("handle") or ""
        if not rpid or not handle:
            logger.debug(
                "product_skipped_missing_keys source=%s id=%r handle=%r",
                self.retailer_slug, rpid, handle,
            )
            return None

        variants = raw.get("variants") or []
        images = raw.get("images") or []
        if not variants:
            counters.skipped_no_variants += 1
            logger.info(
                "product_skipped_no_variants source=%s id=%s",
                self.retailer_slug, rpid,
            )
            return None
        if not images:
            counters.skipped_no_images += 1
            logger.info(
                "product_skipped_no_images source=%s id=%s",
                self.retailer_slug, rpid,
            )
            return None

        options = raw.get("options") or []
        color_pos = self.color_axis_index(options)
        size_pos = next(
            (
                i + 1
                for i, opt in enumerate(options)
                if (opt.get("name") or "").strip().lower() == "size"
            ),
            None,
        )

        by_color: dict[str, list[dict]] = {}
        size_set: set[str] = set()
        for v in variants:
            raw_color = (
                v.get(f"option{color_pos}") if color_pos else None
            ) or None
            color = normalize_color(raw_color) if raw_color else None
            if size_pos:
                size_val = v.get(f"option{size_pos}")
                if size_val and isinstance(size_val, str):
                    size_set.add(size_val.strip())
            key = color or "__default__"
            by_color.setdefault(key, []).append(v)

        variant_entries: list[dict] = []
        surviving_colors: list[str] = []
        is_only_color_product = len(by_color) == 1
        for color, vlist in by_color.items():
            anchor = next((v for v in vlist if v.get("available")), vlist[0])
            color_value = None if color == "__default__" else color
            display_color = color_value or "default"
            image_url, image_inferred = self.best_image_for_variant(
                anchor, color_value, images,
                is_only_color=is_only_color_product,
            )
            if not image_url:
                counters.skipped_no_color_image += 1
                logger.info(
                    "variant_skipped_no_color_image source=%s id=%s color=%s",
                    self.retailer_slug, rpid, display_color,
                )
                continue
            entry = {
                "color": display_color,
                "image_url": image_url,
                "ai_generated": False,
                "available": bool(anchor.get("available")),
            }
            if image_inferred:
                entry["image_inferred"] = True
            variant_entries.append(entry)
            if color_value:
                surviving_colors.append(color_value)

        if not variant_entries:
            logger.info(
                "product_skipped_all_colors_dropped source=%s id=%s",
                self.retailer_slug, rpid,
            )
            return None

        hero_image_url = variant_entries[0]["image_url"]

        avail_variants = [v for v in variants if v.get("available")] or variants

        def _parse_decimal(value: Any) -> float | None:
            if value in (None, ""):
                return None
            try:
                return float(str(value))
            except ValueError:
                return None

        prices = [_parse_decimal(v.get("price")) for v in avail_variants]
        prices = [p for p in prices if p is not None]
        if not prices:
            counters.skipped_no_variants += 1
            logger.info(
                "product_skipped_no_price source=%s id=%s",
                self.retailer_slug, rpid,
            )
            return None
        price = min(prices)
        anchor_v = next(
            (v for v in avail_variants if _parse_decimal(v.get("price")) == price),
            avail_variants[0],
        )
        compare_at = _parse_decimal(anchor_v.get("compare_at_price"))
        original_price = compare_at if compare_at and compare_at > price else None

        product_currency = (
            anchor_v.get("price_currency") or self.currency or "USD"
        ).upper()
        if product_currency != self.currency.upper():
            counters.skipped_bad_currency += 1
            logger.warning(
                "product_skipped_bad_currency source=%s id=%s got=%s expected=%s",
                self.retailer_slug, rpid, product_currency, self.currency,
            )
            return None

        gender = self.gender_for(raw, counters=counters)
        category, raw_category = self.category_for(raw)

        # Category-implied gender — if gender came out "unisex" but the
        # category is one that's overwhelmingly women's (dresses, skirts,
        # swimwear), trust the category. Helps catch products whose tags
        # didn't say women's but whose category is unambiguous.
        if gender == "unisex" and category in CATEGORY_IMPLIED_GENDER:
            implied = CATEGORY_IMPLIED_GENDER[category]
            if implied == "women" or implied == "men":
                gender = implied  # type: ignore[assignment]
                counters.gender_inferred_from_fallback += 1

        if category is None:
            counters.skipped_unmapped_category += 1
            logger.info(
                "category_alias_miss source=%s id=%s raw=%r",
                self.retailer_slug, rpid, raw_category,
            )

        in_stock = any(v.get("available") for v in variants)

        attributes: dict[str, Any] = {
            "variants": variant_entries,
            "features": self.features_for(raw),
        }
        if raw_category:
            attributes["raw_category"] = raw_category
        attributes.setdefault("features_meta", {})

        url = f"{self.base_url.rstrip('/')}/products/{handle}"

        return {
            "retailer": self.retailer_slug,
            "retailer_product_id": rpid,
            "url": url,
            "title": raw.get("title") or "",
            "brand": raw.get("vendor") or self.retailer_slug,
            "category": category,
            "gender": gender,
            "description": strip_html(raw.get("body_html")),
            "price": f"{price:.2f}",
            "original_price": f"{original_price:.2f}" if original_price is not None else None,
            "currency": self.currency.upper(),
            "image_url": hero_image_url,
            "colors": surviving_colors or None,
            "sizes": sorted(size_set) if size_set else None,
            "attributes": attributes,
            "in_stock": in_stock,
        }
