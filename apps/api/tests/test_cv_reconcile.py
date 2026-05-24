"""T2 — reconciliation unit tests (simplified vendor-only flow).

The category pipeline collapsed on 2026-05-25 per user direction:
  category = vendor product_type  →  non-clothing-from-title  →  uncategorized

Title/LLM/CV cascade for category is gone — title + CV still drive
gender and color, but category is purely vendor-derived.

Pure-Python; no torch/transformers/openai. Runs without `--extra cv`.
"""
from __future__ import annotations

import pytest

from clothist_api.cv.reconcile import (
    EXCLUDED,
    THRESHOLDS,
    UNCATEGORIZED,
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


def _call(*, vendor_category=None, non_clothing_alias=None, title="A product",
          scraper_gender=None, scraper_colors=None, verdict=None):
    return reconcile(
        scraper_category=None,
        scraper_gender=scraper_gender,
        scraper_colors=scraper_colors,
        verdict=verdict or _verdict(),
        vendor_category=vendor_category,
        title=title,
        non_clothing_alias=non_clothing_alias,
    )


# ---------------- Category ---------------- #


def test_category_vendor_wins():
    """Vendor product_type maps to a canonical token → that's the answer."""
    d = _call(vendor_category="tshirts", title="Some Tee")
    assert d.category == "tshirts"
    assert d.category_event == "category_vendor"
    assert d.category_source["winner"] == "vendor"


def test_category_vendor_beats_non_clothing_alias():
    """If vendor mapped, we trust it — even when the title looks non-clothing
    (a hypothetical "Tee with Vase Print" should stay tshirts)."""
    d = _call(vendor_category="tshirts", non_clothing_alias="vase",
              title="Vase Print Tee")
    assert d.category == "tshirts"
    assert d.category_event == "category_vendor"


def test_non_clothing_when_vendor_misses():
    """No vendor mapping but title flags non-clothing → excluded."""
    d = _call(vendor_category=None, non_clothing_alias="vase",
              title="Bud Vase")
    assert d.category == EXCLUDED
    assert d.category_event == "category_non_clothing"
    assert d.category_source["winner"] == "non_clothing"


def test_uncategorized_when_nothing_matches():
    """No vendor mapping and no non-clothing token → uncategorized."""
    d = _call(vendor_category=None, non_clothing_alias=None,
              title="Mystery Product")
    assert d.category == UNCATEGORIZED
    assert d.category_event == "category_uncategorized"


def test_uncategorized_carries_audit_payload():
    """category_source surfaces inputs for offline auditing."""
    d = _call(vendor_category=None, title="Mystery Product")
    assert d.category_source == {
        "vendor": None,
        "non_clothing_alias": None,
        "title": "Mystery Product",
        "winner": "uncategorized",
    }


# ---------------- Gender (unchanged 2-way) ---------------- #


def test_gender_corroborated():
    d = _call(scraper_gender="women",
              verdict=_verdict(gender="women", gender_confidence=0.8))
    assert d.gender == "women"
    assert d.gender_event == "cv_gender_corroborated"


def test_gender_override_above_threshold():
    d = _call(scraper_gender="unisex",
              verdict=_verdict(gender="women", gender_confidence=0.70))
    assert d.gender == "women"
    assert d.gender_event == "cv_gender_override"


def test_gender_women_flatlay_guard():
    d = _call(scraper_gender="women",
              verdict=_verdict(gender="unisex", gender_confidence=0.50))
    assert d.gender == "women"
    assert d.gender_event == "cv_gender_flatlay_guard"


def test_gender_flatlay_guard_fires_even_at_high_unisex_conf():
    d = _call(scraper_gender="women",
              verdict=_verdict(gender="unisex", gender_confidence=0.90))
    assert d.gender == "women"
    assert d.gender_event == "cv_gender_flatlay_guard"


def test_gender_override_still_fires_when_cv_picks_opposite():
    d = _call(scraper_gender="women",
              verdict=_verdict(gender="men", gender_confidence=0.70))
    assert d.gender == "men"
    assert d.gender_event == "cv_gender_override"


def test_gender_gap_fill():
    d = _call(scraper_gender=None,
              verdict=_verdict(gender="women", gender_confidence=0.40))
    assert d.gender == "women"
    assert d.gender_event == "cv_gender_filled_gap"


# ---------------- Colors (unchanged 2-way) ---------------- #


def test_color_replace_above_threshold():
    d = _call(
        scraper_colors=["white", "tan"],
        verdict=_verdict(colors=[("black", 0.4), ("navy", 0.3)]),
    )
    assert d.colors == ["black", "navy"]
    assert d.color_event == "cv_color_replaced"


def test_color_keep_below_threshold():
    d = _call(
        scraper_colors=["white", "tan"],
        verdict=_verdict(colors=[("black", 0.1), ("navy", 0.15)]),
    )
    assert d.colors == ["white", "tan"]
    assert d.color_event == "cv_color_kept"


def test_color_empty_cv_keeps_scraper():
    d = _call(scraper_colors=["white"], verdict=_verdict(colors=[]))
    assert d.colors == ["white"]
    assert d.color_event == "cv_color_kept"


# ---------------- Constants ---------------- #


def test_thresholds_pinned():
    assert THRESHOLDS == {
        "gender_override":   0.55,
        "gender_gap_fill":   0.35,
        "color_avg":         0.30,
    }
    assert UNCATEGORIZED == "uncategorized"
    assert EXCLUDED == "excluded"
