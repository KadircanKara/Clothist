"""One-shot seed enricher: infers `gender` from titles + brand cues, assigns
3 color variants per product with gender-aware Pollinations.ai prompts.

Pollinations is a free, no-key image-generation endpoint. URL shape:
    https://image.pollinations.ai/prompt/{URL_ENCODED_PROMPT}?...

This is seed-only — we will NOT use this at scale once real retailer scrapers
run.

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


def _color_variants_for(product: dict, gender: str) -> list[dict]:
    """Return [{color, image_url, ai_generated}] for the product.

    For unisex products: primary = existing Unsplash image (kept as-is),
    alternates = Pollinations.
    For gendered (men/women) products: PRIMARY is also Pollinations with a
    gender-aware prompt so the displayed model matches the catalog page.
    The original Unsplash URL is preserved on the product as
    `attributes.original_unsplash_url` for provenance / future reseed.
    """
    primary_color = (product.get("colors") or [None])[0]
    category = product.get("category")
    title = product.get("title", "")
    out: list[dict] = []

    if primary_color:
        if gender in ("men", "women"):
            # Override the primary with a gender-aware generated image so the
            # /men and /women pages never show a mis-gendered model.
            out.append({
                "color": primary_color,
                "image_url": _build_pollinations_url(title, category, primary_color, gender),
                "ai_generated": True,
            })
        elif product.get("image_url"):
            out.append({
                "color": primary_color,
                "image_url": product["image_url"],
                "ai_generated": False,
            })

    seen = {primary_color} if primary_color else set()
    pool = SECONDARY_COLORS_BY_CATEGORY.get(category or "", DEFAULT_SECONDARY)
    for color in pool:
        if color in seen:
            continue
        seen.add(color)
        out.append({
            "color": color,
            "image_url": _build_pollinations_url(title, category, color, gender),
            "ai_generated": True,
        })
        if len(out) >= 4:
            break
    return out


def enrich(force: bool) -> tuple[int, int]:
    raw = json.loads(SEED_FILE.read_text())
    n_gender = 0
    n_variants = 0
    n_primary_swapped = 0
    for p in raw:
        if force or not p.get("gender"):
            p["gender"] = _infer_gender(
                p.get("title", ""),
                p.get("description"),
                p.get("brand"),
            )
            n_gender += 1
        gender = p.get("gender", "unisex")
        attrs = p.setdefault("attributes", {})
        if force or "variants" not in attrs:
            attrs["variants"] = _color_variants_for(p, gender)
            n_variants += 1
        # For gendered products, also overwrite the top-level image_url so
        # the catalog card hero matches; preserve the original.
        if gender in ("men", "women") and attrs["variants"]:
            primary = attrs["variants"][0]
            if primary.get("ai_generated") and p.get("image_url") != primary["image_url"]:
                attrs.setdefault("original_unsplash_url", p.get("image_url"))
                p["image_url"] = primary["image_url"]
                n_primary_swapped += 1
    SEED_FILE.write_text(json.dumps(raw, indent=2) + "\n")
    print(f"Primary image swapped to gender-aware AI on {n_primary_swapped} products.")
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
