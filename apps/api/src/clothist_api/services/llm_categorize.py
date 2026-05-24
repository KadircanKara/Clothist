"""LLM-based product categorization by title + brand (+ short description).

Companion to the CV image classifier. The hybrid pipeline votes between
three signals — text-alias (scrapers/normalize.py), this LLM, and CV
(cv/classifier.py) — to pick a final category per product.

Provider-agnostic via OpenAI SDK (Groq Llama 3.3 70B by default). The
client + auth model are shared with services/intent.py.

Batching: 10 products per call so the free-tier 30 RPM ceiling holds for
~500-product runs (50 calls ≈ 2 min). Returns None on any upstream error
so the caller can fall back to text+CV-only voting.

Spec: this is the §6 "Approach 1" arm of the user's hybrid plan.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass

from openai import APIError, APITimeoutError, AsyncOpenAI, RateLimitError

from clothist_api.settings import get_settings

logger = logging.getLogger(__name__)


CANONICAL_CATEGORIES = [
    "tshirts", "hoodies", "sweaters", "jackets", "pants", "jeans", "shorts",
    "skirts", "dresses", "sneakers", "accessories", "swimwear", "underwear",
]


SYSTEM_PROMPT = """\
You categorize fashion products into a fixed taxonomy. You will receive a JSON
array of up to 10 products. For each product return one of these categories or
null if no category is a clear fit:

  tshirts, hoodies, sweaters, jackets, pants, jeans, shorts, skirts, dresses,
  sneakers, accessories, swimwear, underwear

Rules
- "accessories" includes bags, hats, belts, jewelry, sunglasses, wallets,
  socks-as-accessory, gloves, scarves — anything non-garment.
- "sneakers" covers ALL footwear (athletic, casual, loafers, flats, heels,
  boots, slippers, mary janes). Do not split footwear across categories.
- "underwear" covers briefs, bras, lingerie, intimate socks (sport socks → accessories).
- "swimwear" covers bikinis, swimsuits, swim shorts, board shorts.
- A "polo" or "button-up shirt" is tshirts.
- A "cardigan" or "knit" is sweaters; a "blazer" or "coat" is jackets.
- Pick AT MOST ONE category. If genuinely ambiguous, return null.

Confidence
- Return a self-assessed confidence in [0, 1] for each product.
- 0.95 = the product name unambiguously names this category (e.g. "Cotton T-Shirt")
- 0.75 = strong signal (e.g. "Air Jordan 1" → sneakers via brand+model)
- 0.50 = weak signal, plausible but other categories possible
- < 0.30 = guessing — prefer returning null over a low-confidence label

Output format (STRICT): a JSON object with a single key "results" whose value
is an array of objects in the SAME ORDER as the input. Each object:
  {"i": <int index>, "category": <string|null>, "confidence": <float 0..1>}

Do not output any explanation, prose, or wrapper. JSON only.
"""


@dataclass(slots=True)
class LLMCategoryVerdict:
    """One categorization per product."""

    category: str | None
    confidence: float
    model_id: str


def _client() -> AsyncOpenAI | None:
    """Returns a configured OpenAI client, or None if LLM_API_KEY isn't set."""
    settings = get_settings()
    if not settings.llm_api_key:
        return None
    return AsyncOpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        timeout=settings.llm_timeout_seconds,
    )


def _format_product(idx: int, *, title: str, brand: str | None, description: str | None) -> dict:
    """Compact input row. Description is truncated to keep the batch prompt small."""
    out: dict = {"i": idx, "title": title}
    if brand:
        out["brand"] = brand
    if description:
        snippet = description.strip()
        if len(snippet) > 200:
            snippet = snippet[:200].rsplit(" ", 1)[0] + "…"
        out["description"] = snippet
    return out


def _tolerant_json(content: str) -> dict | None:
    """Parse the LLM response. Mirrors services/intent.py:_tolerant_json."""
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", content, re.DOTALL)
        if not m:
            return None
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return None


def _parse_results(raw: dict | None, batch_len: int, model_id: str) -> list[LLMCategoryVerdict]:
    """Normalize the LLM JSON into a fixed-length list of verdicts.

    Anything malformed → (None, 0.0) for that slot. We never raise here; the
    caller's vote function treats `category=None` as a missing signal.
    """
    empties = [LLMCategoryVerdict(None, 0.0, model_id) for _ in range(batch_len)]
    if not raw or "results" not in raw or not isinstance(raw["results"], list):
        return empties
    out = list(empties)
    valid = set(CANONICAL_CATEGORIES)
    for item in raw["results"]:
        if not isinstance(item, dict):
            continue
        idx = item.get("i")
        if not isinstance(idx, int) or not (0 <= idx < batch_len):
            continue
        cat = item.get("category")
        if isinstance(cat, str):
            cat = cat.strip().lower()
            if cat not in valid:
                cat = None
        elif cat is not None:
            cat = None
        conf = item.get("confidence")
        if isinstance(conf, (int, float)):
            conf = float(max(0.0, min(1.0, conf)))
        else:
            conf = 0.0
        out[idx] = LLMCategoryVerdict(cat, conf, model_id)
    return out


async def _categorize_one_batch(
    client: AsyncOpenAI, model_id: str, products: list[dict],
) -> list[LLMCategoryVerdict]:
    """Run one batch (≤10 products). Returns one LLMCategoryVerdict per product.

    On any upstream error (rate limit, timeout, 5xx, unparseable JSON), returns
    a list of empty verdicts — the vote function will simply skip the LLM
    signal for that batch.
    """
    try:
        completion = await client.chat.completions.create(
            model=model_id,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps({"products": products})},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=600,  # ~50 tokens per product × 10
        )
    except RateLimitError:
        logger.warning("llm_categorize_rate_limited batch_size=%d", len(products))
        return [LLMCategoryVerdict(None, 0.0, model_id) for _ in products]
    except APITimeoutError:
        logger.warning("llm_categorize_timeout batch_size=%d", len(products))
        return [LLMCategoryVerdict(None, 0.0, model_id) for _ in products]
    except APIError as e:
        logger.warning("llm_categorize_api_error batch_size=%d err=%s", len(products), e)
        return [LLMCategoryVerdict(None, 0.0, model_id) for _ in products]

    content = (completion.choices[0].message.content or "").strip()
    parsed = _tolerant_json(content)
    return _parse_results(parsed, len(products), model_id)


BATCH_SIZE_LLM = 10


async def categorize_batch(
    rows: list[dict], *, concurrency: int = 4,
) -> list[LLMCategoryVerdict]:
    """Categorize N products via the LLM. Caller passes a list of dicts with
    keys: `title` (required), `brand` (optional), `description` (optional).

    Returns one LLMCategoryVerdict per input row, in order. If LLM is disabled
    (no API key) returns all-empty verdicts.
    """
    client = _client()
    settings = get_settings()
    model_id = settings.llm_model
    if client is None:
        logger.info("llm_categorize_disabled — no LLM_API_KEY set")
        return [LLMCategoryVerdict(None, 0.0, model_id) for _ in rows]

    started = time.perf_counter()

    # Slice into 10-product micro-batches and run with bounded concurrency.
    batches: list[list[dict]] = []
    for i in range(0, len(rows), BATCH_SIZE_LLM):
        chunk = rows[i:i + BATCH_SIZE_LLM]
        batches.append([
            _format_product(
                idx=j,
                title=r["title"],
                brand=r.get("brand"),
                description=r.get("description"),
            )
            for j, r in enumerate(chunk)
        ])

    sem = asyncio.Semaphore(concurrency)

    async def _bounded(batch: list[dict]) -> list[LLMCategoryVerdict]:
        async with sem:
            return await _categorize_one_batch(client, model_id, batch)

    results = await asyncio.gather(*(_bounded(b) for b in batches))
    # Flatten.
    flat: list[LLMCategoryVerdict] = []
    for batch_result in results:
        flat.extend(batch_result)

    elapsed = time.perf_counter() - started
    hits = sum(1 for v in flat if v.category)
    logger.info(
        "llm_categorize_done n=%d hits=%d batches=%d elapsed=%.1fs model=%s",
        len(flat), hits, len(batches), elapsed, model_id,
    )
    return flat
