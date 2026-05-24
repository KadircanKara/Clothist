"""One-time helper: select 20 products via fixed-seed stratified random
sample and emit them to tests/fixtures/cv/golden.jsonl as a starter file.

The implementer (operator) hand-labels each row's expected category +
gender + dominant colors, then commits the file. T1 (`test_cv_classifier`)
runs against the labelled set.

Usage:
    uv run python -m clothist_api.scripts.seed_cv_golden
"""
from __future__ import annotations

import asyncio
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

from sqlalchemy import text

from clothist_api.db.session import SessionLocal

OUT = Path(__file__).resolve().parents[5] / "apps" / "api" / "tests" / "fixtures" / "cv" / "golden.starter.jsonl"


CATEGORIES = (
    "hoodies", "tshirts", "pants", "jeans", "shorts", "skirts",
    "dresses", "jackets", "footwear", "sweaters", "accessories",
    "swimwear", "underwear",
)


async def select_sample() -> list[dict]:
    random.seed(20260524)
    async with SessionLocal() as session:
        rows = (
            await session.execute(text(
                "SELECT retailer_product_id, image_url, category, gender, "
                "colors, title, brand "
                "FROM products WHERE image_url IS NOT NULL"
            ))
        ).mappings().all()

    by_cat: dict[str | None, list[dict]] = defaultdict(list)
    for r in rows:
        by_cat[r["category"]].append(dict(r))

    picked: list[dict] = []
    # Stratify: at least 1 per category (cap 2), prefer gender variety.
    for cat in CATEGORIES:
        pool = by_cat.get(cat, [])
        if not pool:
            continue
        pool_sorted = sorted(pool, key=lambda r: r["retailer_product_id"])
        random.shuffle(pool_sorted)
        picked.extend(pool_sorted[:2])

    # Trim to 20 with gender balance — pad with anything if we're short.
    if len(picked) > 20:
        picked = picked[:20]
    else:
        leftover = [r for r in rows if r not in picked]
        random.shuffle(leftover)
        picked.extend(leftover[: max(0, 20 - len(picked))])

    return picked[:20]


async def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    sample = await select_sample()
    with OUT.open("w") as f:
        for r in sample:
            row = {
                "id": r["retailer_product_id"],
                "image_url": r["image_url"],
                "title": r["title"],
                "brand": r["brand"],
                "scraper_category": r["category"],
                "scraper_gender": r["gender"],
                "scraper_colors": r["colors"],
                # Hand-fill these for each row before committing as golden.jsonl
                "category": r["category"],   # CONFIRM
                "gender": r["gender"],       # CONFIRM
                "colors": r["colors"] or [], # CONFIRM
            }
            f.write(json.dumps(row) + "\n")
    print(f"Wrote {len(sample)} candidate rows to {OUT}")
    print(
        "Next: review each row, edit the `category`/`gender`/`colors` "
        "fields to ground truth, then rename to golden.jsonl."
    )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
