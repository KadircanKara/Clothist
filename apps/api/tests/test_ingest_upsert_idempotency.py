"""T2 — Upsert-idempotency for `original_price`.

The fix in plans/scraping/senior_dev_v2.md §2c adds `"original_price"` to
the `UPDATE_COLS` tuple. Without that fix, re-running ingest leaves the
original_price column frozen at its first-seen value — a product going
on sale would never show the discount in the catalog.

This test exercises the actual `services.ingest_common.build_upsert_stmt`
+ `to_row` path against the real DB. Catches the regression directly.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select, text

from clothist_api.db.session import SessionLocal
from clothist_api.models import Product
from clothist_api.services.ingest_common import build_upsert_stmt, to_row


TEST_RETAILER = "test"
TEST_RPID = "ingest-upsert-idempotency-test-1"


def _base_row(price: str, original_price: str | None) -> dict:
    return {
        "retailer": TEST_RETAILER,
        "retailer_product_id": TEST_RPID,
        "url": "https://example.com/test",
        "title": "Upsert Test Product",
        "brand": "TestBrand",
        "category": "tshirts",
        "gender": "unisex",
        "description": "Fixture for upsert idempotency test.",
        "price": price,
        "original_price": original_price,
        "currency": "USD",
        "image_url": "https://example.com/test.jpg",
        "colors": ["black"],
        "sizes": ["M"],
        "attributes": {"variants": [], "features": []},
        "in_stock": True,
    }


@pytest.mark.asyncio
async def test_original_price_refreshes_on_reupsert():
    """Insert a row with price=100, original_price=150. Re-insert with the
    same key but price=80, original_price=120. After the second upsert, the
    row should reflect the NEW values — proving original_price is in
    UPDATE_COLS.
    """
    async with SessionLocal() as session:
        # Cleanup any leftover from a prior aborted run.
        await session.execute(
            text(
                "DELETE FROM products WHERE retailer = :r AND retailer_product_id = :id"
            ).bindparams(r=TEST_RETAILER, id=TEST_RPID)
        )
        await session.commit()

        # First upsert — price=100, original_price=150
        row1 = to_row(_base_row(price="100.00", original_price="150.00"))
        stmt1 = build_upsert_stmt([row1])
        await session.execute(stmt1)
        await session.commit()

        # Second upsert — same key, price=80, original_price=120
        row2 = to_row(_base_row(price="80.00", original_price="120.00"))
        stmt2 = build_upsert_stmt([row2])
        await session.execute(stmt2)
        await session.commit()

        # Verify the refreshed values
        result = await session.execute(
            select(Product.price, Product.original_price).where(
                (Product.retailer == TEST_RETAILER)
                & (Product.retailer_product_id == TEST_RPID)
            )
        )
        price, original_price = result.one()
        # Cleanup
        await session.execute(
            text(
                "DELETE FROM products WHERE retailer = :r AND retailer_product_id = :id"
            ).bindparams(r=TEST_RETAILER, id=TEST_RPID)
        )
        await session.commit()

        assert str(price) == "80.00", (
            f"price not refreshed on re-upsert: got {price}"
        )
        assert str(original_price) == "120.00", (
            f"original_price not refreshed on re-upsert: got {original_price}. "
            f"Did you forget to add 'original_price' to UPDATE_COLS?"
        )
