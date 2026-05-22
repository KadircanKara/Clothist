"""H&M Tier-3 extractor.

Strategy:
  1. Fetch the HTML page (product or listing).
  2. Pull JSON-LD `<script type="application/ld+json">` blocks.
  3. For product pages: find `@type == "Product"` and normalize.
  4. For listing pages: walk __NEXT_DATA__ for product URLs and recurse.

Limitations:
  - H&M markets use Akamai bot detection. Plain HTTP requests may be blocked
    (403) from some IPs; in that case the caller sees BlockedError and we
    surface it rather than silently failing. Playwright fallback is future work.
  - Page structures change. JSON-LD parse is the most stable surface; we
    deliberately avoid CSS-selector-based extraction.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urljoin

from clothist_api.scrapers.base import (
    RetailerClient,
    ScrapeError,
    get_next_data,
    iter_jsonld,
)

logger = logging.getLogger(__name__)

RETAILER = "hm"

# H&M URLs look like .../productpage.0123456789.html — the digits are the article code.
ARTICLE_CODE_RE = re.compile(r"productpage\.(\d+)\.html", re.IGNORECASE)


@dataclass(slots=True)
class HMProduct:
    retailer_product_id: str
    url: str
    title: str
    brand: str | None
    category: str | None
    description: str | None
    price: Decimal | None
    currency: str | None
    image_url: str | None
    colors: list[str] | None
    sizes: list[str] | None
    in_stock: bool
    raw: dict[str, Any]

    def as_db_row(self) -> dict[str, Any]:
        return {
            "retailer": RETAILER,
            "retailer_product_id": self.retailer_product_id,
            "url": self.url,
            "title": self.title,
            "brand": self.brand,
            "category": self.category,
            "description": self.description,
            "price": self.price,
            "currency": self.currency,
            "image_url": self.image_url,
            "colors": self.colors,
            "sizes": self.sizes,
            "attributes": {"raw_jsonld_keys": sorted(self.raw.keys())},
            "in_stock": self.in_stock,
            "scraped_at": datetime.now(timezone.utc),
        }


def _coerce_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _first_image(image_field: Any) -> str | None:
    if isinstance(image_field, str):
        return image_field
    if isinstance(image_field, list) and image_field:
        first = image_field[0]
        if isinstance(first, str):
            return first
        if isinstance(first, dict):
            return first.get("url") or first.get("contentUrl")
    if isinstance(image_field, dict):
        return image_field.get("url") or image_field.get("contentUrl")
    return None


def _brand_name(brand_field: Any) -> str | None:
    if isinstance(brand_field, str):
        return brand_field
    if isinstance(brand_field, dict):
        return brand_field.get("name")
    return None


def _article_code(url: str, jsonld: dict[str, Any]) -> str | None:
    m = ARTICLE_CODE_RE.search(url)
    if m:
        return m.group(1)
    for key in ("sku", "productID", "mpn"):
        val = jsonld.get(key)
        if isinstance(val, str) and val:
            return val
    return None


def _offer_fields(offers: Any) -> tuple[Decimal | None, str | None, bool]:
    """Returns (price, currency, in_stock)."""
    if isinstance(offers, list) and offers:
        offers = offers[0]
    if not isinstance(offers, dict):
        return None, None, True

    price = _coerce_decimal(offers.get("price") or offers.get("lowPrice"))
    currency = offers.get("priceCurrency")
    availability = (offers.get("availability") or "").lower()
    in_stock = "instock" in availability or "instock" in availability.replace(" ", "")
    if not availability:
        in_stock = True
    return price, currency, in_stock


def parse_product(url: str, html: str) -> HMProduct | None:
    """Find the first JSON-LD Product block on the page and normalize it."""
    for block in iter_jsonld(html):
        block_type = block.get("@type")
        if block_type == "Product" or (
            isinstance(block_type, list) and "Product" in block_type
        ):
            rpid = _article_code(url, block)
            if not rpid:
                logger.warning("Could not derive article code for %s", url)
                continue
            offers = block.get("offers")
            price, currency, in_stock = _offer_fields(offers)
            color = block.get("color")
            colors = [color] if isinstance(color, str) and color else None
            return HMProduct(
                retailer_product_id=rpid,
                url=url,
                title=str(block.get("name") or "").strip() or "Untitled",
                brand=_brand_name(block.get("brand")) or "H&M",
                category=block.get("category"),
                description=block.get("description"),
                price=price,
                currency=currency,
                image_url=_first_image(block.get("image")),
                colors=colors,
                sizes=None,  # H&M JSON-LD rarely carries sizes; future work
                in_stock=in_stock,
                raw=block,
            )
    return None


def iter_listing_product_urls(base_url: str, html: str) -> list[str]:
    """Walk __NEXT_DATA__ for product URLs on a listing page."""
    next_data = get_next_data(html)
    if not next_data:
        return []

    urls: set[str] = set()

    def walk(obj: Any) -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k in {"url", "linkPdp", "productLink"} and isinstance(v, str):
                    if "productpage" in v:
                        urls.add(urljoin(base_url, v))
                walk(v)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(next_data)
    return sorted(urls)


async def scrape_one(client: RetailerClient, url: str) -> HMProduct:
    page = await client.fetch(url)
    product = parse_product(page.url, page.html)
    if product is None:
        raise ScrapeError(f"No JSON-LD Product block found at {url}")
    return product


async def scrape_listing(
    client: RetailerClient,
    listing_url: str,
    limit: int = 20,
) -> list[HMProduct]:
    page = await client.fetch(listing_url)
    product_urls = iter_listing_product_urls(page.url, page.html)
    if not product_urls:
        logger.warning("No product URLs found in listing %s", listing_url)
        return []
    product_urls = product_urls[:limit]
    results: list[HMProduct] = []
    for purl in product_urls:
        try:
            results.append(await scrape_one(client, purl))
        except ScrapeError as e:
            logger.warning("Skipped %s: %s", purl, e)
    return results
