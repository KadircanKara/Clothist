"""Pure-Python reconciliation policy.

Category assignment (simplified 2026-05-25 — user direction "only
categorize by the actual category from the source"):

  1. vendor product_type via scrapers/normalize.py:normalize_category
       — when it maps, that's the answer.
  2. else title-based non-clothing detection (categorize_by_text)
       — flags homewares / decor that vendors mistag.
  3. else "uncategorized".

Title + LLM + CV are no longer consulted for category — they were
swing-and-miss heuristics next to vendor-supplied taxonomy. The
"uncategorized" bucket exists as the catch-all but in practice should
be tiny because every storefront we ingest from already tags
product_type.

Gender + colors keep the same 2-way scraper-vs-CV policy: vendors are
unreliable about gender (mostly tag-unisex) and don't surface a
structured color signal, so CV remains the recovery layer.

Has NO torch/transformers/openai dependency — unit tests can run
without `--extra cv`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from clothist_api.cv.types import CVVerdict


# ----------------------- Category ----------------------- #

UNCATEGORIZED = "uncategorized"
EXCLUDED = "excluded"

CategoryEvent = Literal[
    "category_vendor",         # vendor product_type mapped cleanly
    "category_non_clothing",   # title flagged the item as non-clothing → excluded
    "category_uncategorized",  # vendor mapped to nothing; title looks like clothing
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
class ReconciledRow:
    """The post-reconciliation winner for one product."""

    category: str
    gender: str | None
    colors: list[str] | None
    category_event: CategoryEvent
    gender_event: GenderEvent
    color_event: ColorEvent
    scraper_previous: dict
    # Audit payload — written to attributes.cv_verdict.category_source.
    # Format: {"vendor_product_type": "...", "vendor_canonical": "...",
    #          "non_clothing_match": "..." | None, "winner": "vendor"|...}
    category_source: dict = field(default_factory=dict)


def reconcile(
    *,
    scraper_category: str | None,
    scraper_gender: str | None,
    scraper_colors: list[str] | None,
    verdict: CVVerdict,
    vendor_category: str | None,
    title: str,
    non_clothing_alias: str | None = None,
) -> ReconciledRow:
    """Apply the simplified category logic + the 2-way gender/color
    reconciliation. Pure function — no I/O.

    Args:
      vendor_category: result of `normalize_category(product_type)`,
        already a canonical token or None.
      title: product title — checked for non-clothing tokens when
        vendor mapping fails.
      non_clothing_alias: which non-clothing token matched the title
        (debug only — passed in from the caller so we don't double-run
        the regex tournament inside reconcile).
    """
    scraper_previous = {
        "category": scraper_category,
        "gender":   scraper_gender,
        "colors":   list(scraper_colors) if scraper_colors else None,
    }

    final_category, cat_evt, source = _resolve_category(
        vendor_category=vendor_category,
        non_clothing_alias=non_clothing_alias,
        title=title,
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
        category_source=source,
    )


def _resolve_category(
    *,
    vendor_category: str | None,
    non_clothing_alias: str | None,
    title: str,
) -> tuple[str, CategoryEvent, dict]:
    """Three-step decision: vendor → non-clothing → uncategorized."""
    base = {
        "vendor": vendor_category,
        "non_clothing_alias": non_clothing_alias,
        "title": title,
    }
    if vendor_category:
        return (vendor_category, "category_vendor", {**base, "winner": "vendor"})
    if non_clothing_alias:
        return (EXCLUDED, "category_non_clothing", {**base, "winner": "non_clothing"})
    return (UNCATEGORIZED, "category_uncategorized", {**base, "winner": "uncategorized"})


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
