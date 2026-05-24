"""Pure-Python reconciliation policy.

Categories: STRICT CASCADE. Each source is consulted in order and the first
one to hit the confidence threshold (default 0.95) wins. If nothing clears
the bar the product lands in `"other"`. Order: text-by-title → LLM → CV.

  text — fastest (sub-ms, deterministic regex)
  llm  — slow (Groq round-trip, batched)
  cv   — moderate (local CLIP inference)

The cascade has two virtues over the previous parallel 3-way vote:
  1. Correctness: when text is unambiguous (title contains "T-Shirt"), we
     don't let the LLM or CV second-guess. CV in particular can be fooled
     by photography (a "Striped Beach Towel" looks like a striped t-shirt
     to CLIP) — locking the answer at the title stage avoids that.
  2. Cost: high-confidence text matches skip the LLM call entirely, saving
     Groq tokens and wall-clock at scale.

Gender / colors: unchanged 2-way scraper-vs-CV policy.

Has NO torch/transformers/openai dependency so unit tests can run without
`--extra cv`. The LLM verdict is passed in as a dataclass; no network here.

Spec: user request 2026-05-24 (Striped Beach Towel regression).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from clothist_api.cv.types import CVVerdict


# ----------------------- Category cascade ----------------------- #

# The threshold each source's confidence must clear to "decide" the
# category. When NO source clears its threshold the product is bucketed
# as `"other"`. Text and LLM remain at 0.95 (both are calibrated to emit
# high values only on clear matches), but CV gets a lower floor: CLIP's
# 13-class softmax dilutes probability mass, so legitimate "this is
# obviously a sneaker" verdicts often land 0.85-0.94. Raising the gate
# would dump them into "other" and bloat the catch-all bucket — the
# user's reported "Other contains shoes/socks/vests" regression.
CASCADE_THRESHOLD = 0.95          # text + LLM
CASCADE_CV_THRESHOLD = 0.85       # CV-specific, looser per the above
OTHER_CATEGORY = "other"


CategoryEvent = Literal[
    "cascade_text",   # text-by-title cleared threshold
    "cascade_llm",    # text didn't; LLM cleared threshold
    "cascade_cv",     # text + LLM didn't; CV cleared threshold
    "cascade_other",  # nothing cleared → "other"
]


# ----------------------- Gender / colors (2-way) ----------------------- #

THRESHOLDS = {
    "gender_override":   0.55,
    "gender_gap_fill":   0.35,
    "color_avg":         0.30,
}


GenderEvent = Literal[
    "cv_gender_corroborated", "cv_gender_override", "cv_gender_below_threshold",
    "cv_gender_filled_gap", "cv_gender_gap_unfilled", "cv_gender_flatlay_guard",
    "cv_gender_both_unknown",
]
ColorEvent = Literal["cv_color_replaced", "cv_color_kept"]


@dataclass(slots=True)
class TextCatVote:
    """Text-by-title verdict. Pure data — no regex deps here.

    `category=None` ⇒ no alias matched the title. The cascade treats this
    as the text stage abstaining; the LLM stage is consulted next.
    """
    category: str | None
    confidence: float
    matched_alias: str | None = None


@dataclass(slots=True)
class LLMCatVote:
    """LLM-by-name verdict. Pure data — no dependency on openai/etc."""
    category: str | None
    confidence: float


@dataclass(slots=True)
class ReconciledRow:
    """The post-reconciliation winner for one product."""

    category: str | None
    gender: str | None
    colors: list[str] | None
    category_event: CategoryEvent
    gender_event: GenderEvent
    color_event: ColorEvent
    scraper_previous: dict
    # Per-stage breakdown — written to attributes.cv_verdict.category_cascade
    # for auditing. Format:
    #   {"text": [cat|null, conf], "llm": [...], "cv": [...],
    #    "winner_stage": "text"|"llm"|"cv"|"other", "threshold": 0.95}
    category_cascade: dict = field(default_factory=dict)


def reconcile(
    *,
    scraper_category: str | None,  # legacy: ignored by the cascade but kept for API compat
    scraper_gender: str | None,
    scraper_colors: list[str] | None,
    verdict: CVVerdict,
    text_vote: TextCatVote | None = None,
    llm_vote: LLMCatVote | None = None,
    cascade_threshold: float = CASCADE_THRESHOLD,
    cv_cascade_threshold: float = CASCADE_CV_THRESHOLD,
) -> ReconciledRow:
    """Apply the cascade for category, plus the existing 2-way policy for
    gender and color. Pure function — no I/O.

    `text_vote=None` falls back to a synthetic vote from scraper_category at
    a moderate confidence (0.85), preserving compatibility with callers that
    haven't been ported to the new title-based text classifier yet.
    """
    scraper_previous = {
        "category": scraper_category,
        "gender":   scraper_gender,
        "colors":   list(scraper_colors) if scraper_colors else None,
    }

    if text_vote is None:
        # Back-compat path: synthesize a text vote from the scraper's stored
        # category. Below 0.95 → falls through to LLM/CV as expected.
        text_vote = TextCatVote(
            category=scraper_category,
            confidence=0.85 if scraper_category else 0.0,
        )
    if llm_vote is None:
        llm_vote = LLMCatVote(category=None, confidence=0.0)

    final_category, cat_evt, cascade_breakdown = _cascade_category(
        text=text_vote, llm=llm_vote, verdict=verdict,
        text_llm_threshold=cascade_threshold,
        cv_threshold=cv_cascade_threshold,
    )
    final_gender, gen_evt = _reconcile_gender(
        scraper_gender, verdict.gender, verdict.gender_confidence,
    )
    final_colors, col_evt = _reconcile_colors(scraper_colors, verdict.colors)

    return ReconciledRow(
        category=final_category,
        gender=final_gender,
        colors=final_colors,
        category_event=cat_evt,
        gender_event=gen_evt,
        color_event=col_evt,
        scraper_previous=scraper_previous,
        category_cascade=cascade_breakdown,
    )


def _cascade_category(
    *,
    text: TextCatVote,
    llm: LLMCatVote,
    verdict: CVVerdict,
    text_llm_threshold: float,
    cv_threshold: float,
) -> tuple[str, CategoryEvent, dict]:
    """Strict cascade — first source ≥ threshold wins; fall back to "other".

    The text and LLM stages share `text_llm_threshold` (default 0.95). The
    CV stage uses the looser `cv_threshold` (default 0.85) since CLIP's
    13-class softmax rarely peaks at 0.95 on real fashion photos.
    """
    cv_cat = verdict.category
    cv_conf = verdict.category_confidence

    breakdown_base = {
        "text": [text.category, round(text.confidence, 4)],
        "llm":  [llm.category,  round(llm.confidence, 4)],
        "cv":   [cv_cat,        round(cv_conf, 4)],
        "threshold_text_llm": text_llm_threshold,
        "threshold_cv":       cv_threshold,
    }

    if text.category and text.confidence >= text_llm_threshold:
        return (text.category, "cascade_text",
                {**breakdown_base, "winner_stage": "text"})
    if llm.category and llm.confidence >= text_llm_threshold:
        return (llm.category, "cascade_llm",
                {**breakdown_base, "winner_stage": "llm"})
    if cv_cat and cv_conf >= cv_threshold:
        return (cv_cat, "cascade_cv",
                {**breakdown_base, "winner_stage": "cv"})
    return (OTHER_CATEGORY, "cascade_other",
            {**breakdown_base, "winner_stage": "other"})


# ----------------------- Gender (unchanged 2-way) ----------------------- #


def _reconcile_gender(
    scraper: str | None, cv: str | None, cv_conf: float,
) -> tuple[str | None, GenderEvent]:
    cv_known = cv is not None and cv_conf >= THRESHOLDS["gender_gap_fill"]

    if scraper is None and not cv_known:
        return (None, "cv_gender_both_unknown")
    if scraper is None and cv_known:
        return (cv, "cv_gender_filled_gap")
    if scraper is not None and not cv_known:
        return (scraper, "cv_gender_gap_unfilled")
    # Both have values
    if cv == scraper:
        return (scraper, "cv_gender_corroborated")
    # Strong flat-lay guard: if scraper has a confident gender (women/men)
    # and CV's verdict is `unisex`, ALWAYS keep the scraper's gender —
    # regardless of CV's confidence. CV saying "unisex" on a flat-lay
    # product photo (no model visible) does NOT disprove the scraper's
    # text-derived gender signal.
    if scraper in ("women", "men") and cv == "unisex":
        return (scraper, "cv_gender_flatlay_guard")
    if cv_conf >= THRESHOLDS["gender_override"]:
        return (cv, "cv_gender_override")
    return (scraper, "cv_gender_below_threshold")


# ----------------------- Colors (unchanged 2-way) ----------------------- #


def _reconcile_colors(
    scraper: list[str] | None,
    cv_colors: list[tuple[str, float]],
) -> tuple[list[str] | None, ColorEvent]:
    if not cv_colors:
        return (scraper, "cv_color_kept")
    avg_conf = sum(c for _, c in cv_colors) / len(cv_colors)
    if avg_conf < THRESHOLDS["color_avg"]:
        return (scraper, "cv_color_kept")
    return ([name for name, _ in cv_colors], "cv_color_replaced")
