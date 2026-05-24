"""Pure-Python reconciliation policy.

Categories: 3-way confidence-weighted vote between text-alias (scraper),
LLM-by-name (services/llm_categorize), and CV-by-image (cv/classifier).
Gender / colors: unchanged 2-way scraper-vs-CV policy.

Has NO torch/transformers/openai dependency so unit tests can run without
`--extra cv`. The LLM verdict is passed in as a dataclass; we don't make
any network calls here.

Spec: plans/cv_classify/senior_dev_v2.md §6 (original 2-way) +
the user's hybrid amendment (2026-05-24).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from clothist_api.cv.types import CVVerdict


# ----------------------- Category vote (3-way) ----------------------- #

# Per-source minimum confidence to "qualify" as a vote. Anything below
# these floors is treated as "no signal" from that source.
TEXT_VOTE_WEIGHT = 0.85       # text-alias matches are deterministic when they fire
LLM_MIN_QUALIFY  = 0.30       # below this the LLM admits it's guessing
CV_MIN_QUALIFY   = 0.25       # matches the old category_gap_fill threshold


CategoryEvent = Literal[
    "cat_unanimous",
    "cat_text_llm_agree",
    "cat_text_cv_agree",
    "cat_llm_cv_agree",
    "cat_text_only",
    "cat_llm_only",
    "cat_cv_only",
    "cat_three_way_split",
    "cat_no_signal",
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
class LLMCatVote:
    """LLM-by-name verdict. Pure data — no dependency on openai/etc.

    `category=None` ⇒ LLM had no signal (disabled, errored, or "could not
    tell"). The vote function treats this as an abstention.
    """
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
    # Per-source breakdown — written to attributes.cv_verdict.category_vote
    # for auditing. Format: {"text": [cat|null, weight], "llm": [...], "cv": [...]}.
    category_vote: dict = field(default_factory=dict)


def reconcile(
    *,
    scraper_category: str | None,
    scraper_gender: str | None,
    scraper_colors: list[str] | None,
    verdict: CVVerdict,
    llm_vote: LLMCatVote | None = None,
) -> ReconciledRow:
    """Apply policy. Pure function — no I/O.

    `llm_vote` is optional; pass None (or an LLMCatVote with category=None)
    to fall back to the 2-source vote (text + CV only). This preserves the
    pre-hybrid behavior end-to-end when LLM is disabled.
    """
    scraper_previous = {
        "category": scraper_category,
        "gender":   scraper_gender,
        "colors":   list(scraper_colors) if scraper_colors else None,
    }

    cv_cat_qualified = (
        verdict.category if (verdict.category and verdict.category_confidence >= CV_MIN_QUALIFY)
        else None
    )
    cv_cat_conf = verdict.category_confidence if cv_cat_qualified else 0.0

    llm_cat_qualified: str | None = None
    llm_cat_conf = 0.0
    if llm_vote and llm_vote.category and llm_vote.confidence >= LLM_MIN_QUALIFY:
        llm_cat_qualified = llm_vote.category
        llm_cat_conf = llm_vote.confidence

    final_category, cat_evt, vote_breakdown = _reconcile_category_3way(
        text_category=scraper_category,
        llm_category=llm_cat_qualified, llm_conf=llm_cat_conf,
        cv_category=cv_cat_qualified,   cv_conf=cv_cat_conf,
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
        category_vote=vote_breakdown,
    )


def _reconcile_category_3way(
    *,
    text_category: str | None,
    llm_category: str | None, llm_conf: float,
    cv_category: str | None,  cv_conf: float,
) -> tuple[str | None, CategoryEvent, dict]:
    """3-way weighted vote across text-alias, LLM, and CV.

    Vote weights:
      text: TEXT_VOTE_WEIGHT (binary — match or no-match; aliases are precise)
      llm:  the LLM's self-reported confidence (already qualified)
      cv:   CLIP softmax probability (already qualified)

    Decision:
      1. Sum weights per candidate category.
      2. Winner = argmax. Tiebreaker = highest single-source weight.
      3. Returns the event that BEST describes which sources agreed.
    """
    text_w = TEXT_VOTE_WEIGHT if text_category else 0.0

    breakdown = {
        "text": [text_category, round(text_w, 4)],
        "llm":  [llm_category,  round(llm_conf, 4)],
        "cv":   [cv_category,   round(cv_conf, 4)],
    }

    # Sum weights per candidate.
    weights: dict[str, float] = {}
    if text_category:
        weights[text_category] = weights.get(text_category, 0.0) + text_w
    if llm_category:
        weights[llm_category] = weights.get(llm_category, 0.0) + llm_conf
    if cv_category:
        weights[cv_category] = weights.get(cv_category, 0.0) + cv_conf

    if not weights:
        return (None, "cat_no_signal", breakdown)

    # Pick the heaviest category. On ties, fall back to whichever single
    # source has the highest individual qualifying weight.
    winner = max(weights, key=weights.get)
    max_weight = weights[winner]
    if sum(1 for w in weights.values() if w == max_weight) > 1:
        # Tied on summed weight — break by highest individual weight.
        per_source = [
            (text_category, text_w),
            (llm_category, llm_conf),
            (cv_category, cv_conf),
        ]
        per_source = [(c, w) for c, w in per_source if c is not None]
        per_source.sort(key=lambda kv: -kv[1])
        winner = per_source[0][0]

    # Classify the event by which sources backed the winner.
    backers = {
        "text": text_category == winner,
        "llm":  llm_category  == winner,
        "cv":   cv_category   == winner,
    }
    n_backing = sum(backers.values())

    if n_backing >= 3:
        evt: CategoryEvent = "cat_unanimous"
    elif n_backing == 2:
        if backers["text"] and backers["llm"]:
            evt = "cat_text_llm_agree"
        elif backers["text"] and backers["cv"]:
            evt = "cat_text_cv_agree"
        else:
            evt = "cat_llm_cv_agree"
    else:
        # Exactly one source qualified for the winner. Is it the *only*
        # qualifying source overall? If yes → "_only" event; if other
        # sources qualified for a different category → split event.
        qualified_sources = sum(
            1 for c in (text_category, llm_category, cv_category) if c is not None
        )
        if qualified_sources == 1:
            evt = (
                "cat_text_only" if backers["text"]
                else "cat_llm_only" if backers["llm"]
                else "cat_cv_only"
            )
        else:
            evt = "cat_three_way_split"

    return (winner, evt, breakdown)


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
