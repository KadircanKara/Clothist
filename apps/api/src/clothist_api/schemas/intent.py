"""Structured output for AI query parsing.

We deliberately keep this small: only fields the search endpoint already
understands, plus an `explanation` for the UI. The LLM picks valid category /
brand values from a taxonomy list we inject into the prompt; anything outside
the list is dropped during validation.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ParsedIntent(BaseModel):
    """What the LLM extracts from a free-text query."""

    model_config = ConfigDict(extra="ignore")

    category: str | None = None
    brand: str | None = None
    color: str | None = None
    min_price: float | None = Field(default=None, ge=0)
    max_price: float | None = Field(default=None, ge=0)
    in_stock_only: bool = False
    refined_query: str | None = None
    explanation: str = ""

    @field_validator("category", "brand", "color", "refined_query", mode="before")
    @classmethod
    def _blank_to_none(cls, v):
        if isinstance(v, str) and not v.strip():
            return None
        return v


class IntentRequest(BaseModel):
    q: str = Field(min_length=1, max_length=400)


class IntentResponse(BaseModel):
    raw_query: str
    parsed: ParsedIntent
    model: str
    duration_ms: int
