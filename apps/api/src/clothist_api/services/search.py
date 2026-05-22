"""Search service: Postgres full-text search with optional filters.

Query strategy:
  - Tokenize input on word boundaries (Python regex).
  - Build a `websearch_to_tsquery('english', "token1 OR token2 OR ...")` —
    OR semantics so users get loose matches even on noisy natural-language
    input.
  - Rank by `ts_rank_cd` so products matching more / higher-weighted tokens
    surface first.

This is intentionally simple keyword search. The CTO doc's "AI query
understanding" step (LLM → structured filters) layers on top of this and is
the planned next step.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from clothist_api.models import Product

_TOKEN_RE = re.compile(r"[\w']+", re.UNICODE)


def _to_search_expr(q: str) -> str | None:
    """Convert user input into a websearch_to_tsquery expression.

    Joins tokens with `OR` so any term can match; `ts_rank_cd` then orders
    products by how strongly they match.
    """
    tokens = _TOKEN_RE.findall(q.lower())
    # Drop single-char tokens; they explode the result set with noise.
    tokens = [t for t in tokens if len(t) > 1]
    if not tokens:
        return None
    return " OR ".join(tokens)


@dataclass(slots=True)
class SearchFilters:
    q: str | None = None
    category: str | None = None
    brand: str | None = None
    color: str | None = None
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    in_stock_only: bool = False


@dataclass(slots=True)
class SearchPaging:
    limit: int = 24
    offset: int = 0


def _apply_non_text_filters(stmt, f: SearchFilters):
    if f.category:
        stmt = stmt.where(Product.category == f.category)
    if f.brand:
        stmt = stmt.where(Product.brand == f.brand)
    if f.color:
        # Membership in the products.colors text[] array (@> operator).
        # Both sides are lowercased: seed data uses lowercase, prompt instructs
        # the LLM to emit lowercase, sidebar inputs are normalized below.
        stmt = stmt.where(Product.colors.contains([f.color.lower()]))
    if f.min_price is not None:
        stmt = stmt.where(Product.price >= f.min_price)
    if f.max_price is not None:
        stmt = stmt.where(Product.price <= f.max_price)
    if f.in_stock_only:
        stmt = stmt.where(Product.in_stock.is_(True))
    return stmt


async def search_products(
    session: AsyncSession,
    f: SearchFilters,
    p: SearchPaging,
) -> tuple[int, list[Product]]:
    search_expr = _to_search_expr(f.q) if f.q else None

    count_stmt = _apply_non_text_filters(select(func.count(Product.id)), f)
    if search_expr:
        ts_query = func.websearch_to_tsquery("english", search_expr)
        count_stmt = count_stmt.where(Product.search_vector.op("@@")(ts_query))
    total = (await session.execute(count_stmt)).scalar_one()

    stmt = _apply_non_text_filters(select(Product), f)
    if search_expr:
        ts_query = func.websearch_to_tsquery("english", search_expr)
        rank = func.ts_rank_cd(Product.search_vector, ts_query).label("rank")
        stmt = (
            stmt.where(Product.search_vector.op("@@")(ts_query))
            .add_columns(rank)
            .order_by(rank.desc(), Product.created_at.desc())
        )
        result = await session.execute(stmt.limit(p.limit).offset(p.offset))
        items = [row[0] for row in result.all()]
    else:
        stmt = stmt.order_by(Product.created_at.desc())
        result = await session.execute(stmt.limit(p.limit).offset(p.offset))
        items = list(result.scalars().all())

    return total, items


async def get_facets(session: AsyncSession) -> dict:
    """Return category/brand counts + price range across in-stock products."""
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
    price_row = (
        await session.execute(select(func.min(Product.price), func.max(Product.price)))
    ).one()

    return {
        "categories": [{"value": v, "count": c} for v, c in cat_rows],
        "brands": [{"value": v, "count": c} for v, c in brand_rows],
        "price": {"min": price_row[0], "max": price_row[1]},
    }
