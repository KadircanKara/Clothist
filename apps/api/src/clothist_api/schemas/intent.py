"""Structured output for AI query parsing.

The chain runs as: deterministic pre-pass → LLM call → post-pass (taxonomy +
synonyms + features-vocab filter). Each step produces a typed payload; the
final `IntentResponse` is what the frontend reads.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

SortKey = Literal["relevance", "price_asc", "price_desc", "newest", "highest_rated"]
DegradedReason = Literal["llm_rate_limited", "llm_timeout", "llm_5xx", "llm_disabled"]


class AmbiguityHint(BaseModel):
    """Emitted by the pre-parser when step 3 (currency convention) and step
    3.5 (single-separator override) disagree on a number. The frontend renders
    a one-click override nudge.
    """

    token: str
    parsed_as: str
    alternative: str


class ParsedIntent(BaseModel):
    """Canonical structured filters after pre-pass + LLM + post-pass."""

    model_config = ConfigDict(extra="ignore")

    category: str | None = None
    brand: str | None = None
    color: str | None = None
    min_price: float | None = Field(default=None, ge=0)
    max_price: float | None = Field(default=None, ge=0)
    in_stock_only: bool = False
    refined_query: str | None = None
    explanation: str = ""

    features: list[str] = Field(default_factory=list)
    excluded_features: list[str] = Field(default_factory=list)
    sort: SortKey = "relevance"

    # Pre-parser surface: lets the UI render "4300₺ ≈ $133 USD" instead of
    # just the converted USD value.
    detected_currency: str | None = None
    detected_amount_native: Decimal | None = None
    ambiguity_hint: AmbiguityHint | None = None
    locale: str = "en"

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

    # Graceful-degradation channel: when the LLM call fails, we return 200
    # with `degraded=true` and a pre-pass-only ParsedIntent so the frontend
    # can still apply price/currency filters and keyword-search the raw query.
    degraded: bool = False
    degraded_reason: DegradedReason | None = None

    # Free-form UI hints surfaced by the chain (e.g. "reviews coming soon").
    ui_hints: list[str] = Field(default_factory=list)
