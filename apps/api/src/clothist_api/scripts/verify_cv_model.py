"""Pre-flight: download the CLIP model + run one smoke classification.

Run this once after `uv sync --extra cv` and before the first
`classify_products.py` invocation. It blocks for ~5 minutes on the first
run (downloading ~600 MB) and ~5 seconds on subsequent runs (cache hit).

Usage:
    uv run python -m clothist_api.scripts.verify_cv_model [--model X]
"""
from __future__ import annotations

import argparse
import io
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="openai/clip-vit-base-patch32")
    args = parser.parse_args()

    try:
        from PIL import Image  # noqa: F401
        import torch  # noqa: F401
        from transformers import CLIPModel, CLIPProcessor  # noqa: F401
    except ImportError as e:
        print(
            f"ERROR: CV deps not installed: {e}.\n"
            "Run `uv sync --extra cv` first.",
            file=sys.stderr,
        )
        return 2

    print(f"Loading {args.model} (this may take ~5 min on first run)…")
    from clothist_api.cv.classifier import CLIPClassifier
    clf = CLIPClassifier(model_id=args.model)
    print(f"OK — device={clf._device} logit_scale={clf.logit_scale:.2f}")

    # Smoke-classify a synthesized 224×224 solid-black image.
    from PIL import Image as PILImage
    img = PILImage.new("RGB", (224, 224), color=(10, 10, 10))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    verdicts = clf.classify_batch([img], ["synth://solid-black"], [buf.getvalue()])
    v = verdicts[0]
    print(
        f"Smoke verdict: category={v.category} ({v.category_confidence:.2f}) "
        f"gender={v.gender} ({v.gender_confidence:.2f}) "
        f"colors={[(c, round(p, 2)) for c, p in v.colors]}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
