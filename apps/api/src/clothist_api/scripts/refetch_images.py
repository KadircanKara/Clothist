"""Re-fetch product primary images from Unsplash using gender-specific
queries so the visible model matches the product's gender field.

Uses the official Unsplash API at api.unsplash.com. Requires
`UNSPLASH_ACCESS_KEY` set in .env. Free tier is 50 req/hour — plenty for a
~12-product seed refresh.

For each product flagged with `gender in {'men','women'}` (or whatever the
`--genders` flag specifies), builds a query like `"woman black dress"` and
replaces image_url with the first matching hit. Also updates the first
entry of attributes.variants[] to keep the PDP gallery consistent and
flips its ai_generated back to False (it's a real photo again).

This is seed-only. Real scraped products will keep their retailer-provided
imagery.

Usage:
    uv run python -m clothist_api.scripts.refetch_images [--limit N] [--dry-run] [--genders men,women]
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
UNSPLASH_API = "https://api.unsplash.com/search/photos"
RATE_LIMIT_SECONDS = 0.4  # well under 50/hr even at this rate


_STOPWORDS = {
    "the", "a", "an", "of", "in", "and", "with", "for",
    "polartec", "tech", "fleece", "sportswear", "shop",
    "nike", "adidas", "carhartt", "patagonia", "uniqlo", "zara",
    "hm", "asos", "topshop", "mango", "champion", "arc", "teryx",
    "beta", "detroit", "ar", "tnf", "north", "face", "wolf", "tree",
}


def _query_for(product: dict, fallback: bool = False) -> str:
    gender = product.get("gender", "unisex")
    category = product.get("category") or "clothing"
    # Singularize for cleaner photo queries ("hoodies" → "hoodie").
    if category.endswith("s") and not category.endswith("ss"):
        category = category[:-1]
    color = (product.get("colors") or [""])[0]
    audience = {"men": "man", "women": "woman"}.get(gender, "")
    if fallback:
        # Simplest possible query — gender + color + category.
        return " ".join(p for p in (audience, color, category) if p)
    title = product.get("title", "")
    title_words = re.findall(r"\b[a-zA-Z]+\b", title.lower())
    title_keep = [w for w in title_words if w not in _STOPWORDS and len(w) > 2][:2]
    parts = [audience, color, category, *title_keep]
    return " ".join(p for p in parts if p)


def _to_cdn(raw_url: str) -> str:
    """Strip Unsplash's caller transform params and rebuild with our sizing.

    Unsplash CDN URLs follow `https://images.unsplash.com/photo-XXXX?...` —
    we keep the base photo identifier and pin our preferred dimensions.
    """
    base = raw_url.split("?")[0]
    return f"{base}?w=600&h=800&fit=crop&auto=format&q=75"


def fetch_one(client: httpx.Client, access_key: str, query: str) -> str | None:
    try:
        r = client.get(
            UNSPLASH_API,
            params={"query": query, "per_page": 5, "page": 1, "orientation": "portrait"},
            headers={
                "Accept-Version": "v1",
                "Authorization": f"Client-ID {access_key}",
            },
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        for hit in (data.get("results") or []):
            urls = hit.get("urls") or {}
            full = urls.get("regular") or urls.get("full") or urls.get("small")
            if full:
                return _to_cdn(full)
        return None
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 403:
            print(
                f"  ! Unsplash 403 (rate limit or invalid key) on '{query}'",
                file=sys.stderr,
            )
        else:
            print(
                f"  ! Unsplash {e.response.status_code} on '{query}': "
                f"{e.response.text[:120]}",
                file=sys.stderr,
            )
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

    access_key = get_settings().unsplash_access_key
    if not access_key:
        print(
            "ERROR: UNSPLASH_ACCESS_KEY is not set in .env. "
            "Get a free key at https://unsplash.com/developers.",
            file=sys.stderr,
        )
        return 2

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
            url = fetch_one(client, access_key, q)
            if not url:
                q2 = _query_for(p, fallback=True)
                if q2 != q:
                    time.sleep(RATE_LIMIT_SECONDS)
                    url = fetch_one(client, access_key, q2)
                    if url:
                        print(f"  ✓ {p['retailer_product_id']:32}  (fallback) '{q2}'")
                        q = q2
            if not url:
                print(f"  - {p['retailer_product_id']:32}  no hit for '{q}'")
                continue
            if q == _query_for(p):
                print(f"  ✓ {p['retailer_product_id']:32}  '{q}'")
            if not args.dry_run:
                # Stash provenance only the first time we swap (don't overwrite
                # an Unsplash original with another Unsplash original).
                attrs = p.setdefault("attributes", {})
                if attrs.get("variants") and attrs["variants"][0].get("ai_generated"):
                    # We're replacing an AI-generated primary with a real photo.
                    pass
                elif p.get("image_url") and "original_unsplash_url" not in attrs:
                    attrs["original_unsplash_url"] = p["image_url"]

                p["image_url"] = url
                if attrs.get("variants"):
                    attrs["variants"][0]["image_url"] = url
                    attrs["variants"][0]["ai_generated"] = False
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
