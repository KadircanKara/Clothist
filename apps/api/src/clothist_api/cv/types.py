"""Plain dataclasses for the CV pipeline. Importing this module does NOT
pull in torch/transformers; it only needs typing + dataclasses, so the
type can be referenced from the FastAPI side or tests without paying the
CV deps cost.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class CVVerdict:
    """One classifier output per product."""

    category: str | None
    category_confidence: float                          # post-scaling softmax probability in [0, 1]
    category_runner_up: tuple[str, float] | None        # second-best, for debugging
    gender: str | None
    gender_confidence: float
    gender_runner_up: tuple[str, float] | None
    colors: list[tuple[str, float]] = field(default_factory=list)
    # Audit trail — what the scraper wrote into category/gender/colors BEFORE
    # this CV pass overwrote them. Populated by the reconciliation step, not
    # the model itself. See plans/cv_classify/senior_dev_v2.md §5a.
    scraper_previous: dict | None = None
    model_id: str = ""
    image_url: str = ""
    duration_ms: int = 0
