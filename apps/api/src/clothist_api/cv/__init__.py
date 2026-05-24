"""Post-ingest computer-vision classifier.

This subpackage is intentionally OUTSIDE `services/` so the FastAPI app
startup doesn't auto-import `transformers` / `torch` / `Pillow` / `numpy`.
Those deps live behind the `cv` optional-extra in pyproject.toml and only
load when `scripts/classify_products.py` is invoked.

Public surface:
  - `cv.types.CVVerdict` — per-product classification output.
  - `cv.palette.COLOR_HEX` — canonical palette loaded from
    data/taxonomy/colors.json (same source TS uses).
  - `cv.palette.delta_e_76(rgb1, rgb2)` — perceptual color distance.
  - `cv.classifier.CLIPClassifier` — the CLIP wrapper itself (instantiating
    it imports the heavy deps; importing the module does not).
  - `cv.reconcile.reconcile()` — pure-Python policy that decides whether
    CV's verdict overrides the scraper's guess. Importable without
    torch/transformers — used by both the CLI and the test suite.
"""
