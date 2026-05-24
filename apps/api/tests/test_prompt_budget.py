"""T4 — Prompt budget enforcement.

The intent system prompt (categories + brands + features) must fit inside
≤1750 tokens when rendered with the post-ingest top-20 brand list. Without
the top-K cap in `services/intent.py:_build_system_prompt`, Kith's
multi-vendor catalog (Nike, Adidas, NB, Asics, Wilson, in-house Kith, plus
30+ resold brands) blows past this budget.

Uses tiktoken's gpt-4 encoder as a token-count proxy — the actual Groq
Llama tokenizer is similar but not identical. ≤1750 leaves a ~15% slack
below the hard 2000-token Groq ceiling.
"""
from __future__ import annotations

import pytest

from clothist_api.scrapers.normalize import CANONICAL_CATEGORIES
from clothist_api.services.features_vocab import get_features_vocabulary
from clothist_api.services.intent import PROMPT_BRAND_TOP_K, _build_system_prompt


# A realistic post-ingest brand-list shape — heavy on streetwear/sportswear
# vendor names because Kith dominates cardinality.
SIMULATED_BRANDS = [
    "Nike", "Adidas", "New Balance", "Asics", "Wilson", "Allbirds",
    "Aimé Leon Dore", "Princess Polly", "Rothy's", "Kith",
    "Awake NY", "Reigning Champ", "Birkenstock", "Stüssy", "Lacoste",
    "Norda", "Salomon", "Tabio", "Sunspel", "Stone Island",
    # Long tail beyond top-20 — should be dropped by the cap.
    "Engineered Garments", "Beams Plus", "Comme des Garçons", "And Wander",
    "Visvim", "Marni", "Etudes Studio", "Norse Projects", "Nanamica",
    "Margaret Howell", "Wood Wood", "A.P.C.", "Officine Generale",
    "YMC", "Folk", "Universal Works",
]


def _count_tokens(text: str) -> int:
    import tiktoken

    enc = tiktoken.encoding_for_model("gpt-4")
    return len(enc.encode(text))


def test_top_k_cap_holds():
    assert PROMPT_BRAND_TOP_K == 20, (
        "Top-K cap drift will silently allow prompt budget overrun"
    )


def test_full_prompt_under_budget():
    categories = sorted(CANONICAL_CATEGORIES)
    features = list(get_features_vocabulary())
    prompt = _build_system_prompt(categories, SIMULATED_BRANDS, features)
    tokens = _count_tokens(prompt)
    # 1750 ceiling per plans/senior_dev_v3.md §6g and plans/scraping/senior_dev_v2.md §1a Test T4.
    assert tokens <= 1750, (
        f"Prompt is {tokens} tokens (cap=1750). "
        f"Brand list rendered {min(len(SIMULATED_BRANDS), PROMPT_BRAND_TOP_K)} brands."
    )


def test_capped_brand_list_appears_in_prompt():
    """The top-20 brands should literally appear in the prompt; brands
    beyond the cap (the "long tail") should NOT."""
    categories = sorted(CANONICAL_CATEGORIES)
    features = list(get_features_vocabulary())
    prompt = _build_system_prompt(categories, SIMULATED_BRANDS, features)
    # First 20 brands should be present.
    for brand in SIMULATED_BRANDS[:PROMPT_BRAND_TOP_K]:
        assert brand in prompt, f"Top-{PROMPT_BRAND_TOP_K} brand {brand!r} missing from prompt"
    # Brands beyond the cap should NOT be present.
    long_tail = SIMULATED_BRANDS[PROMPT_BRAND_TOP_K:]
    if long_tail:
        leaked = [b for b in long_tail if b in prompt]
        assert not leaked, f"Long-tail brand(s) leaked past the cap: {leaked}"
