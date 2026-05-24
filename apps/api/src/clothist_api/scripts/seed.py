"""Load hand-curated seed products from data/seed/products.json into the DB.

Usage:
    uv run python -m clothist_api.scripts.seed
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path

from sqlalchemy import text

from clothist_api.db.session import SessionLocal
from clothist_api.services.ingest_common import build_upsert_stmt, to_row

logger = logging.getLogger(__name__)

SEED_FILE = Path(__file__).resolve().parents[5] / "data" / "seed" / "products.json"


async def seed() -> int:
    if not SEED_FILE.exists():
        raise FileNotFoundError(f"Seed file not found: {SEED_FILE}")

    raw_items = json.loads(SEED_FILE.read_text())
    rows = [to_row(item) for item in raw_items]

    stmt = build_upsert_stmt(rows)
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
