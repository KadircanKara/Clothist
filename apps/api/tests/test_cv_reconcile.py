"""T2 — reconciliation unit tests.

Pure-Python; no torch/transformers/openai. Runs without `--extra cv` and
without an LLM_API_KEY.

Category: STRICT CASCADE — text → LLM → CV at the 0.95 threshold,
fallback to "other" if no source clears it.
Gender / colors: 2-way scraper-vs-CV (unchanged).
"""
from __future__ import annotations

import pytest

from clothist_api.cv.reconcile import (
    CASCADE_CV_THRESHOLD,
    CASCADE_THRESHOLD,
    OTHER_CATEGORY,
    THRESHOLDS,
    LLMCatVote,
    ReconciledRow,
    TextCatVote,
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


# ---------------- Cascade ---------------- #


def test_cascade_text_wins_at_threshold():
    """Text at exactly 0.95 clears the bar; LLM and CV are not consulted."""
    d = reconcile(
        scraper_category=None, scraper_gender=None, scraper_colors=None,
        verdict=_verdict(category="footwear", category_confidence=0.99),  # ignored
        text_vote=TextCatVote("tshirts", 0.95),
        llm_vote=LLMCatVote("dresses", 0.99),  # also ignored
    )
    assert d.category == "tshirts"
    assert d.category_event == "cascade_text"
    assert d.category_cascade["winner_stage"] == "text"


def test_cascade_text_above_threshold_wins():
    """Text at 0.97 (canonical-token tier) → text wins; LLM skipped logically."""
    d = reconcile(
        scraper_category=None, scraper_gender=None, scraper_colors=None,
        verdict=_verdict(category="dresses", category_confidence=0.85),
        text_vote=TextCatVote("tshirts", 0.97),
        llm_vote=LLMCatVote("dresses", 0.90),
    )
    assert d.category == "tshirts"
    assert d.category_event == "cascade_text"


def test_cascade_falls_through_to_llm():
    """Text below threshold → LLM consulted; LLM at 0.97 wins."""
    d = reconcile(
        scraper_category=None, scraper_gender=None, scraper_colors=None,
        verdict=_verdict(category="hoodies", category_confidence=0.50),
        text_vote=TextCatVote("footwear", 0.90),  # below 0.95
        llm_vote=LLMCatVote("dresses", 0.97),
    )
    assert d.category == "dresses"
    assert d.category_event == "cascade_llm"
    assert d.category_cascade["winner_stage"] == "llm"


def test_cascade_falls_through_to_cv():
    """Text and LLM both below threshold → CV consulted; CV at 0.97 wins."""
    d = reconcile(
        scraper_category=None, scraper_gender=None, scraper_colors=None,
        verdict=_verdict(category="dresses", category_confidence=0.97),
        text_vote=TextCatVote("footwear", 0.90),
        llm_vote=LLMCatVote("hoodies", 0.80),
    )
    assert d.category == "dresses"
    assert d.category_event == "cascade_cv"
    assert d.category_cascade["winner_stage"] == "cv"


def test_cascade_falls_through_to_other():
    """No source clears its threshold → category is 'other'. text/LLM gate
    is 0.95; CV gate is 0.85. Here every source sits below its own gate."""
    d = reconcile(
        scraper_category=None, scraper_gender=None, scraper_colors=None,
        verdict=_verdict(category="tshirts", category_confidence=0.80),  # < 0.85
        text_vote=TextCatVote("accessories", 0.90),                       # < 0.95
        llm_vote=LLMCatVote(None, 0.0),
    )
    assert d.category == OTHER_CATEGORY
    assert d.category_event == "cascade_other"
    assert d.category_cascade["winner_stage"] == "other"


def test_cascade_cv_wins_between_thresholds():
    """CV at 0.88 — above CV's 0.85 gate, below the text/LLM 0.95 gate —
    now decides the category. Before the dual-threshold split this would
    have fallen to 'other' even though CV was clearly confident enough.
    Tracks the "shoes in Other" regression the user reported."""
    d = reconcile(
        scraper_category=None, scraper_gender=None, scraper_colors=None,
        verdict=_verdict(category="footwear", category_confidence=0.88),
        text_vote=TextCatVote(None, 0.0),
        llm_vote=LLMCatVote(None, 0.0),
    )
    assert d.category == "footwear"
    assert d.category_event == "cascade_cv"


def test_cascade_all_sources_silent_to_other():
    """Text NULL, LLM abstains, CV uncertain → other."""
    d = reconcile(
        scraper_category=None, scraper_gender=None, scraper_colors=None,
        verdict=_verdict(category="tshirts", category_confidence=0.10),
        text_vote=TextCatVote(None, 0.0),
        llm_vote=LLMCatVote(None, 0.0),
    )
    assert d.category == OTHER_CATEGORY
    assert d.category_event == "cascade_other"


def test_cascade_threshold_is_exclusive_below():
    """Confidence at exactly 0.949 does NOT clear 0.95 — boundary check."""
    d = reconcile(
        scraper_category=None, scraper_gender=None, scraper_colors=None,
        verdict=_verdict(category="tshirts", category_confidence=0.10),
        text_vote=TextCatVote("footwear", 0.949),
        llm_vote=LLMCatVote(None, 0.0),
    )
    assert d.category == OTHER_CATEGORY


def test_cascade_breakdown_carries_all_three_stages():
    """category_cascade dict surfaces each stage's [cat, conf] for auditing."""
    d = reconcile(
        scraper_category=None, scraper_gender=None, scraper_colors=None,
        verdict=_verdict(category="hoodies", category_confidence=0.80),
        text_vote=TextCatVote("footwear", 0.90),
        llm_vote=LLMCatVote("dresses", 0.85),
    )
    assert d.category_cascade["text"] == ["footwear", 0.9]
    assert d.category_cascade["llm"]  == ["dresses", 0.85]
    assert d.category_cascade["cv"]   == ["hoodies", 0.8]
    assert d.category_cascade["threshold_text_llm"] == CASCADE_THRESHOLD
    assert d.category_cascade["threshold_cv"] == CASCADE_CV_THRESHOLD


def test_cascade_backwards_compat_no_text_or_llm():
    """Legacy callers may omit text_vote/llm_vote — we synthesize a text
    vote from scraper_category at 0.85 (below threshold) so the cascade
    falls through. With only CV at 0.97, CV wins."""
    d = reconcile(
        scraper_category="tshirts", scraper_gender=None, scraper_colors=None,
        verdict=_verdict(category="footwear", category_confidence=0.97),
    )
    # text_vote synthesized at 0.85, below 0.95 → CV wins.
    assert d.category == "footwear"
    assert d.category_event == "cascade_cv"


def test_cascade_text_with_null_category_at_high_conf_is_ignored():
    """Text vote with category=None can't 'win' even at high confidence —
    None means 'no match', not a category to assign."""
    d = reconcile(
        scraper_category=None, scraper_gender=None, scraper_colors=None,
        verdict=_verdict(category="dresses", category_confidence=0.96),
        text_vote=TextCatVote(None, 0.99),  # contradictory but harmless
        llm_vote=LLMCatVote(None, 0.0),
    )
    assert d.category == "dresses"
    assert d.category_event == "cascade_cv"


def test_cascade_custom_threshold():
    """The caller can lower either threshold for ablation experiments."""
    d = reconcile(
        scraper_category=None, scraper_gender=None, scraper_colors=None,
        verdict=_verdict(category="footwear", category_confidence=0.50),
        text_vote=TextCatVote("dresses", 0.80),
        llm_vote=LLMCatVote("hoodies", 0.85),
        cascade_threshold=0.75,
    )
    assert d.category == "dresses"
    assert d.category_event == "cascade_text"


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


# ---------------- Constants ---------------- #


def test_thresholds_pinned():
    assert THRESHOLDS == {
        "gender_override":   0.55,
        "gender_gap_fill":   0.35,
        "color_avg":         0.30,
    }
    assert CASCADE_THRESHOLD == 0.95
    assert CASCADE_CV_THRESHOLD == 0.85
    assert OTHER_CATEGORY == "other"
