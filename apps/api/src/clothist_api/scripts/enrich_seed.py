"""One-shot seed enricher: infers `gender` from titles + brand cues, then
seeds a single primary variant entry per product. Multi-color variants are
populated separately by `fetch_variant_images.py` (which hits Unsplash via
the official API).

History: this script used to generate Pollinations.ai URLs for alternate
colors, but Pollinations monetized after the initial seed and now returns
402. Pollinations references were stripped on 2026-05-24. To regenerate
alternate-color variants, use `fetch_variant_images.py` instead.

Usage:
    uv run python -m clothist_api.scripts.enrich_seed [--force]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import quote

SEED_FILE = Path(__file__).resolve().parents[5] / "data" / "seed" / "products.json"

POLLINATIONS_BASE = "https://image.pollinations.ai/prompt/"
POLLINATIONS_PARAMS = "?width=600&height=800&nologo=true&model=flux"

SECONDARY_COLORS_BY_CATEGORY: dict[str, list[str]] = {
    "hoodies": ["black", "cream", "navy"],
    "tshirts": ["white", "black", "olive"],
    "pants": ["khaki", "black", "stone"],
    "jeans": ["indigo", "black", "stone-wash"],
    "shorts": ["black", "olive", "stone"],
    "skirts": ["black", "cream", "tan"],
    "dresses": ["black", "cream", "rust"],
    "jackets": ["black", "olive", "tan"],
    "sneakers": ["white", "black", "grey"],
    "sweaters": ["cream", "navy", "rust"],
}
DEFAULT_SECONDARY = ["black", "cream", "navy"]

# Gender inference — applied in order; first match wins.
_GENDER_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(men'?s|man'?s|mens|guys?)\b", re.I), "men"),
    (re.compile(r"\b(women'?s|woman'?s|womens|ladies'?|girls?'?)\b", re.I), "women"),
    # Categories that are essentially women-coded across the seed corpus
    (re.compile(r"\b(dress|midi|maxi|skirt|blouse|crop\s*top)\b", re.I), "women"),
    # Brand + product cues — Nike Tech, Carhartt, Patagonia heavy gear lean men;
    # Aritzia, Mango, Topshop lean women.
    (re.compile(r"\b(carhartt|tech\s*fleece|cargo|workwear|polartec|arc'?teryx)\b", re.I), "men"),
    (re.compile(r"\b(aritzia|topshop|mango)\b", re.I), "women"),
]


def _infer_gender(title: str, description: str | None, brand: str | None) -> str:
    text = " ".join([title, description or "", brand or ""])
    for rule, gender in _GENDER_RULES:
        if rule.search(text):
            return gender
    return "unisex"


def _model_prompt_for(gender: str) -> str:
    """Phrase fragment used in the Pollinations prompt so generated images
    match the product's gender (and the page they'll appear on)."""
    if gender == "men":
        return "worn by a male model"
    if gender == "women":
        return "worn by a female model"
    return "presented as a flat-lay studio shot with no person"


def _build_pollinations_url(title: str, category: str | None, color: str, gender: str) -> str:
    cat_singular = category[:-1] if category and category.endswith("s") else (category or "clothing item")
    model_phrase = _model_prompt_for(gender)
    parts = [
        f"Editorial fashion product photo of a {color}",
        cat_singular,
        f"named '{title}',",
        model_phrase + ",",
        "studio backdrop, soft natural lighting, e-commerce catalog framing,",
        "minimalist composition, sharp focus, 4k",
    ]
    prompt = " ".join(p for p in parts if p)
    return f"{POLLINATIONS_BASE}{quote(prompt)}{POLLINATIONS_PARAMS}"


def _primary_variant_for(product: dict) -> dict | None:
    """Return the single primary variant entry: the product's existing
    listing image, keyed by its first color. Alternate colors are added
    by fetch_variant_images.py.
    """
    primary_color = (product.get("colors") or [None])[0]
    if not (primary_color and product.get("image_url")):
        return None
    return {
        "color": primary_color,
        "image_url": product["image_url"],
        "ai_generated": False,
    }


def enrich(force: bool) -> tuple[int, int]:
    raw = json.loads(SEED_FILE.read_text())
    n_gender = 0
    n_variants = 0
    for p in raw:
        if force or not p.get("gender"):
            p["gender"] = _infer_gender(
                p.get("title", ""),
                p.get("description"),
                p.get("brand"),
            )
            n_gender += 1
        attrs = p.setdefault("attributes", {})
        if force or "variants" not in attrs or not attrs["variants"]:
            primary = _primary_variant_for(p)
            attrs["variants"] = [primary] if primary else []
            n_variants += 1
    SEED_FILE.write_text(json.dumps(raw, indent=2) + "\n")
    return n_gender, n_variants


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="overwrite existing fields")
    args = parser.parse_args()
    n_gender, n_variants = enrich(args.force)
    print(f"Updated gender on {n_gender} products, variants on {n_variants} products.")
    print(f"Wrote {SEED_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
