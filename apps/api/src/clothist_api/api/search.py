from __future__ import annotations

import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from clothist_api.db.session import get_session
from clothist_api.rate_limit import limiter
from clothist_api.schemas import (
    FacetsResponse,
    IntentRequest,
    IntentResponse,
    ProductOut,
    SearchResponse,
)
from clothist_api.services.intent import parse_intent_cached
from clothist_api.services.search import (
    SearchFilters,
    SearchPaging,
    apply_display_currency,
    get_facets,
    get_taxonomy_version,
    search_products,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# `currency` is presentation-only. min_price and max_price are always
# interpreted in the currency detected by the pre-parser (default USD) and
# compared against the canonical price_usd column.
@router.get("", response_model=SearchResponse)
async def search(
    q: str | None = Query(default=None, max_length=200, description="Free-text query"),
    category: str | None = None,
    brand: str | None = None,
    color: str | None = Query(default=None, max_length=32),
    min_price: Decimal | None = Query(default=None, ge=0),
    max_price: Decimal | None = Query(default=None, ge=0),
    in_stock_only: bool = False,
    features: list[str] = Query(default_factory=list),
    excluded_features: list[str] = Query(default_factory=list),
    sort: str = Query(
        default="relevance",
        pattern="^(?:relevance|price_asc|price_desc|newest|highest_rated)$",
    ),
    currency: str | None = Query(default=None, min_length=3, max_length=3),
    limit: int = Query(default=24, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=1000),
    session: AsyncSession = Depends(get_session),
) -> SearchResponse:
    if min_price is not None and max_price is not None and min_price > max_price:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="min_price must be <= max_price",
        )

    filters = SearchFilters(
        q=q,
        category=category,
        brand=brand,
        color=color,
        min_price=min_price,
        max_price=max_price,
        in_stock_only=in_stock_only,
        features=list(features),
        excluded_features=list(excluded_features),
    )
    paging = SearchPaging(limit=limit, offset=offset, sort=sort)  # type: ignore[arg-type]
    total, items = await search_products(session, filters, paging)
    rows = apply_display_currency(items, currency)
    return SearchResponse(
        query=q,
        total=total,
        limit=limit,
        offset=offset,
        items=[ProductOut.model_validate(row) for row in rows],
    )


@router.get("/facets", response_model=FacetsResponse)
async def facets(session: AsyncSession = Depends(get_session)) -> FacetsResponse:
    raw = await get_facets(session)
    return FacetsResponse.model_validate(raw)


@router.post("/intent", response_model=IntentResponse)
@limiter.limit("10/minute")
async def intent(
    request: Request,
    body: IntentRequest,
    session: AsyncSession = Depends(get_session),
) -> IntentResponse:
    """LLM-parse a free-text query into structured filters.

    Returns 200 always. When `LLM_API_KEY` is unset or the upstream LLM
    fails (rate limit / timeout / 5xx), the response carries `degraded=true`
    and a pre-pass-only `ParsedIntent` so the frontend can still apply
    price / currency / sort / negation hints from the deterministic regex.
    """
    raw = await get_facets(session)
    categories = [c["value"] for c in raw["categories"]]
    brands = [b["value"] for b in raw["brands"]]
    taxonomy_version = await get_taxonomy_version(session)

    return await parse_intent_cached(
        body.q,
        categories=categories,
        brands=brands,
        taxonomy_version=taxonomy_version,
    )
