"""Re-fetch product primary images from Unsplash using gender-specific
queries so the visible model matches the product's gender field.

Hits the public unsplash.com/napi/search/photos endpoint (no auth). For each
product flagged with `gender in {'men','women'}`, builds a query like
`"women black dress"` and replaces image_url with the first hit. Also
updates the first entry of attributes.variants[] to keep the PDP gallery
consistent.

This is seed-only. Real scraped products will keep their retailer-provided
imagery.

Usage:
    uv run python -m clothist_api.scripts.refetch_images [--limit N] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

import httpx

SEED_FILE = Path(__file__).resolve().parents[5] / "data" / "seed" / "products.json"
UNSPLASH_NAPI = "https://unsplash.com/napi/search/photos"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
RATE_LIMIT_SECONDS = 0.6  # be polite


def _query_for(product: dict) -> str:
    gender = product.get("gender", "unisex")
    category = product.get("category") or "clothing"
    color = (product.get("colors") or [""])[0]
    title = product.get("title", "")
    # Strip likely brand-name noise from the title for a more visual query.
    title_words = re.findall(r"\b[a-zA-Z]+\b", title.lower())
    title_keep = [
        w for w in title_words
        if w not in {
            "the", "a", "an", "of", "in", "and", "with", "for",
            "polartec", "tech", "fleece", "sportswear", "shop",
        }
        and len(w) > 2
    ][:3]
    audience = {"men": "male model", "women": "female model"}.get(gender, "model")
    # E.g. "female model black dress linen midi"
    parts = [audience, color, category, *title_keep]
    return " ".join(p for p in parts if p)


def _to_cdn(raw_url: str) -> str:
    """Strip Unsplash query string and rebuild with our preferred sizing."""
    # The CDN base is images.unsplash.com/photo-XXXX.jpg; keep that, drop the
    # caller's transform params and append our own.
    base = raw_url.split("?")[0]
    return f"{base}?w=600&h=800&fit=crop&auto=format&q=75"


def fetch_one(client: httpx.Client, query: str) -> str | None:
    try:
        r = client.get(
            UNSPLASH_NAPI,
            params={"query": query, "per_page": 5, "page": 1, "orientation": "portrait"},
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
                "Referer": "https://unsplash.com/s/photos",
            },
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        results = data.get("results") or []
        if not results:
            return None
        # Pick the first one whose alt text doesn't conflict obviously
        for hit in results:
            urls = hit.get("urls") or {}
            full = urls.get("regular") or urls.get("full") or urls.get("small")
            if full:
                return _to_cdn(full)
        return None
    except httpx.HTTPError as e:
        print(f"  ! httpx error on '{query}': {e}", file=sys.stderr)
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="cap how many products to refetch (0 = all)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--genders", default="men,women", help="comma-separated gender filter")
    args = parser.parse_args()

    raw = json.loads(SEED_FILE.read_text())
    wanted = set(g.strip() for g in args.genders.split(",") if g.strip())
    targets = [p for p in raw if p.get("gender") in wanted]
    if args.limit:
        targets = targets[: args.limit]
    print(f"Re-fetching {len(targets)} product(s) where gender in {wanted}")

    n_updated = 0
    with httpx.Client(http2=False, follow_redirects=True) as client:
        for p in targets:
            q = _query_for(p)
            url = fetch_one(client, q)
            if not url:
                print(f"  - {p['retailer_product_id']:32}  no hit for '{q}'")
                continue
            print(f"  ✓ {p['retailer_product_id']:32}  {q}")
            if not args.dry_run:
                p["image_url"] = url
                variants = (p.get("attributes") or {}).get("variants") or []
                if variants and not variants[0].get("ai_generated"):
                    variants[0]["image_url"] = url
                n_updated += 1
            time.sleep(RATE_LIMIT_SECONDS)

    if not args.dry_run:
        SEED_FILE.write_text(json.dumps(raw, indent=2) + "\n")
        print(f"Updated {n_updated} products in {SEED_FILE}")
    else:
        print("(dry run — no changes written)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
