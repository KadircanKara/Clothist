"""LLM-driven query intent extractor (3-step chain).

  raw_query
    → intent_preparse.run()         pure Python, ~1ms
    → LLM call (Groq / OpenAI-compatible)
    → intent_postpass.merge()       pure Python, ~1ms

Provider-agnostic via OpenAI SDK. Provider swap is env-vars only — see
`settings.py`. On LLM down (429 / timeout / 5xx / disabled), returns a 200
with `degraded=true` and a pre-pass-only ParsedIntent so the frontend still
gets price/currency filters from the deterministic regex.

Spec: plans/senior_dev_v3.md §3.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from hashlib import sha256
from typing import Any

from cachetools import TTLCache
from openai import APIError, APITimeoutError, AsyncOpenAI, RateLimitError

from clothist_api.schemas.intent import (
    DegradedReason,
    IntentResponse,
    ParsedIntent,
)
from clothist_api.services import intent_postpass, intent_preparse
from clothist_api.services.features_vocab import get_features_vocabulary
from clothist_api.settings import get_settings

logger = logging.getLogger(__name__)


class LLMDisabledError(RuntimeError):
    """Raised when LLM_API_KEY is not configured."""


class LLMUpstreamError(RuntimeError):
    """Raised on a transport / provider error from the LLM upstream."""


SYSTEM_PROMPT_TEMPLATE = """\
You are a fashion search query interpreter for Clothist, a multi-retailer
fashion meta-search. Convert each user query into structured filters.

Currency tokens (e.g. "$100", "€80", "4300₺") and "under/over/between" price
phrases have ALREADY been extracted from the query by a deterministic
pre-parser. Do NOT re-emit min_price or max_price; the system handles those.

# Available taxonomy

Categories (pick AT MOST ONE, only if it clearly matches):
{categories}

Brands (pick AT MOST ONE, only if mentioned by name):
{brands}

Features (this is the LOCKED vocabulary; pick zero or more):
{features}

# Output

Respond with a single JSON object matching this exact schema. Any key may be
null/omitted if the query doesn't imply it. Do NOT invent values that aren't
in the lists above.

{{
  "category": string | null,
  "brand": string | null,
  "color": string | null,
  "in_stock_only": boolean,
  "features": string[],
  "excluded_features": string[],
  "refined_query": string | null,
  "sort": "relevance" | "price_asc" | "price_desc" | "newest" | null,
  "explanation": string
}}

# Rules

- `features` and `excluded_features` MUST come from the features list above.
  Drop anything you can't fit; don't invent new tokens.
- `refined_query` is reserved for style/vibe tokens with no structured home
  (minimalist, streetwear, vintage). Keep it 1-4 words. Do NOT include
  features, materials, currencies, or color words there.
- If the query is a bare brand name, set brand and leave refined_query null.
- If you cannot match a category, leave it null — do NOT force a match.
- `in_stock_only` defaults to false; set true only if the user explicitly
  asked ("in stock", "available now").
- `explanation` is ONE short sentence, present tense, max 80 chars.

# Examples

Query: "cargo pants with hidden pockets"
Output: {{"category":"pants","brand":null,"color":null,"in_stock_only":false,"features":["cargo_pockets","hidden_pockets"],"excluded_features":[],"refined_query":null,"sort":null,"explanation":"Cargo pants with hidden pockets"}}

Query: "minimalist hoodie"
Output: {{"category":"hoodie","brand":null,"color":null,"in_stock_only":false,"features":[],"excluded_features":[],"refined_query":"minimalist","sort":null,"explanation":"Minimalist hoodies"}}

Query: "nike running shoes available now"
Output: {{"category":"sneakers","brand":"Nike","color":null,"in_stock_only":true,"features":[],"excluded_features":[],"refined_query":"running","sort":null,"explanation":"Nike sneakers for running, in stock"}}

Query: "no logo hoodie"
Output: {{"category":"hoodie","brand":null,"color":null,"in_stock_only":false,"features":["logo_free"],"excluded_features":["embroidered_logo"],"refined_query":null,"sort":null,"explanation":"Logo-free hoodies"}}

Query: "waterproof jacket"
Output: {{"category":"jackets","brand":null,"color":null,"in_stock_only":false,"features":["waterproof"],"excluded_features":[],"refined_query":null,"sort":null,"explanation":"Waterproof jackets"}}
"""


def _build_system_prompt(categories: list[str], brands: list[str], features: list[str]) -> str:
    cats = "\n".join(f"  - {c}" for c in categories) or "  (none yet)"
    brs = "\n".join(f"  - {b}" for b in brands) or "  (none yet)"
    feats = "\n".join(f"  - {f}" for f in features) or "  (none yet)"
    return SYSTEM_PROMPT_TEMPLATE.format(categories=cats, brands=brs, features=feats)


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


def _tolerant_json(content: str) -> dict[str, Any]:
    """Try strict JSON first; on failure, extract the first {...} block.

    Note: this is NOT a retry — no second API call is made.
    """
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", content, re.DOTALL)
        if not m:
            raise
        return json.loads(m.group(0))


def _redact(q: str) -> str:
    if get_settings().log_redact_queries:
        return f"sha256:{sha256(q.encode('utf-8')).hexdigest()[:16]}"
    return q


def _degraded_response(
    *,
    q: str,
    pre,
    categories: list[str],
    brands: list[str],
    reason: DegradedReason,
    duration_ms: int,
) -> IntentResponse:
    parsed = intent_postpass.merge(pre, None, categories=categories, brands=brands)
    if not parsed.refined_query:
        parsed.refined_query = q.strip() or None
    logger.info(
        "intent_degraded q=%s reason=%s locale=%s",
        _redact(q),
        reason,
        parsed.locale,
    )
    return IntentResponse(
        raw_query=q,
        parsed=parsed,
        model=get_settings().llm_model,
        duration_ms=duration_ms,
        degraded=True,
        degraded_reason=reason,
        ui_hints=parsed.locale and pre.ui_hints or pre.ui_hints,
    )


async def parse_intent(
    q: str,
    *,
    categories: list[str],
    brands: list[str],
) -> IntentResponse:
    """Run the full chain: pre-pass → LLM → post-pass. On LLM error returns a
    200-style payload with `degraded=true` (caller maps to FastAPI's 200).
    """
    started = time.perf_counter()

    # 1. Pre-pass (deterministic).
    pre_start = time.perf_counter()
    pre = intent_preparse.run(q)
    duration_pre_ms = int((time.perf_counter() - pre_start) * 1000)

    settings = get_settings()

    if not settings.llm_api_key:
        total_ms = int((time.perf_counter() - started) * 1000)
        return _degraded_response(
            q=q, pre=pre, categories=categories, brands=brands,
            reason="llm_disabled", duration_ms=total_ms,
        )

    features_vocab = get_features_vocabulary()
    system_prompt = _build_system_prompt(categories, brands, features_vocab)
    user_input = pre.stripped_query or q

    # 2. LLM call.
    llm_start = time.perf_counter()
    try:
        client = _client()
        completion = await client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=300,
        )
        content = (completion.choices[0].message.content or "").strip()
        try:
            llm_raw = _tolerant_json(content)
        except json.JSONDecodeError:
            llm_raw = None
            logger.warning("intent_llm_unparseable content=%r", content[:200])
    except RateLimitError:
        total_ms = int((time.perf_counter() - started) * 1000)
        return _degraded_response(
            q=q, pre=pre, categories=categories, brands=brands,
            reason="llm_rate_limited", duration_ms=total_ms,
        )
    except APITimeoutError:
        total_ms = int((time.perf_counter() - started) * 1000)
        return _degraded_response(
            q=q, pre=pre, categories=categories, brands=brands,
            reason="llm_timeout", duration_ms=total_ms,
        )
    except APIError:
        total_ms = int((time.perf_counter() - started) * 1000)
        return _degraded_response(
            q=q, pre=pre, categories=categories, brands=brands,
            reason="llm_5xx", duration_ms=total_ms,
        )
    duration_llm_ms = int((time.perf_counter() - llm_start) * 1000)

    # 3. Post-pass.
    post_start = time.perf_counter()
    parsed = intent_postpass.merge(pre, llm_raw, categories=categories, brands=brands)
    duration_post_ms = int((time.perf_counter() - post_start) * 1000)

    total_ms = int((time.perf_counter() - started) * 1000)
    logger.info(
        "intent q=%s locale=%s model=%s pre_ms=%d llm_ms=%d post_ms=%d total_ms=%d",
        _redact(q),
        parsed.locale,
        settings.llm_model,
        duration_pre_ms,
        duration_llm_ms,
        duration_post_ms,
        total_ms,
    )
    return IntentResponse(
        raw_query=q,
        parsed=parsed,
        model=settings.llm_model,
        duration_ms=total_ms,
        degraded=False,
        ui_hints=pre.ui_hints,
    )


# -----------------------------------------------------------------------------
# Caching layer (TTLCache + per-key singleflight).
# -----------------------------------------------------------------------------

_intent_cache: TTLCache[tuple[str, int], IntentResponse] = TTLCache(maxsize=512, ttl=300)
_intent_inflight: dict[tuple[str, int], asyncio.Future[IntentResponse]] = {}


def _cache_key(q: str, taxonomy_version: int) -> tuple[str, int]:
    return (" ".join(q.lower().split()), taxonomy_version)


async def parse_intent_cached(
    q: str,
    *,
    categories: list[str],
    brands: list[str],
    taxonomy_version: int,
) -> IntentResponse:
    """Async-safe cached wrapper. Returns the cached IntentResponse for an
    identical (normalized query, taxonomy version) pair within 5 minutes.
    Concurrent misses for the same key share one upstream call.
    """
    key = _cache_key(q, taxonomy_version)
    cached = _intent_cache.get(key)
    if cached is not None:
        return cached

    inflight = _intent_inflight.get(key)
    if inflight is not None:
        return await inflight

    loop = asyncio.get_running_loop()
    fut: asyncio.Future[IntentResponse] = loop.create_future()
    _intent_inflight[key] = fut
    try:
        result = await parse_intent(q, categories=categories, brands=brands)
        # Only cache non-degraded responses; degraded payloads should be retried
        # quickly when the upstream comes back, not pinned for 5 minutes.
        if not result.degraded:
            _intent_cache[key] = result
        fut.set_result(result)
        return result
    except BaseException as e:
        if not fut.done():
            fut.set_exception(e)
        raise
    finally:
        _intent_inflight.pop(key, None)
