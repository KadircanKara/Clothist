"""Pure-Python reconciliation policy.

Decides whether the CV verdict overrides the scraper's category/gender/
colors values. Has NO torch/transformers dependency so unit tests can run
without `--extra cv` installed.

Spec: plans/cv_classify/senior_dev_v2.md §6.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from clothist_api.cv.types import CVVerdict


# Thresholds — post `logit_scale.exp()` softmax probabilities per §6 preamble.
THRESHOLDS = {
    "category_override": 0.40,
    "category_gap_fill": 0.25,
    "gender_override":   0.55,
    "gender_gap_fill":   0.35,
    "color_avg":         0.30,
}

# Below this confidence, CV's top-1 is treated as indistinguishable from
# random (13-class softmax noise floor ≈ 1/13 = 0.077; we set a buffer
# above). Used only to distinguish the two "CV unconfident" log events:
# above NOISE_FLOOR + below gap_fill → `cv_gap_unfilled`; below NOISE_FLOOR
# → `cv_both_unknown`. Both leave the column NULL.
NOISE_FLOOR = 0.15


CategoryEvent = Literal[
    "cv_corroborated", "cv_category_override", "cv_below_threshold",
    "cv_filled_gap", "cv_gap_unfilled", "cv_both_unknown", "cv_undetermined",
]
GenderEvent = Literal[
    "cv_gender_corroborated", "cv_gender_override", "cv_gender_below_threshold",
    "cv_gender_filled_gap", "cv_gender_gap_unfilled", "cv_gender_flatlay_guard",
    "cv_gender_both_unknown",
]
ColorEvent = Literal["cv_color_replaced", "cv_color_kept"]


@dataclass(slots=True)
class ReconciledRow:
    """The post-reconciliation winner for one product."""

    category: str | None
    gender: str | None
    colors: list[str] | None
    # Logging — caller emits structured logs from these.
    category_event: CategoryEvent
    gender_event: GenderEvent
    color_event: ColorEvent
    # The pre-CV scraper-side payload, captured here so the caller can write
    # it into `attributes.cv_verdict.scraper_previous` per §5a.
    scraper_previous: dict


def reconcile(
    *,
    scraper_category: str | None,
    scraper_gender: str | None,
    scraper_colors: list[str] | None,
    verdict: CVVerdict,
) -> ReconciledRow:
    """Apply §6 policy. Pure function — no I/O. Returns the winning values
    + log events + the scraper-previous audit trail.
    """
    scraper_previous = {
        "category": scraper_category,
        "gender":   scraper_gender,
        "colors":   list(scraper_colors) if scraper_colors else None,
    }

    final_category, cat_evt = _reconcile_category(
        scraper_category, verdict.category, verdict.category_confidence,
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
    )


def _reconcile_category(
    scraper: str | None, cv: str | None, cv_conf: float,
) -> tuple[str | None, CategoryEvent]:
    # CV's top-1 might fall below the gap-fill threshold — treat as "unknown".
    cv_known = cv is not None and cv_conf >= THRESHOLDS["category_gap_fill"]

    if scraper is None and not cv_known:
        # Distinguish "CV had a usable hint but below gap_fill" from "CV had
        # near-random signal". Same DB outcome (NULL stays NULL); different
        # event so we can tune prompts.
        if cv is not None and cv_conf >= NOISE_FLOOR:
            return (None, "cv_gap_unfilled")
        return (None, "cv_both_unknown")
    if scraper is None and cv_known:
        return (cv, "cv_filled_gap")
    if scraper is not None and not cv_known:
        # Scraper had a value, CV didn't push anything confident — keep scraper.
        return (scraper, "cv_undetermined")
    # Both have values
    if cv == scraper:
        return (scraper, "cv_corroborated")
    if cv_conf >= THRESHOLDS["category_override"]:
        return (cv, "cv_category_override")
    return (scraper, "cv_below_threshold")


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
    # text-derived gender signal. The override path only fires when CV
    # confidently swaps to the OPPOSITE concrete gender (women↔men). This
    # is the tightened §6b after the first live ingest showed 22/30 Rothy's
    # women's-shoes flat-lays getting wrongly demoted to unisex.
    if scraper in ("women", "men") and cv == "unisex":
        return (scraper, "cv_gender_flatlay_guard")
    if cv_conf >= THRESHOLDS["gender_override"]:
        return (cv, "cv_gender_override")
    return (scraper, "cv_gender_below_threshold")


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
