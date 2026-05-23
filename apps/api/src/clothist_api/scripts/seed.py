"""Load hand-curated seed products from data/seed/products.json into the DB.

Usage:
    uv run python -m clothist_api.scripts.seed
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from clothist_api.db.session import SessionLocal
from clothist_api.models import Product
from clothist_api.services.fx import UnknownCurrencyError, rate_for

logger = logging.getLogger(__name__)

SEED_FILE = Path(__file__).resolve().parents[5] / "data" / "seed" / "products.json"


def _to_row(raw: dict) -> dict:
    row = dict(raw)
    if row.get("price") is not None:
        row["price"] = Decimal(str(row["price"]))
    if row.get("original_price") is not None:
        row["original_price"] = Decimal(str(row["original_price"]))
    row.setdefault("attributes", {})
    row.setdefault("in_stock", True)
    row["scraped_at"] = datetime.now(timezone.utc)

    ccy = (row.get("currency") or "USD").upper()
    try:
        row["fx_rate_used"] = rate_for(ccy)
    except UnknownCurrencyError as e:
        raise RuntimeError(
            f"Seed row '{row.get('retailer_product_id')}' has unknown currency {ccy!r}; "
            f"add it to data/fx/rates.json"
        ) from e
    # price_usd is a GENERATED column — never set it directly.
    row.pop("price_usd", None)
    return row


async def seed() -> int:
    if not SEED_FILE.exists():
        raise FileNotFoundError(f"Seed file not found: {SEED_FILE}")

    raw_items = json.loads(SEED_FILE.read_text())
    rows = [_to_row(item) for item in raw_items]

    stmt = pg_insert(Product).values(rows)
    update_cols = {
        col: stmt.excluded[col]
        for col in (
            "url", "title", "brand", "category", "description",
            "price", "currency", "fx_rate_used",
            "image_url", "colors", "sizes",
            "attributes", "in_stock", "scraped_at",
        )
    }
    stmt = stmt.on_conflict_do_update(
        constraint="uq_products_retailer_rpid",
        set_=update_cols,
    )

    async with SessionLocal() as session:
        await session.execute(stmt)
        # Bump taxonomy_version so the facets cache invalidates.
        await session.execute(
            text("UPDATE meta SET taxonomy_version = taxonomy_version + 1")
        )
        await session.commit()

    return len(rows)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    n = asyncio.run(seed())
    print(f"Seeded {n} products from {SEED_FILE.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
