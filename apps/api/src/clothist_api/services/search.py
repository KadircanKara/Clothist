"""Search service: Postgres FTS + JSONB features + canonical USD price.

Ranking (when sort=relevance and a text query or features are present):

  score = 0.6 * ts_rank_norm + 0.4 * feature_match_norm

  ts_rank_norm = LEAST(ts_rank_cd(...) / 0.5, 1.0)
  feature_match_norm =
    1.0                              when no features requested  (so the
                                     composite cleanly reduces to 0.6 *
                                     ts_rank_norm + 0.4)
    matches / requested_count        otherwise

Price filtering compares the user's bound (already normalized to USD by the
pre-parser) against the `price_usd` GENERATED column on products.

Spec: plans/senior_dev_v3.md §2b, §2d, §4a.
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from clothist_api.models import Meta, Product
from clothist_api.services.features_vocab import get_features_vocabulary
from clothist_api.services.fx import snapshot_date

logger = logging.getLogger(__name__)

SortKey = Literal["relevance", "price_asc", "price_desc", "newest", "highest_rated"]

_TOKEN_RE = re.compile(r"[\w']+", re.UNICODE)


def _to_search_expr(q: str) -> str | None:
    tokens = _TOKEN_RE.findall(q.lower())
    tokens = [t for t in tokens if len(t) > 1]
    if not tokens:
        return None
    return " OR ".join(tokens)


@dataclass(slots=True)
class SearchFilters:
    q: str | None = None
    category: str | None = None
    brand: str | None = None
    gender: str | None = None
    color: str | None = None
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    in_stock_only: bool = False
    features: list[str] = field(default_factory=list)
    excluded_features: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SearchPaging:
    limit: int = 24
    offset: int = 0
    sort: SortKey = "relevance"


# Common WHERE-clause builder used by every path. Returns (sql, params).
def _build_where(f: SearchFilters, *, with_ts: bool) -> tuple[list[str], dict]:
    parts: list[str] = []
    params: dict = {}
    if f.category:
        parts.append("category = :p_category")
        params["p_category"] = f.category
    if f.brand:
        parts.append("brand = :p_brand")
        params["p_brand"] = f.brand
    if f.gender:
        # Strict gender match — each route is exclusive (Men, Unisex, Women).
        parts.append("gender = :p_gender")
        params["p_gender"] = f.gender
    if f.color:
        parts.append("colors @> ARRAY[:p_color]::text[]")
        params["p_color"] = f.color.lower()
    if f.min_price is not None:
        parts.append("price_usd >= :p_min_price")
        params["p_min_price"] = f.min_price
    if f.max_price is not None:
        parts.append("price_usd <= :p_max_price")
        params["p_max_price"] = f.max_price
    if f.in_stock_only:
        parts.append("in_stock = true")
    if f.features:
        # @> requires JSONB on both sides; cast a JSON-string bind to jsonb.
        parts.append("attributes -> 'features' @> CAST(:p_features_json AS jsonb)")
        params["p_features_json"] = json.dumps(f.features)
    if f.excluded_features:
        # Avoid the `?|` operator inside text() (SQLAlchemy treats `?` as a
        # bind placeholder). Use a NOT EXISTS over the unnested feature array.
        parts.append(
            "NOT EXISTS (SELECT 1 FROM jsonb_array_elements_text(attributes -> 'features') AS efeat "
            "WHERE efeat = ANY(CAST(:p_excluded AS text[])))"
        )
        params["p_excluded"] = list(f.excluded_features)
    if with_ts:
        parts.append("search_vector @@ websearch_to_tsquery('english', :p_ts_expr)")
    return parts, params


SCORE_EXPR = """
    0.6 * LEAST(
        ts_rank_cd(search_vector, websearch_to_tsquery('english', :p_ts_expr))
        / 0.5,
        1.0
    )
    + 0.4 * CASE
        WHEN array_length(CAST(:p_score_features AS text[]), 1) IS NULL THEN 1.0
        ELSE COALESCE(
            (
              SELECT COUNT(*)::numeric
              FROM jsonb_array_elements_text(attributes -> 'features') AS sfeat
              WHERE sfeat = ANY(CAST(:p_score_features AS text[]))
            )
            / NULLIF(array_length(CAST(:p_score_features AS text[]), 1), 0)::numeric,
            0.0
        )
      END
"""


async def search_products(
    session: AsyncSession,
    f: SearchFilters,
    p: SearchPaging,
) -> tuple[int, list[Product]]:
    search_expr = _to_search_expr(f.q) if f.q else None
    sort: SortKey = p.sort or "relevance"
    if sort == "highest_rated":
        sort = "relevance"

    with_ts = search_expr is not None
    where_parts, params = _build_where(f, with_ts=with_ts)
    if with_ts:
        params["p_ts_expr"] = search_expr
    where_sql = " AND ".join(where_parts) if where_parts else "TRUE"

    count_sql = f"SELECT COUNT(*) FROM products WHERE {where_sql}"
    total = (await session.execute(text(count_sql), params)).scalar_one()

    use_score = sort == "relevance" and (with_ts or bool(f.features))
    if use_score:
        params["p_score_features"] = list(f.features)
        if not with_ts:
            # SCORE_EXPR references :p_ts_expr; bind an empty string so the
            # ts_rank_cd call returns 0 when there's no text query.
            params["p_ts_expr"] = ""
        order_by = "ORDER BY score DESC, created_at DESC"
        select_cols = f"products.*, ({SCORE_EXPR}) AS score"
    elif sort == "price_asc":
        order_by = "ORDER BY price_usd ASC NULLS LAST, created_at DESC"
        select_cols = "products.*"
    elif sort == "price_desc":
        order_by = "ORDER BY price_usd DESC NULLS LAST, created_at DESC"
        select_cols = "products.*"
    elif sort == "newest":
        order_by = "ORDER BY created_at DESC"
        select_cols = "products.*"
    else:
        order_by = "ORDER BY created_at DESC"
        select_cols = "products.*"

    params["p_limit"] = p.limit
    params["p_offset"] = p.offset

    items_sql = (
        f"SELECT {select_cols} FROM products WHERE {where_sql} "
        f"{order_by} LIMIT :p_limit OFFSET :p_offset"
    )
    rows = (await session.execute(text(items_sql), params)).mappings().all()
    items = [_row_to_product(row) for row in rows]
    return total, items


def _row_to_product(row) -> Product:
    """Hydrate a Product ORM object from a RowMapping (raw SQL result)."""
    return Product(
        id=row["id"] if isinstance(row["id"], uuid.UUID) else uuid.UUID(str(row["id"])),
        retailer=row["retailer"],
        retailer_product_id=row["retailer_product_id"],
        url=row["url"],
        title=row["title"],
        brand=row["brand"],
        category=row["category"],
        gender=row["gender"],
        description=row["description"],
        price=row["price"],
        currency=row["currency"],
        original_price=row["original_price"],
        fx_rate_used=row["fx_rate_used"],
        price_usd=row["price_usd"],
        image_url=row["image_url"],
        colors=row["colors"],
        sizes=row["sizes"],
        attributes=row["attributes"],
        in_stock=row["in_stock"],
        scraped_at=row["scraped_at"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


# In-process facets cache, invalidated by meta.taxonomy_version.
_facets_cache: dict = {"version": None, "data": None}


async def get_taxonomy_version(session: AsyncSession) -> int:
    return (await session.execute(select(Meta.taxonomy_version))).scalar_one()


async def _compute_facets(session: AsyncSession) -> dict:
    cat_rows = (
        await session.execute(
            select(Product.category, func.count(Product.id))
            .where(Product.category.is_not(None))
            .group_by(Product.category)
            .order_by(func.count(Product.id).desc())
        )
    ).all()
    brand_rows = (
        await session.execute(
            select(Product.brand, func.count(Product.id))
            .where(Product.brand.is_not(None))
            .group_by(Product.brand)
            .order_by(func.count(Product.id).desc())
        )
    ).all()
    # Colors come from the text[] array column — unnest, count, sort.
    color_rows = (
        await session.execute(
            text(
                "SELECT c, COUNT(*) FROM products, "
                "unnest(coalesce(colors, ARRAY[]::text[])) AS c "
                "GROUP BY c ORDER BY COUNT(*) DESC"
            )
        )
    ).all()
    price_row = (
        await session.execute(select(func.min(Product.price_usd), func.max(Product.price_usd)))
    ).one()
    return {
        "categories": [{"value": v, "count": c} for v, c in cat_rows],
        "brands": [{"value": v, "count": c} for v, c in brand_rows],
        "colors": [{"value": v, "count": c} for v, c in color_rows],
        "price": {"min": price_row[0], "max": price_row[1]},
        "features": list(get_features_vocabulary()),
        "fx_date": snapshot_date(),
    }


async def get_facets(session: AsyncSession) -> dict:
    """Cached facets, invalidated on taxonomy_version bump."""
    current = await get_taxonomy_version(session)
    if _facets_cache["version"] != current:
        _facets_cache["data"] = await _compute_facets(session)
        _facets_cache["version"] = current
    return _facets_cache["data"]


def apply_display_currency(items: list[Product], currency: str | None) -> list[dict]:
    """Compute `display_price = price_usd * rate(currency)` per item when
    the client asked for a display currency. Returns dicts ready to feed
    ProductOut.model_validate.
    """
    from clothist_api.services.fx import UnknownCurrencyError, rate_for

    if not currency:
        return [_orm_to_dict(p) for p in items]
    try:
        rate = rate_for(currency.upper())
    except UnknownCurrencyError:
        return [_orm_to_dict(p) for p in items]
    out: list[dict] = []
    for p in items:
        row = _orm_to_dict(p)
        if p.price_usd is not None:
            row["display_price"] = (Decimal(p.price_usd) * rate).quantize(Decimal("0.01"))
        out.append(row)
    return out


def _orm_to_dict(p: Product) -> dict:
    return {
        "id": p.id,
        "retailer": p.retailer,
        "retailer_product_id": p.retailer_product_id,
        "url": p.url,
        "title": p.title,
        "brand": p.brand,
        "category": p.category,
        "gender": p.gender,
        "description": p.description,
        "price": p.price,
        "currency": p.currency,
        "original_price": p.original_price,
        "price_usd": p.price_usd,
        "image_url": p.image_url,
        "colors": p.colors,
        "sizes": p.sizes,
        "attributes": p.attributes,
        "in_stock": p.in_stock,
    }
