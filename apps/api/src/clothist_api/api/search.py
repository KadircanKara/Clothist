from __future__ import annotations

import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from clothist_api.db.session import get_session
from clothist_api.schemas import (
    FacetsResponse,
    IntentRequest,
    IntentResponse,
    ProductOut,
    SearchResponse,
)
from clothist_api.services.intent import (
    LLMDisabledError,
    LLMUpstreamError,
    parse_intent,
)
from clothist_api.services.search import (
    SearchFilters,
    SearchPaging,
    get_facets,
    search_products,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=SearchResponse)
async def search(
    q: str | None = Query(default=None, max_length=200, description="Free-text query"),
    category: str | None = None,
    brand: str | None = None,
    color: str | None = Query(default=None, max_length=32),
    min_price: Decimal | None = Query(default=None, ge=0),
    max_price: Decimal | None = Query(default=None, ge=0),
    in_stock_only: bool = False,
    limit: int = Query(default=24, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> SearchResponse:
    filters = SearchFilters(
        q=q,
        category=category,
        brand=brand,
        color=color,
        min_price=min_price,
        max_price=max_price,
        in_stock_only=in_stock_only,
    )
    paging = SearchPaging(limit=limit, offset=offset)
    total, items = await search_products(session, filters, paging)
    return SearchResponse(
        query=q,
        total=total,
        limit=limit,
        offset=offset,
        items=[ProductOut.model_validate(item) for item in items],
    )


@router.get("/facets", response_model=FacetsResponse)
async def facets(session: AsyncSession = Depends(get_session)) -> FacetsResponse:
    raw = await get_facets(session)
    return FacetsResponse.model_validate(raw)


@router.post("/intent", response_model=IntentResponse)
async def intent(
    body: IntentRequest,
    session: AsyncSession = Depends(get_session),
) -> IntentResponse:
    """LLM-parse a free-text query into structured filters.

    Returns 503 if XAI_API_KEY isn't configured — the frontend should fall
    back to plain keyword search in that case.
    """
    raw = await get_facets(session)
    categories = [c["value"] for c in raw["categories"]]
    brands = [b["value"] for b in raw["brands"]]

    try:
        return await parse_intent(body.q, categories=categories, brands=brands)
    except LLMDisabledError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        ) from e
    except LLMUpstreamError as e:
        logger.warning("LLM upstream error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM upstream error: {e}",
        ) from e
