"""One-shot seed enricher: infers `gender` from titles, assigns 3 color
variants per product, and writes Pollinations.ai generation URLs into
attributes.variants[].

Pollinations is a free, no-key image-generation endpoint. URL shape:
    https://image.pollinations.ai/prompt/{URL_ENCODED_PROMPT}?width=600&height=800&nologo=true&model=flux

The browser fetches these directly; the URL is the cache key. This is
seed-only — we will NOT use this at scale once real retailer scrapers run.

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

# Default secondary colors per category. The product's "primary" color is
# always added too; we don't generate a variant for whatever color is already
# the listing color (the existing image_url serves it).
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


def _infer_gender(title: str, description: str | None) -> str:
    """Return 'men' | 'women' | 'unisex' by best-effort parse of the text."""
    text = f"{title} {description or ''}".lower()
    # Strong men signals
    if re.search(r"\b(men'?s?|man'?s)\b", text):
        return "men"
    # Strong women signals
    if re.search(r"\b(women'?s?|woman'?s|ladies'?)\b", text):
        return "women"
    # Category-derived defaults
    if re.search(r"\b(dress|skirt|blouse)\b", text):
        return "women"
    return "unisex"


def _build_pollinations_url(title: str, category: str | None, color: str) -> str:
    parts = [
        f"Studio fashion product photo of a {color}",
        category[:-1] if category and category.endswith("s") else (category or "clothing item"),
        f"named '{title}'" if title else "",
        "on a plain neutral background, front-facing, e-commerce catalog shot,",
        "minimalist editorial style, soft natural lighting, sharp focus, 4k",
    ]
    prompt = " ".join(p for p in parts if p)
    return f"{POLLINATIONS_BASE}{quote(prompt)}{POLLINATIONS_PARAMS}"


def _color_variants_for(product: dict) -> list[dict]:
    """Return [{color, image_url}] including the primary color (existing image)
    plus 3 generated alternates.
    """
    primary_color = (product.get("colors") or [None])[0]
    category = product.get("category")
    title = product.get("title", "")
    out: list[dict] = []
    if primary_color and product.get("image_url"):
        out.append({"color": primary_color, "image_url": product["image_url"], "ai_generated": False})
    seen = {primary_color} if primary_color else set()
    pool = SECONDARY_COLORS_BY_CATEGORY.get(category or "", DEFAULT_SECONDARY)
    for color in pool:
        if color in seen:
            continue
        seen.add(color)
        out.append({
            "color": color,
            "image_url": _build_pollinations_url(title, category, color),
            "ai_generated": True,
        })
        if len(out) >= 4:
            break
    return out


def enrich(force: bool) -> tuple[int, int]:
    raw = json.loads(SEED_FILE.read_text())
    n_gender = 0
    n_variants = 0
    for p in raw:
        if force or not p.get("gender"):
            p["gender"] = _infer_gender(p.get("title", ""), p.get("description"))
            n_gender += 1
        attrs = p.setdefault("attributes", {})
        if force or "variants" not in attrs:
            attrs["variants"] = _color_variants_for(p)
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
