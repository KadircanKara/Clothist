"""Manual H&M scraper entrypoint.

Usage:
    uv run python -m clothist_api.scripts.scrape_hm <url> [--limit N]

<url> can be either a product page (.../productpage.NNNNN.html) or a listing
page; listing pages are walked for up to --limit product URLs.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from sqlalchemy.dialects.postgresql import insert as pg_insert

from clothist_api.db.session import SessionLocal
from clothist_api.models import Product
from clothist_api.scrapers.base import BlockedError, RetailerClient, ScrapeError
from clothist_api.scrapers.hm import HMProduct, scrape_listing, scrape_one

logger = logging.getLogger(__name__)


async def upsert_products(rows: list[HMProduct]) -> int:
    if not rows:
        return 0
    payload = [r.as_db_row() for r in rows]
    stmt = pg_insert(Product).values(payload)
    update_cols = {
        col: stmt.excluded[col]
        for col in (
            "url",
            "title",
            "brand",
            "category",
            "description",
            "price",
            "currency",
            "image_url",
            "colors",
            "sizes",
            "attributes",
            "in_stock",
            "scraped_at",
        )
    }
    stmt = stmt.on_conflict_do_update(
        constraint="uq_products_retailer_rpid",
        set_=update_cols,
    )
    async with SessionLocal() as session:
        await session.execute(stmt)
        await session.commit()
    return len(payload)


async def run(url: str, limit: int) -> int:
    async with RetailerClient() as client:
        if "productpage." in url:
            products = [await scrape_one(client, url)]
        else:
            products = await scrape_listing(client, url, limit=limit)
    return await upsert_products(products)


def main() -> int:
    parser = argparse.ArgumentParser(description="Scrape H&M product or listing into Postgres.")
    parser.add_argument("url", help="H&M product or listing URL")
    parser.add_argument("--limit", type=int, default=20, help="Max products from a listing")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    try:
        n = asyncio.run(run(args.url, args.limit))
    except BlockedError as e:
        logger.error("Blocked: %s", e)
        return 2
    except ScrapeError as e:
        logger.error("Scrape failed: %s", e)
        return 1

    print(f"Upserted {n} product(s) from {args.url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
