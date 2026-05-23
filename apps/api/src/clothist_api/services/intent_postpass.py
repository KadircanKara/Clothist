"""Post-pass: merge pre-pass + LLM output into the canonical ParsedIntent.

Drops taxonomy/feature values the LLM hallucinated outside the locked lists,
applies the synonyms map (English layer always; Turkish layered when locale
flagged Turkish), maps pre-pass negation tokens to canonical excluded
features, and stitches together the final response payload.

Spec: plans/senior_dev_v3.md §2a, §2c.
"""
from __future__ import annotations

import logging
from decimal import Decimal

from clothist_api.schemas.intent import ParsedIntent, SortKey
from clothist_api.services.features_vocab import get_features_set, get_synonyms
from clothist_api.services.intent_preparse import PrePassResult

logger = logging.getLogger(__name__)

# Negation-context aliases. When a user says "no logo" they almost certainly
# want to exclude products tagged `embroidered_logo` rather than the
# negative-positive "logo_free" tag. Anything not in this map AND not
# already a vocab token is dropped.
_NEGATION_FEATURE_ALIASES: dict[str, str] = {
    "logo": "embroidered_logo",
    "logos": "embroidered_logo",
    "branding": "embroidered_logo",
    "rip": "ripped",
    "rips": "ripped",
}


def _resolve_taxonomy(value: str | None, taxonomy: set[str]) -> str | None:
    if not value:
        return None
    if value in taxonomy:
        return value
    for t in taxonomy:
        if t.lower() == value.lower():
            return t
    return None


def _expand_synonyms_for_category(
    raw: str | None,
    synonyms_en: dict[str, str],
    synonyms_locale: dict[str, str] | None,
    taxonomy: set[str],
) -> str | None:
    if not raw:
        return None
    candidate = raw.strip().lower()
    # Locale layer wins on tied keys.
    if synonyms_locale and candidate in synonyms_locale:
        candidate = synonyms_locale[candidate]
    elif candidate in synonyms_en:
        candidate = synonyms_en[candidate]
    return _resolve_taxonomy(candidate, taxonomy)


def _tokenize_refined(text: str, synonyms_en: dict[str, str], synonyms_locale: dict[str, str] | None) -> str:
    """Apply token-level synonyms to refined_query."""
    if not text:
        return ""
    parts = text.split()
    out: list[str] = []
    for p in parts:
        key = p.lower().strip(",.;:!?")
        if synonyms_locale and key in synonyms_locale:
            out.append(synonyms_locale[key])
        elif key in synonyms_en:
            out.append(synonyms_en[key])
        else:
            out.append(p)
    return " ".join(out)


def _filter_features(values: list[str] | None) -> list[str]:
    if not values:
        return []
    vocab = get_features_set()
    seen: set[str] = set()
    out: list[str] = []
    for raw in values:
        token = raw.strip().lower().replace(" ", "_").replace("-", "_")
        if token in vocab and token not in seen:
            out.append(token)
            seen.add(token)
        else:
            logger.info("features_vocab_miss token=%r", raw)
    return out


def _map_negation_tokens(tokens: list[str]) -> list[str]:
    if not tokens:
        return []
    vocab = get_features_set()
    seen: set[str] = set()
    out: list[str] = []
    for raw in tokens:
        key = raw.lower().strip()
        token = key.replace(" ", "_").replace("-", "_")
        canonical: str | None = None
        if token in vocab:
            canonical = token
        elif key in _NEGATION_FEATURE_ALIASES:
            canonical = _NEGATION_FEATURE_ALIASES[key]
        if canonical and canonical not in seen:
            out.append(canonical)
            seen.add(canonical)
    return out


def merge(
    pre: PrePassResult,
    llm: dict | None,
    *,
    categories: list[str],
    brands: list[str],
) -> ParsedIntent:
    """Combine the deterministic pre-pass with the LLM output (or None on
    LLM-down) into a canonical ParsedIntent.
    """
    llm_raw = llm or {}
    synonyms = get_synonyms()
    syn_en = synonyms.get("en", {})
    syn_locale = synonyms.get(pre.locale) if pre.locale != "en" else None
    cat_set = set(categories)
    brand_set = set(brands)

    raw_category = llm_raw.get("category")
    category = _expand_synonyms_for_category(raw_category, syn_en, syn_locale, cat_set)
    if raw_category and category is None:
        logger.info("dropped hallucinated category=%r", raw_category)

    raw_brand = llm_raw.get("brand")
    brand = _resolve_taxonomy(raw_brand, brand_set)
    if raw_brand and brand is None:
        logger.info("dropped hallucinated brand=%r", raw_brand)

    color = llm_raw.get("color")
    if isinstance(color, str):
        color = color.strip().lower() or None
    else:
        color = None

    refined = llm_raw.get("refined_query")
    if isinstance(refined, str):
        refined = _tokenize_refined(refined.strip(), syn_en, syn_locale) or None
    else:
        refined = None

    features = _filter_features(llm_raw.get("features"))
    excluded_features = _filter_features(llm_raw.get("excluded_features"))
    for token in _map_negation_tokens(pre.negation_tokens):
        if token not in excluded_features:
            excluded_features.append(token)
    # If a token ended up in both lists, the user's intent is contradictory —
    # trust the negation (post-pass derived from explicit "no X").
    features = [f for f in features if f not in excluded_features]

    explanation = ""
    raw_expl = llm_raw.get("explanation")
    if isinstance(raw_expl, str):
        explanation = raw_expl.strip()[:200]

    in_stock_only = bool(llm_raw.get("in_stock_only"))

    # Sort: pre-pass wins if set (explicit intent like "cheapest"); else
    # accept the LLM's sort hint if it's a known key; else default.
    sort: SortKey = pre.sort if pre.sort else "relevance"
    llm_sort = llm_raw.get("sort")
    if pre.sort is None and isinstance(llm_sort, str):
        if llm_sort in ("relevance", "price_asc", "price_desc", "newest", "highest_rated"):
            if llm_sort == "highest_rated":
                sort = "relevance"
            else:
                sort = llm_sort  # type: ignore[assignment]

    # Pre-pass price is authoritative — it ran a deterministic regex.
    min_price = float(pre.min_price_usd) if pre.min_price_usd is not None else None
    max_price = float(pre.max_price_usd) if pre.max_price_usd is not None else None

    detected_amount = (
        Decimal(pre.detected_amount_native) if pre.detected_amount_native is not None else None
    )

    return ParsedIntent(
        category=category,
        brand=brand,
        color=color,
        min_price=min_price,
        max_price=max_price,
        in_stock_only=in_stock_only,
        refined_query=refined,
        explanation=explanation,
        features=features,
        excluded_features=excluded_features,
        sort=sort,
        detected_currency=pre.detected_currency,
        detected_amount_native=detected_amount,
        ambiguity_hint=pre.ambiguity_hint,
        locale=pre.locale,
    )
