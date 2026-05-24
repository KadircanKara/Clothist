"""Kill switch — restore top-level category/gender/colors from
`attributes.cv_verdict.scraper_previous`. Use when a bad CV run shipped.

Usage:
    uv run python -m clothist_api.scripts.cv_rollback [--retailer slug] [--dry-run]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys

from sqlalchemy import text

from clothist_api.db.session import SessionLocal

logger = logging.getLogger(__name__)


async def rollback(*, retailer: str | None, dry_run: bool) -> int:
    async with SessionLocal() as session:
        sql = (
            "SELECT id, category, gender, colors, "
            "attributes -> 'cv_verdict' -> 'scraper_previous' AS prev "
            "FROM products "
            "WHERE attributes ? 'cv_verdict' "
            "  AND attributes -> 'cv_verdict' ? 'scraper_previous'"
        )
        params = {}
        if retailer:
            sql += " AND retailer = :p_retailer"
            params["p_retailer"] = retailer

        rows = (await session.execute(text(sql), params)).mappings().all()
        logger.info("rollback_candidates n=%d retailer=%s", len(rows), retailer)

        n_restored = 0
        for r in rows:
            prev = r["prev"] or {}
            if dry_run:
                logger.info(
                    "dry_run_would_restore id=%s cur=(%s,%s,%s) prev=(%s,%s,%s)",
                    r["id"],
                    r["category"], r["gender"], r["colors"],
                    prev.get("category"), prev.get("gender"), prev.get("colors"),
                )
                continue
            await session.execute(
                text(
                    """
                    UPDATE products
                    SET category = :cat, gender = :gen, colors = :cols,
                        attributes = attributes - 'cv_verdict' - 'cv_classified_at' - 'cv_model'
                    WHERE id = :pid
                    """
                ).bindparams(
                    cat=prev.get("category"),
                    gen=prev.get("gender"),
                    cols=prev.get("colors"),
                    pid=r["id"],
                )
            )
            n_restored += 1

        if not dry_run:
            await session.commit()
        return n_restored


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Restore pre-CV category/gender/colors from "
                    "attributes.cv_verdict.scraper_previous."
    )
    parser.add_argument("--retailer", default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    n = asyncio.run(rollback(retailer=args.retailer, dry_run=args.dry_run))
    print(f"Restored {n} products. {'(dry run)' if args.dry_run else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
