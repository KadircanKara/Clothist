"""LLM-based query parser.

Converts free-text input like "black cargo pants under $100" into structured
filters that the existing /search endpoint understands.

Provider-agnostic: uses any OpenAI-compatible API. Default is Google Gemini
(2.0/2.5 Flash) — generous free tier and reliable JSON mode. Switch providers
by changing LLM_BASE_URL + LLM_MODEL in .env; the prompt + parsing stay the
same. See settings.py for config.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any

from openai import APIError, APITimeoutError, AsyncOpenAI

from clothist_api.schemas.intent import IntentResponse, ParsedIntent
from clothist_api.settings import get_settings

logger = logging.getLogger(__name__)


class LLMDisabledError(RuntimeError):
    """Raised when LLM_API_KEY is not configured."""


class LLMUpstreamError(RuntimeError):
    """Raised on a transport / provider error from the LLM upstream."""


SYSTEM_PROMPT_TEMPLATE = """\
You are a fashion search query interpreter for Clothist, a multi-retailer
fashion meta-search. Convert each user query into structured filters.

# Available taxonomy

Categories (pick AT MOST ONE, only if it clearly matches):
{categories}

Brands (pick AT MOST ONE, only if mentioned by name):
{brands}

# Output

Respond with a single JSON object matching this exact schema. Any key may be
null/omitted if the query doesn't imply it. Do NOT invent values that aren't
in the lists above.

{{
  "category": string | null,        // must be one of the listed categories or null
  "brand": string | null,           // must be one of the listed brands or null
  "color": string | null,           // a single color word, lowercase, e.g. "black"
  "min_price": number | null,       // dollar amount, no currency symbol
  "max_price": number | null,       // dollar amount, no currency symbol
  "in_stock_only": boolean,         // default false; true if user explicitly asked
  "refined_query": string | null,   // remaining descriptive keywords for full-text search (style, fit, fabric, features). EXCLUDE words already captured in category/brand/color/price.
  "explanation": string             // ONE short sentence in present tense describing your interpretation, max 80 chars
}}

# Rules

- "under $X" / "less than $X" / "below $X" → max_price = X
- "over $X" / "more than $X" / "above $X" / "at least $X" → min_price = X
- "between $X and $Y" → min_price = X, max_price = Y
- "in stock" / "available now" → in_stock_only = true
- If the query is a bare brand name ("nike"), set brand and leave refined_query null.
- If you cannot match a category, leave it null — do NOT force a match.
- refined_query should be 1–4 words, kept terse; it powers a Postgres FTS query.

# Examples

Query: "black cargo pants with hidden pockets under $100"
Output: {{"category":"pants","brand":null,"color":"black","min_price":null,"max_price":100,"in_stock_only":false,"refined_query":"cargo hidden pockets","explanation":"Black pants under $100 with cargo style and hidden pockets"}}

Query: "minimalist hoodie"
Output: {{"category":"hoodies","brand":null,"color":null,"min_price":null,"max_price":null,"in_stock_only":false,"refined_query":"minimalist","explanation":"Minimalist hoodies"}}

Query: "nike running shoes available now"
Output: {{"category":"sneakers","brand":"Nike","color":null,"min_price":null,"max_price":null,"in_stock_only":true,"refined_query":"running","explanation":"Nike sneakers for running, in stock"}}

Query: "waterproof jacket reviewers say lasts forever"
Output: {{"category":"jackets","brand":null,"color":null,"min_price":null,"max_price":null,"in_stock_only":false,"refined_query":"waterproof durable","explanation":"Durable waterproof jackets"}}
"""


def _build_system_prompt(categories: list[str], brands: list[str]) -> str:
    cats = "\n".join(f"  - {c}" for c in categories) or "  (none yet)"
    brs = "\n".join(f"  - {b}" for b in brands) or "  (none yet)"
    return SYSTEM_PROMPT_TEMPLATE.format(categories=cats, brands=brs)


def _client() -> AsyncOpenAI:
    settings = get_settings()
    if not settings.llm_api_key:
        raise LLMDisabledError(
            "LLM_API_KEY is not set. Set it in .env to enable /search/intent."
        )
    return AsyncOpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        timeout=settings.llm_timeout_seconds,
    )


def _validate_against_taxonomy(
    parsed: ParsedIntent,
    categories: set[str],
    brands: set[str],
) -> ParsedIntent:
    """Drop category/brand values the LLM hallucinated outside the taxonomy."""
    if parsed.category and parsed.category not in categories:
        logger.info("Dropping hallucinated category: %r", parsed.category)
        parsed.category = None
    if parsed.brand and parsed.brand not in brands:
        # Case-insensitive recovery — LLM sometimes lowercases the brand.
        for b in brands:
            if b.lower() == parsed.brand.lower():
                parsed.brand = b
                break
        else:
            logger.info("Dropping hallucinated brand: %r", parsed.brand)
            parsed.brand = None
    return parsed


async def parse_intent(
    q: str,
    *,
    categories: list[str],
    brands: list[str],
) -> IntentResponse:
    """Call Grok to parse a free-text query. Raises LLMDisabledError if no key."""
    settings = get_settings()
    client = _client()

    system_prompt = _build_system_prompt(categories, brands)
    started = time.perf_counter()

    try:
        completion = await client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": q},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=300,
        )
    except APITimeoutError as e:
        raise LLMUpstreamError(f"LLM timed out: {e}") from e
    except APIError as e:
        raise LLMUpstreamError(f"LLM error: {e}") from e

    duration_ms = int((time.perf_counter() - started) * 1000)

    content = (completion.choices[0].message.content or "").strip()
    try:
        raw: dict[str, Any] = json.loads(content)
    except json.JSONDecodeError as e:
        raise LLMUpstreamError(f"LLM returned non-JSON: {content!r}") from e

    parsed = ParsedIntent.model_validate(raw)
    parsed = _validate_against_taxonomy(parsed, set(categories), set(brands))

    return IntentResponse(
        raw_query=q,
        parsed=parsed,
        model=settings.llm_model,
        duration_ms=duration_ms,
    )
