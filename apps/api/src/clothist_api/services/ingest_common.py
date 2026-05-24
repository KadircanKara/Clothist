"""Shared ingest helpers used by both the offline seed loader and the
real-product Shopify ingest.

`to_row()` is the canonical raw-dict → SQLAlchemy-row transform. It populates
`fx_rate_used` via the FX snapshot, normalises Decimals, and refuses to ship
a row with `price_usd` set (that's a GENERATED column).

`UPDATE_COLS` is the canonical upsert SET list — every column we expect the
ingest to refresh on re-run. Adding/removing columns here is the only
single-source-of-truth way to change upsert semantics across both ingest
paths.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import func, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from clothist_api.models import Product
from clothist_api.services.fx import UnknownCurrencyError, rate_for


# Columns refreshed on conflict-upsert. `original_price` is here so sale
# prices update on re-run — without it, a product going on sale would never
# show the discount in our catalog.
UPDATE_COLS: tuple[str, ...] = (
    "url",
    "title",
    "brand",
    "category",
    "gender",
    "description",
    "price",
    "original_price",
    "currency",
    "fx_rate_used",
    "image_url",
    "colors",
    "sizes",
    "attributes",
    "in_stock",
    "scraped_at",
)


def to_row(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalise a product dict for INSERT/UPSERT into `products`.

    Caller passes the raw shape from either the seed JSON or a scraper
    adapter; we return a dict ready for `pg_insert(Product).values([row])`.

    Raises `RuntimeError` if the currency is unknown to the FX snapshot —
    the only legal failure mode here is "you forgot to add the currency to
    data/fx/rates.json".
    """
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
            f"Product '{row.get('retailer_product_id')}' has unknown currency "
            f"{ccy!r}; add it to data/fx/rates.json"
        ) from e

    # price_usd is a GENERATED column — Postgres rejects writes to it.
    row.pop("price_usd", None)
    return row


def build_upsert_stmt(rows: list[dict[str, Any]]):
    """Build the ON CONFLICT DO UPDATE statement keyed by
    (retailer, retailer_product_id), refreshing all UPDATE_COLS.

    `attributes` is special-cased: instead of a full JSONB replacement, the
    statement does a shallow merge via Postgres's `||` operator. The scraper
    writes its keys on top of whatever is there; CV-side keys (`cv_verdict`,
    `cv_classified_at`, `cv_model`, `cv_image_hash`, `cv_fetch_failures`,
    `cv_skip_until`) survive re-ingest because they're never in the
    scraper's outgoing payload. See plans/cv_classify/senior_dev_v2.md §5b.
    """
    stmt = pg_insert(Product).values(rows)
    update_set = {col: stmt.excluded[col] for col in UPDATE_COLS if col != "attributes"}
    # JSONB-merge: existing.attributes || incoming.attributes.
    # `func.coalesce` defends against a row that somehow has NULL attributes,
    # though `server_default '{}'::jsonb` on the column makes it unlikely.
    update_set["attributes"] = func.coalesce(
        Product.__table__.c.attributes, text("'{}'::jsonb")
    ).op("||")(stmt.excluded.attributes)
    return stmt.on_conflict_do_update(
        constraint="uq_products_retailer_rpid",
        set_=update_set,
    )
