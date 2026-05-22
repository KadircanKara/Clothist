from __future__ import annotations

import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    retailer: str
    retailer_product_id: str
    url: str
    title: str
    brand: str | None = None
    category: str | None = None
    description: str | None = None
    price: Decimal | None = None
    currency: str | None = None
    original_price: Decimal | None = None
    image_url: str | None = None
    colors: list[str] | None = None
    sizes: list[str] | None = None
    attributes: dict | None = None
    in_stock: bool = True


class SearchResponse(BaseModel):
    query: str | None = None
    total: int
    limit: int
    offset: int
    items: list[ProductOut] = Field(default_factory=list)


class FacetValue(BaseModel):
    value: str
    count: int


class PriceRange(BaseModel):
    min: Decimal | None = None
    max: Decimal | None = None


class FacetsResponse(BaseModel):
    categories: list[FacetValue]
    brands: list[FacetValue]
    price: PriceRange
