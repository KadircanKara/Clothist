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


@pytest.mark.asyncio
async def test_cv_keys_survive_reingest():
    """CR-6 / CR-14 / §5b — when the scraper re-ingests a product, JSONB
    keys that live alongside the scraper's payload (notably `cv_verdict`,
    `cv_classified_at`, `cv_model`) MUST survive the upsert.

    The fix in build_upsert_stmt is to merge `attributes` via Postgres
    `jsonb || jsonb` rather than replace it. Without the merge, every
    re-ingest wipes the CV verdict and demotes the catalog back to the
    scraper's text-derived guess.
    """
    test_rpid = "cv-survives-reingest-test-1"
    async with SessionLocal() as session:
        # Cleanup any leftover.
        await session.execute(
            text(
                "DELETE FROM products WHERE retailer = :r AND retailer_product_id = :id"
            ).bindparams(r=TEST_RETAILER, id=test_rpid)
        )
        await session.commit()

        # First upsert — scraper writes its own attributes payload.
        row1 = to_row({
            **_base_row(price="100.00", original_price=None),
            "retailer_product_id": test_rpid,
            "attributes": {"variants": [], "features": [], "raw_category": "Tees"},
        })
        await session.execute(build_upsert_stmt([row1]))
        await session.commit()

        # Simulate the CV pass writing into attributes via a direct UPDATE
        # (the real CV CLI does this; we just need to ensure the shape ends
        # up the same).
        cv_payload = {
            "cv_verdict": {
                "category": {"value": "tshirts", "confidence": 0.91, "runner_up": None},
                "gender":   {"value": "unisex",  "confidence": 0.80, "runner_up": None},
                "colors":   [],
                "scraper_previous": {"category": "tshirts", "gender": "unisex"},
                "colors_previous": [],
            },
            "cv_classified_at": "2026-05-24T17:00:00+00:00",
            "cv_model": "openai/clip-vit-base-patch32",
        }
        await session.execute(
            text(
                "UPDATE products "
                "SET attributes = attributes || CAST(:p AS jsonb) "
                "WHERE retailer = :r AND retailer_product_id = :id"
            ).bindparams(
                p=__import__("json").dumps(cv_payload),
                r=TEST_RETAILER,
                id=test_rpid,
            )
        )
        await session.commit()

        # Second scraper upsert — same product, scraper writes its
        # attributes payload AGAIN. This is the re-ingest case.
        row2 = to_row({
            **_base_row(price="95.00", original_price=None),
            "retailer_product_id": test_rpid,
            "attributes": {"variants": [], "features": [], "raw_category": "Tees"},
        })
        await session.execute(build_upsert_stmt([row2]))
        await session.commit()

        # Verify the CV keys are still present.
        result = await session.execute(
            select(Product.attributes, Product.price).where(
                (Product.retailer == TEST_RETAILER)
                & (Product.retailer_product_id == test_rpid)
            )
        )
        attrs, price = result.one()

        # Cleanup.
        await session.execute(
            text(
                "DELETE FROM products WHERE retailer = :r AND retailer_product_id = :id"
            ).bindparams(r=TEST_RETAILER, id=test_rpid)
        )
        await session.commit()

        # Scraper-side keys refreshed.
        assert str(price) == "95.00", f"price not refreshed: {price}"
        assert attrs.get("raw_category") == "Tees"

        # CV-side keys preserved.
        assert "cv_verdict" in attrs, (
            "cv_verdict missing after re-ingest — JSONB merge is not preserving CV keys. "
            "Check build_upsert_stmt in services/ingest_common.py."
        )
        assert attrs["cv_classified_at"] == "2026-05-24T17:00:00+00:00"
        assert attrs["cv_model"] == "openai/clip-vit-base-patch32"
        assert attrs["cv_verdict"]["category"]["value"] == "tshirts"
