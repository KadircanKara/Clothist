"""Fetch alternate-color variant images from Unsplash for every product
that doesn't already have them, downloading to apps/web/public/variants/
and rewriting seed-file URLs to local paths.

Pollinations.ai monetized after the seed was first built, so the
previously-generated variant URLs all return 402. This script switches the
variant source to Unsplash via the official API (UNSPLASH_ACCESS_KEY in
.env). Free tier is 50 req/hr — the script throttles, saves progress
incrementally, and stops gracefully on rate-limit so a re-run picks up
where it left off.

Usage:
    uv run python -m clothist_api.scripts.fetch_variant_images \\
        [--variants-per-product N] [--max-requests N] [--throttle-seconds S]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

import httpx

from clothist_api.settings import get_settings

SEED_FILE = Path(__file__).resolve().parents[5] / "data" / "seed" / "products.json"
PUBLIC_DIR = Path(__file__).resolve().parents[5] / "apps" / "web" / "public" / "variants"
UNSPLASH_API = "https://api.unsplash.com/search/photos"

# Default alternates per category — picked to look distinct from typical
# primary listing colors.
SECONDARY_COLORS_BY_CATEGORY: dict[str, list[str]] = {
    "hoodies": ["black", "cream", "navy"],
    "tshirts": ["white", "black", "olive"],
    "pants": ["khaki", "black", "stone"],
    "jeans": ["indigo", "black", "stone-wash"],
    "shorts": ["black", "olive", "stone"],
    "skirts": ["black", "cream", "tan"],
    "dresses": ["black", "cream", "rust"],
    "jackets": ["black", "olive", "tan"],
    "footwear": ["white", "black", "grey"],
    "sweaters": ["cream", "navy", "rust"],
}
DEFAULT_ALTERNATES = ["black", "cream", "navy"]


def _filename_for(retailer_product_id: str, color: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", color.lower()).strip("-") or "color"
    return f"{retailer_product_id}_{slug}.jpg"


def _query_for(product: dict, color: str) -> str:
    gender = product.get("gender", "unisex")
    category = product.get("category") or "clothing"
    if category.endswith("s") and not category.endswith("ss"):
        category = category[:-1]
    audience = {"men": "man", "women": "woman"}.get(gender, "")
    return " ".join(p for p in (audience, color, category) if p)


def _to_cdn(raw_url: str) -> str:
    base = raw_url.split("?")[0]
    return f"{base}?w=600&h=800&fit=crop&auto=format&q=75"


def _save_seed(raw: list[dict]) -> None:
    SEED_FILE.write_text(json.dumps(raw, indent=2) + "\n")


def fetch_one(
    client: httpx.Client, access_key: str, query: str
) -> tuple[str | None, bool]:
    """Returns (url, rate_limited)."""
    try:
        r = client.get(
            UNSPLASH_API,
            params={"query": query, "per_page": 3, "page": 1, "orientation": "portrait"},
            headers={
                "Accept-Version": "v1",
                "Authorization": f"Client-ID {access_key}",
            },
            timeout=15,
        )
        if r.status_code == 403:
            return (None, True)
        r.raise_for_status()
        for hit in (r.json().get("results") or []):
            urls = hit.get("urls") or {}
            full = urls.get("regular") or urls.get("full") or urls.get("small")
            if full:
                return (_to_cdn(full), False)
        return (None, False)
    except httpx.HTTPError as e:
        print(f"  ! '{query}': {e}", file=sys.stderr)
        return (None, False)


def download_to(client: httpx.Client, url: str, dest: Path) -> bool:
    try:
        r = client.get(url, timeout=30, follow_redirects=True)
        r.raise_for_status()
        if len(r.content) < 1000:
            return False
        tmp = dest.with_suffix(".tmp")
        tmp.write_bytes(r.content)
        tmp.replace(dest)
        return True
    except (httpx.HTTPError, OSError) as e:
        print(f"  ! download {dest.name}: {e}", file=sys.stderr)
        return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variants-per-product", type=int, default=2)
    parser.add_argument("--max-requests", type=int, default=48)
    parser.add_argument("--throttle-seconds", type=float, default=1.5)
    args = parser.parse_args()

    access_key = get_settings().unsplash_access_key
    if not access_key:
        print("ERROR: UNSPLASH_ACCESS_KEY is not set in .env", file=sys.stderr)
        return 2

    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    raw = json.loads(SEED_FILE.read_text())

    # Plan: for each product, ensure it has at least N variants. The first
    # variant (primary) is kept as-is; we top up with alternates.
    work: list[tuple[dict, str]] = []
    for p in raw:
        attrs = p.setdefault("attributes", {})
        variants = attrs.setdefault("variants", [])
        existing_colors = {v["color"] for v in variants}
        category = p.get("category")
        pool = SECONDARY_COLORS_BY_CATEGORY.get(category or "", DEFAULT_ALTERNATES)
        needed = max(0, args.variants_per_product - len(variants))
        added = 0
        for color in pool:
            if color in existing_colors:
                continue
            work.append((p, color))
            existing_colors.add(color)
            added += 1
            if added >= needed:
                break

    print(f"Planned: {len(work)} variant fetches (budget {args.max_requests})")

    n_fetched = 0
    n_saved = 0
    rate_limited = False
    with httpx.Client(follow_redirects=True) as client:
        for product, color in work:
            if n_fetched >= args.max_requests or rate_limited:
                break
            q = _query_for(product, color)
            dest = PUBLIC_DIR / _filename_for(product["retailer_product_id"], color)
            if dest.exists():
                # Already on disk from a prior run; just register in variants.
                pass
            else:
                url, rl = fetch_one(client, access_key, q)
                n_fetched += 1
                if rl:
                    print("  ! Unsplash rate-limited. Stopping.")
                    rate_limited = True
                    break
                if not url:
                    print(f"  - {product['retailer_product_id']:32}  no hit for '{q}'")
                    time.sleep(args.throttle_seconds)
                    continue
                if not download_to(client, url, dest):
                    time.sleep(args.throttle_seconds)
                    continue

            # Register or update the variant entry.
            attrs = product["attributes"]
            local_url = f"/variants/{dest.name}"
            variants: list[dict] = attrs.get("variants") or []
            existing = next((v for v in variants if v["color"] == color), None)
            if existing:
                existing["image_url"] = local_url
                existing["ai_generated"] = False
            else:
                variants.append({"color": color, "image_url": local_url, "ai_generated": False})
            attrs["variants"] = variants
            # Sync product.colors[] union
            seen: list[str] = []
            for c in [*(product.get("colors") or []), *(v["color"] for v in variants)]:
                if c and c not in seen:
                    seen.append(c)
            product["colors"] = seen

            n_saved += 1
            print(f"  ✓ {product['retailer_product_id']:32}  {color:8}  '{q}'")
            # Checkpoint every 5 successful saves so a crash doesn't lose progress.
            if n_saved % 5 == 0:
                _save_seed(raw)
            time.sleep(args.throttle_seconds)

    _save_seed(raw)
    print(f"Fetched {n_fetched} Unsplash queries, saved {n_saved} variants. ")
    print("Re-run to fill more — each run picks up where the last left off.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
