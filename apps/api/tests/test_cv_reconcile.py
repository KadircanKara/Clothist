"""T2 — reconciliation unit tests.

Pure-Python; does NOT import torch/transformers/openai. Runs without
`--extra cv` and without an LLM_API_KEY.

Category: 3-way confidence-weighted vote between text-alias, LLM-by-name,
and CV-by-image.
Gender / colors: 2-way scraper-vs-CV (unchanged).
"""
from __future__ import annotations

import pytest

from clothist_api.cv.reconcile import (
    CV_MIN_QUALIFY,
    LLM_MIN_QUALIFY,
    TEXT_VOTE_WEIGHT,
    THRESHOLDS,
    LLMCatVote,
    ReconciledRow,
    reconcile,
)
from clothist_api.cv.types import CVVerdict


def _verdict(
    *,
    category: str | None = "tshirts",
    category_confidence: float = 0.9,
    gender: str | None = "unisex",
    gender_confidence: float = 0.9,
    colors: list[tuple[str, float]] | None = None,
) -> CVVerdict:
    return CVVerdict(
        category=category,
        category_confidence=category_confidence,
        category_runner_up=None,
        gender=gender,
        gender_confidence=gender_confidence,
        gender_runner_up=None,
        colors=colors or [],
        model_id="test",
        image_url="test://1",
        duration_ms=0,
    )


# ---------------- Category — 3-way vote ---------------- #


def test_cat_unanimous_all_three_agree():
    """All three sources name the same category → cat_unanimous."""
    d = reconcile(
        scraper_category="sneakers", scraper_gender=None, scraper_colors=None,
        verdict=_verdict(category="sneakers", category_confidence=0.7),
        llm_vote=LLMCatVote("sneakers", 0.9),
    )
    assert d.category == "sneakers"
    assert d.category_event == "cat_unanimous"
    assert d.category_vote == {
        "text": ["sneakers", round(TEXT_VOTE_WEIGHT, 4)],
        "llm":  ["sneakers", 0.9],
        "cv":   ["sneakers", 0.7],
    }


def test_cat_text_llm_agree_outweighs_cv():
    """text + LLM agree on sneakers; CV says tshirts → sneakers wins."""
    d = reconcile(
        scraper_category="sneakers", scraper_gender=None, scraper_colors=None,
        verdict=_verdict(category="tshirts", category_confidence=0.50),
        llm_vote=LLMCatVote("sneakers", 0.85),
    )
    assert d.category == "sneakers"
    assert d.category_event == "cat_text_llm_agree"


def test_cat_llm_cv_agree_overrides_wrong_text():
    """LLM + CV agree the product is sneakers; the alias scan put it in
    tshirts (e.g. "Jordan" matched a generic alias). The two image/name
    signals override text."""
    d = reconcile(
        scraper_category="tshirts", scraper_gender=None, scraper_colors=None,
        verdict=_verdict(category="sneakers", category_confidence=0.60),
        llm_vote=LLMCatVote("sneakers", 0.85),
    )
    assert d.category == "sneakers"
    assert d.category_event == "cat_llm_cv_agree"


def test_cat_text_cv_agree_overrides_wrong_llm():
    """text + CV agree on hoodies; LLM picked jackets. Two-of-three wins."""
    d = reconcile(
        scraper_category="hoodies", scraper_gender=None, scraper_colors=None,
        verdict=_verdict(category="hoodies", category_confidence=0.70),
        llm_vote=LLMCatVote("jackets", 0.70),
    )
    assert d.category == "hoodies"
    assert d.category_event == "cat_text_cv_agree"


def test_cat_text_only_when_others_abstain():
    """Only the alias scan fired; LLM was disabled, CV uncertain."""
    d = reconcile(
        scraper_category="hoodies", scraper_gender=None, scraper_colors=None,
        verdict=_verdict(category="tshirts", category_confidence=0.10),  # below CV_MIN_QUALIFY
        llm_vote=LLMCatVote(None, 0.0),
    )
    assert d.category == "hoodies"
    assert d.category_event == "cat_text_only"


def test_cat_llm_only_when_others_abstain():
    """Alias scan returned NULL, CV uncertain — only LLM has a signal."""
    d = reconcile(
        scraper_category=None, scraper_gender=None, scraper_colors=None,
        verdict=_verdict(category="tshirts", category_confidence=0.10),  # below CV_MIN_QUALIFY
        llm_vote=LLMCatVote("dresses", 0.80),
    )
    assert d.category == "dresses"
    assert d.category_event == "cat_llm_only"


def test_cat_cv_only_when_others_abstain():
    """text NULL + LLM disabled — CV alone fills the gap."""
    d = reconcile(
        scraper_category=None, scraper_gender=None, scraper_colors=None,
        verdict=_verdict(category="sneakers", category_confidence=0.55),
        llm_vote=LLMCatVote(None, 0.0),
    )
    assert d.category == "sneakers"
    assert d.category_event == "cat_cv_only"


def test_cat_three_way_split_picks_highest_weight():
    """All three sources qualify but each names a different category. The
    highest single-source weight wins. LLM @0.92 > text @0.85 > CV @0.50."""
    d = reconcile(
        scraper_category="hoodies", scraper_gender=None, scraper_colors=None,
        verdict=_verdict(category="sneakers", category_confidence=0.50),
        llm_vote=LLMCatVote("dresses", 0.92),
    )
    assert d.category == "dresses"
    assert d.category_event == "cat_three_way_split"


def test_cat_no_signal_returns_null():
    """No source qualifies — NULL stays NULL."""
    d = reconcile(
        scraper_category=None, scraper_gender=None, scraper_colors=None,
        verdict=_verdict(category="tshirts", category_confidence=0.10),  # below CV_MIN_QUALIFY
        llm_vote=LLMCatVote(None, 0.0),
    )
    assert d.category is None
    assert d.category_event == "cat_no_signal"


def test_cat_llm_low_confidence_filtered_out():
    """LLM below LLM_MIN_QUALIFY = 0.30 is treated as abstaining."""
    d = reconcile(
        scraper_category="hoodies", scraper_gender=None, scraper_colors=None,
        verdict=_verdict(category="tshirts", category_confidence=0.10),
        llm_vote=LLMCatVote("dresses", 0.20),  # below floor
    )
    assert d.category == "hoodies"
    assert d.category_event == "cat_text_only"


def test_cat_backwards_compat_no_llm_arg():
    """When llm_vote is omitted (legacy callers), 2-way vote still works:
    text + CV agree → unanimous-with-only-two-sources reduces to text_cv_agree."""
    d = reconcile(
        scraper_category="sneakers", scraper_gender=None, scraper_colors=None,
        verdict=_verdict(category="sneakers", category_confidence=0.7),
    )
    assert d.category == "sneakers"
    assert d.category_event == "cat_text_cv_agree"


def test_cat_vote_breakdown_captures_all_three_sources():
    """The category_vote dict surfaces per-source verdicts for auditing."""
    d = reconcile(
        scraper_category="hoodies", scraper_gender=None, scraper_colors=None,
        verdict=_verdict(category="sneakers", category_confidence=0.60),
        llm_vote=LLMCatVote("hoodies", 0.85),
    )
    assert "text" in d.category_vote
    assert "llm" in d.category_vote
    assert "cv" in d.category_vote
    assert d.category_vote["text"] == ["hoodies", 0.85]
    assert d.category_vote["llm"] == ["hoodies", 0.85]
    assert d.category_vote["cv"] == ["sneakers", 0.6]


# ---------------- Gender (2-way, unchanged) ---------------- #


def test_gender_corroborated():
    d = reconcile(
        scraper_category=None, scraper_gender="women", scraper_colors=None,
        verdict=_verdict(gender="women", gender_confidence=0.8),
    )
    assert d.gender == "women"
    assert d.gender_event == "cv_gender_corroborated"


def test_gender_override_above_threshold():
    d = reconcile(
        scraper_category=None, scraper_gender="unisex", scraper_colors=None,
        verdict=_verdict(gender="women", gender_confidence=0.70),
    )
    assert d.gender == "women"
    assert d.gender_event == "cv_gender_override"


def test_gender_women_flatlay_guard():
    d = reconcile(
        scraper_category=None, scraper_gender="women", scraper_colors=None,
        verdict=_verdict(gender="unisex", gender_confidence=0.50),
    )
    assert d.gender == "women"
    assert d.gender_event == "cv_gender_flatlay_guard"


def test_gender_men_flatlay_guard():
    d = reconcile(
        scraper_category=None, scraper_gender="men", scraper_colors=None,
        verdict=_verdict(gender="unisex", gender_confidence=0.50),
    )
    assert d.gender == "men"
    assert d.gender_event == "cv_gender_flatlay_guard"


def test_gender_flatlay_guard_fires_even_at_high_unisex_conf():
    d = reconcile(
        scraper_category=None, scraper_gender="women", scraper_colors=None,
        verdict=_verdict(gender="unisex", gender_confidence=0.90),
    )
    assert d.gender == "women"
    assert d.gender_event == "cv_gender_flatlay_guard"


def test_gender_override_still_fires_when_cv_picks_opposite():
    d = reconcile(
        scraper_category=None, scraper_gender="women", scraper_colors=None,
        verdict=_verdict(gender="men", gender_confidence=0.70),
    )
    assert d.gender == "men"
    assert d.gender_event == "cv_gender_override"


def test_gender_gap_fill():
    d = reconcile(
        scraper_category=None, scraper_gender=None, scraper_colors=None,
        verdict=_verdict(gender="women", gender_confidence=0.40),
    )
    assert d.gender == "women"
    assert d.gender_event == "cv_gender_filled_gap"


# ---------------- Colors (2-way, unchanged) ---------------- #


def test_color_replace_above_threshold():
    d = reconcile(
        scraper_category=None, scraper_gender=None,
        scraper_colors=["white", "tan"],
        verdict=_verdict(colors=[("black", 0.4), ("navy", 0.3)]),
    )
    assert d.colors == ["black", "navy"]
    assert d.color_event == "cv_color_replaced"


def test_color_keep_below_threshold():
    d = reconcile(
        scraper_category=None, scraper_gender=None,
        scraper_colors=["white", "tan"],
        verdict=_verdict(colors=[("black", 0.1), ("navy", 0.15)]),
    )
    assert d.colors == ["white", "tan"]
    assert d.color_event == "cv_color_kept"


def test_color_empty_cv_keeps_scraper():
    d = reconcile(
        scraper_category=None, scraper_gender=None,
        scraper_colors=["white"],
        verdict=_verdict(colors=[]),
    )
    assert d.colors == ["white"]
    assert d.color_event == "cv_color_kept"


# ---------------- Audit trail ---------------- #


def test_scraper_previous_captured_on_override():
    """The scraper_previous dict holds the pre-CV state for rollback."""
    d = reconcile(
        scraper_category="tshirts", scraper_gender="women",
        scraper_colors=["white", "tan"],
        verdict=_verdict(
            category="sneakers", category_confidence=0.60,
            gender="women", gender_confidence=0.80,
            colors=[("black", 0.4)],
        ),
        llm_vote=LLMCatVote("sneakers", 0.85),
    )
    assert d.scraper_previous == {
        "category": "tshirts",
        "gender": "women",
        "colors": ["white", "tan"],
    }


def test_thresholds_pinned():
    """Gender + color thresholds and per-source vote floors are the contract."""
    assert THRESHOLDS == {
        "gender_override":   0.55,
        "gender_gap_fill":   0.35,
        "color_avg":         0.30,
    }
    assert TEXT_VOTE_WEIGHT == 0.85
    assert LLM_MIN_QUALIFY  == 0.30
    assert CV_MIN_QUALIFY   == 0.25
