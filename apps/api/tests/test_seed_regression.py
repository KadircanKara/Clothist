"""T3 — Seed loader regression after the ingest_common refactor.

`scripts/seed.py` used to define `_to_row` inline. The refactor moves it to
`services/ingest_common.py`. Both paths must keep working — confirm the
seed script still loads `data/seed/products.json` end-to-end without error.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from clothist_api.services.ingest_common import to_row


SEED_FILE = Path(__file__).resolve().parents[3] / "data" / "seed" / "products.json"


def test_seed_file_exists():
    assert SEED_FILE.exists(), f"Seed file missing: {SEED_FILE}"


def test_to_row_handles_every_seed_entry():
    """to_row() should not raise for any product in the live seed file."""
    raw_items = json.loads(SEED_FILE.read_text())
    for item in raw_items:
        row = to_row(item)
        assert row["retailer"] == item.get("retailer")
        assert row["retailer_product_id"] == item.get("retailer_product_id")
        # fx_rate_used must be set — proves the FX lookup succeeded.
        assert row.get("fx_rate_used") is not None
        # price_usd must NOT be set (GENERATED column).
        assert "price_usd" not in row
