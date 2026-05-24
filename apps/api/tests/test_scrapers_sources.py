"""T1 — Per-adapter fixture replay.

For each Tier-1 source: load a captured /products.json snapshot, feed every
product through its adapter's `to_product()`, and assert the canonical row
shape. Catches regressions when a vendor tweaks their tag namespace or schema
without us noticing.

Fixtures captured live on 24 May 2026; re-capture when adapter behavior
changes by rerunning the curl-loop in plans/scraping/senior_dev_v2.md §11
deliverable D-tests.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pytest

from clothist_api.scrapers import IngestCounters
from clothist_api.scrapers.sources import SOURCES


CANONICAL_GENDERS = frozenset({"men", "women", "unisex"})


def _load_fixture(slug: str, fixtures_dir: Path) -> list[dict]:
    raw = json.loads((fixtures_dir / "scrapers" / f"{slug}.json").read_text())
    return list(raw.get("products") or [])


@pytest.mark.parametrize("slug", sorted(SOURCES))
def test_adapter_maps_fixture(slug: str, fixtures_dir: Path):
    adapter = SOURCES[slug]()
    products = _load_fixture(slug, fixtures_dir)
    assert products, f"Fixture for {slug} is empty"

    counters = IngestCounters()
    mapped = []
    for raw in products:
        row = adapter.to_product(raw, counters=counters)
        if row is not None:
            mapped.append(row)

    # At least 1 of the 5 fixture products should successfully map. If 0 do,
    # the adapter or the vendor's schema has changed.
    assert mapped, (
        f"{slug}: zero products mapped from fixture. "
        f"counters={asdict(counters)}"
    )


@pytest.mark.parametrize("slug", sorted(SOURCES))
def test_required_fields_present(slug: str, fixtures_dir: Path):
    """Every mapped row must have the columns the ingest pipeline depends on."""
    required_keys = {
        "retailer", "retailer_product_id", "url", "title", "brand",
        "category", "gender", "price", "currency",
        "image_url", "attributes", "in_stock",
    }
    adapter = SOURCES[slug]()
    products = _load_fixture(slug, fixtures_dir)
    counters = IngestCounters()
    for raw in products:
        row = adapter.to_product(raw, counters=counters)
        if row is None:
            continue
        missing = required_keys - set(row.keys())
        assert not missing, (
            f"{slug} product {row.get('retailer_product_id')!r} missing keys: {missing}"
        )


@pytest.mark.parametrize("slug", sorted(SOURCES))
def test_gender_canonical(slug: str, fixtures_dir: Path):
    """Every mapped row's `gender` must be in our canonical set."""
    adapter = SOURCES[slug]()
    products = _load_fixture(slug, fixtures_dir)
    counters = IngestCounters()
    for raw in products:
        row = adapter.to_product(raw, counters=counters)
        if row is None:
            continue
        assert row["gender"] in CANONICAL_GENDERS, (
            f"{slug} product {row['retailer_product_id']!r} has non-canonical "
            f"gender={row['gender']!r}"
        )


@pytest.mark.parametrize("slug", sorted(SOURCES))
def test_retailer_slug_set(slug: str, fixtures_dir: Path):
    """`retailer` must equal the adapter's declared slug — guards against
    typos that would make seed/real rows collide."""
    adapter = SOURCES[slug]()
    products = _load_fixture(slug, fixtures_dir)
    counters = IngestCounters()
    for raw in products:
        row = adapter.to_product(raw, counters=counters)
        if row is None:
            continue
        assert row["retailer"] == adapter.retailer_slug


@pytest.mark.parametrize("slug", sorted(SOURCES))
def test_variants_have_image_urls(slug: str, fixtures_dir: Path):
    """Every variant in attributes.variants[] must have a non-empty image_url
    (the §3a step-4 skip rule should have dropped any that didn't)."""
    adapter = SOURCES[slug]()
    products = _load_fixture(slug, fixtures_dir)
    counters = IngestCounters()
    for raw in products:
        row = adapter.to_product(raw, counters=counters)
        if row is None:
            continue
        variants = row["attributes"].get("variants") or []
        assert variants, f"{slug}: {row['retailer_product_id']} has no surviving variants"
        for v in variants:
            assert v.get("image_url"), (
                f"{slug}: {row['retailer_product_id']} variant {v.get('color')!r} "
                f"has empty image_url — §3a step-4 should have dropped it"
            )


@pytest.mark.parametrize("slug", sorted(SOURCES))
def test_price_parses_to_decimal(slug: str, fixtures_dir: Path):
    """Price strings must be Decimal-parseable; price >= 0."""
    from decimal import Decimal

    adapter = SOURCES[slug]()
    products = _load_fixture(slug, fixtures_dir)
    counters = IngestCounters()
    for raw in products:
        row = adapter.to_product(raw, counters=counters)
        if row is None:
            continue
        price = Decimal(row["price"])
        assert price >= 0, f"{slug}: negative price {price}"
        if row.get("original_price") is not None:
            orig = Decimal(row["original_price"])
            assert orig > price, (
                f"{slug}: original_price {orig} not greater than price {price}"
            )
