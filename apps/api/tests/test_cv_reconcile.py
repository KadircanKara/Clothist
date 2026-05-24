"""T2 — reconciliation unit tests.

Pure-Python; does NOT import torch/transformers. Runs without `--extra cv`.

Exercises every state in plans/cv_classify/senior_dev_v2.md §6 + §10b.
"""
from __future__ import annotations

import pytest

from clothist_api.cv.reconcile import (
    THRESHOLDS,
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


# ---------------- Category ---------------- #


def test_category_corroborated_keeps_scraper_value():
    """1. Agreement: scraper=tshirts, CV=tshirts → final=tshirts."""
    d = reconcile(
        scraper_category="tshirts", scraper_gender=None, scraper_colors=None,
        verdict=_verdict(category="tshirts", category_confidence=0.9),
    )
    assert d.category == "tshirts"
    assert d.category_event == "cv_corroborated"


def test_category_override_above_threshold():
    """2. Override: scraper=tshirts, CV=sneakers @ 0.60 → final=sneakers."""
    d = reconcile(
        scraper_category="tshirts", scraper_gender=None, scraper_colors=None,
        verdict=_verdict(category="sneakers", category_confidence=0.60),
    )
    assert d.category == "sneakers"
    assert d.category_event == "cv_category_override"


def test_category_below_threshold_keeps_scraper():
    """3. Below threshold: scraper=tshirts, CV=sneakers @ 0.30 → keep tshirts."""
    d = reconcile(
        scraper_category="tshirts", scraper_gender=None, scraper_colors=None,
        verdict=_verdict(category="sneakers", category_confidence=0.30),
    )
    assert d.category == "tshirts"
    assert d.category_event == "cv_below_threshold"


def test_category_gap_fill_above_low_threshold():
    """4. Gap fill: scraper=NULL, CV=sneakers @ 0.30 → fill with sneakers."""
    d = reconcile(
        scraper_category=None, scraper_gender=None, scraper_colors=None,
        verdict=_verdict(category="sneakers", category_confidence=0.30),
    )
    assert d.category == "sneakers"
    assert d.category_event == "cv_filled_gap"


def test_category_gap_unfilled_below_low_threshold():
    """5. Gap unfilled: scraper=NULL, CV=sneakers @ 0.20 → keep NULL."""
    d = reconcile(
        scraper_category=None, scraper_gender=None, scraper_colors=None,
        verdict=_verdict(category="sneakers", category_confidence=0.20),
    )
    assert d.category is None
    assert d.category_event == "cv_gap_unfilled"


def test_category_both_unknown_keeps_null():
    """6. Both unknown: scraper=NULL, CV top-1 below gap threshold → NULL."""
    d = reconcile(
        scraper_category=None, scraper_gender=None, scraper_colors=None,
        verdict=_verdict(category="sneakers", category_confidence=0.10),
    )
    assert d.category is None
    assert d.category_event == "cv_both_unknown"


def test_category_undetermined_keeps_scraper():
    """7. Scraper has value but CV uncertain (< gap_fill) → keep scraper."""
    d = reconcile(
        scraper_category="tshirts", scraper_gender=None, scraper_colors=None,
        verdict=_verdict(category="sneakers", category_confidence=0.15),
    )
    assert d.category == "tshirts"
    assert d.category_event == "cv_undetermined"


# ---------------- Gender ---------------- #


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
    """7. scraper=women + CV=unisex → keep women regardless of CV conf
    (strengthened post-first-ingest: a flat-lay's unisex verdict never
    disproves scraper's confident gender signal)."""
    d = reconcile(
        scraper_category=None, scraper_gender="women", scraper_colors=None,
        verdict=_verdict(gender="unisex", gender_confidence=0.50),
    )
    assert d.gender == "women"
    assert d.gender_event == "cv_gender_flatlay_guard"


def test_gender_men_flatlay_guard():
    """8. Symmetric: scraper=men + CV=unisex → keep men."""
    d = reconcile(
        scraper_category=None, scraper_gender="men", scraper_colors=None,
        verdict=_verdict(gender="unisex", gender_confidence=0.50),
    )
    assert d.gender == "men"
    assert d.gender_event == "cv_gender_flatlay_guard"


def test_gender_flatlay_guard_fires_even_at_high_unisex_conf():
    """Tightened §6b: high-confidence unisex still loses to scraper's
    gendered verdict — CV's `unisex` is a not-a-disagreement, not a
    counter-vote. This is what the Rothy's flat-lay regression demanded."""
    d = reconcile(
        scraper_category=None, scraper_gender="women", scraper_colors=None,
        verdict=_verdict(gender="unisex", gender_confidence=0.90),
    )
    assert d.gender == "women"
    assert d.gender_event == "cv_gender_flatlay_guard"


def test_gender_override_still_fires_when_cv_picks_opposite():
    """Override still happens when CV picks the OPPOSITE concrete gender:
    scraper=women, CV=men @ 0.70 → final=men. The flat-lay guard only
    covers the unisex fallback path."""
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


# ---------------- Colors ---------------- #


def test_color_replace_above_threshold():
    """9. CV avg conf >= color_avg → replace."""
    d = reconcile(
        scraper_category=None, scraper_gender=None,
        scraper_colors=["white", "tan"],
        verdict=_verdict(colors=[("black", 0.4), ("navy", 0.3)]),
    )
    assert d.colors == ["black", "navy"]
    assert d.color_event == "cv_color_replaced"


def test_color_keep_below_threshold():
    """9b. CV avg conf < color_avg → keep scraper list."""
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
    """10. scraper_previous holds the pre-CV state for the audit trail."""
    d = reconcile(
        scraper_category="tshirts", scraper_gender="women",
        scraper_colors=["white", "tan"],
        verdict=_verdict(
            category="sneakers", category_confidence=0.60,
            gender="women", gender_confidence=0.80,
            colors=[("black", 0.4)],
        ),
    )
    assert d.scraper_previous == {
        "category": "tshirts",
        "gender": "women",
        "colors": ["white", "tan"],
    }


def test_thresholds_pinned():
    """11. THRESHOLDS map is the contract; raising them silently weakens the
    CV pipeline. This test fails if anyone tweaks values without intent."""
    assert THRESHOLDS == {
        "category_override": 0.40,
        "category_gap_fill": 0.25,
        "gender_override":   0.55,
        "gender_gap_fill":   0.35,
        "color_avg":         0.30,
    }
