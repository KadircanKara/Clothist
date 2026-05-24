"""Shared normalization helpers — category alias map, gender canonicalization,
HTML stripping. Used by every Shopify adapter.

The category alias map lives here (not in each adapter) so when a vendor adds
a new product type we extend the map once and every source benefits.
"""
from __future__ import annotations

import re
from functools import lru_cache
from typing import Literal

from selectolax.parser import HTMLParser

Gender = Literal["men", "women", "unisex"]


# Canonical taxonomy. Extended from the original 10-token seed corpus with
# 3 categories that real Shopify retailers heavily populate:
#   - accessories (hats, bags, belts, jewelry, sunglasses, wallets)
#   - swimwear (bikinis, swim shorts/tops)
#   - underwear (briefs, boxers, lingerie, bras)
CANONICAL_CATEGORIES = frozenset({
    "hoodies", "sweatshirts", "tshirts", "pants", "jeans", "shorts",
    "skirts", "dresses", "jackets", "footwear", "sweaters",
    "accessories", "swimwear", "underwear",
    # Vendor product_type didn't map AND the title wasn't flagged as
    # non-clothing. Expected to be tiny — every storefront we ingest
    # already tags product_type. Renamed from "other" 2026-05-25 to
    # match the simplified vendor-only pipeline.
    "uncategorized",
    # Items detected as non-clothing (flasks, cigar cutters, ceramic
    # homewares, golf gear, model sailboats, paper fans). The search API
    # filters these out by default; they exist in the DB so a future
    # re-classification can move them back if the detection improves.
    # See services/text_categorize.py:NON_CLOTHING_TOKENS.
    "excluded",
})


# Vendor-string → canonical-token. Keys are lowercased. Match order:
#   1. Direct hit on the lowercased product_type.
#   2. Any alias substring present in the lowercased product_type.
# Misses fall through to `category = None` and the raw string lands on
# `attributes.raw_category` for review.
CATEGORY_ALIASES: dict[str, str] = {
    # Tops
    "tee": "tshirts", "tees": "tshirts", "t-shirt": "tshirts", "t-shirts": "tshirts",
    "tshirt": "tshirts", "tshirts": "tshirts",
    "tank": "tshirts", "tank top": "tshirts", "tank tops": "tshirts",
    "polo": "tshirts", "polos": "tshirts",
    # Sweatshirts and hoodies are now separate canonical buckets — vendor
    # tagging treats them distinctly (a crewneck sweatshirt is not a hood),
    # so we honor that on the filter UI.
    "sweatshirt": "sweatshirts", "sweatshirts": "sweatshirts",
    "crewneck sweatshirt": "sweatshirts",
    "hoodie": "hoodies", "hoodies": "hoodies",
    "pullover": "hoodies", "pullovers": "hoodies",
    "sweater": "sweaters", "sweaters": "sweaters",
    "cardigan": "sweaters", "cardigans": "sweaters",
    "knit": "sweaters", "knits": "sweaters", "knitwear": "sweaters",
    "jumper": "sweaters", "jumpers": "sweaters",        # UK English for sweater
    "pullover": "sweaters", "pullovers": "sweaters",
    "shirt": "tshirts", "shirts": "tshirts",  # button-up shirts; conflates with tees but workable
    "top": "tshirts", "tops": "tshirts",
    "blouse": "tshirts", "blouses": "tshirts",
    "crewneck": "tshirts", "crewnecks": "tshirts",  # crewneck-tee cut
    # Bottoms
    "pant": "pants", "pants": "pants",
    "trouser": "pants", "trousers": "pants",
    "chino": "pants", "chinos": "pants",
    "jogger": "pants", "joggers": "pants",
    "track pant": "pants", "track pants": "pants",
    "sweatpant": "pants", "sweatpants": "pants",
    "leggings": "pants",
    "jean": "jeans", "jeans": "jeans", "denim": "jeans",
    "short": "shorts", "shorts": "shorts",
    "skirt": "skirts", "skirts": "skirts",
    "midi skirt": "skirts", "maxi skirt": "skirts", "mini skirt": "skirts",
    "dress": "dresses", "dresses": "dresses",
    "midi dress": "dresses", "maxi dress": "dresses", "mini dress": "dresses",
    "gown": "dresses", "gowns": "dresses",
    # Outerwear
    "jacket": "jackets", "jackets": "jackets",
    "coat": "jackets", "coats": "jackets",
    "outerwear": "jackets",
    "suiting": "jackets",
    "blazer": "jackets", "blazers": "jackets",
    "vest": "jackets", "vests": "jackets",
    "parka": "jackets",
    # Footwear — boots & flats roll under footwear for the MVP taxonomy
    "sneaker": "footwear", "footwear": "footwear",
    "shoe": "footwear", "shoes": "footwear",
    "boot": "footwear", "boots": "footwear",
    "flat": "footwear", "flats": "footwear",
    "sandal": "footwear", "sandals": "footwear",
    "loafer": "footwear", "loafers": "footwear",
    "trainer": "footwear", "trainers": "footwear",
    "runner": "footwear", "runners": "footwear",
    "espadrille": "footwear", "espadrilles": "footwear",
    "mary jane": "footwear", "ballerina": "footwear", "ballerinas": "footwear",
    "clog": "footwear", "clogs": "footwear",
    "heel": "footwear", "heels": "footwear",
    "high top": "footwear", "high tops": "footwear",
    "low top": "footwear", "low tops": "footwear",
    "slide": "footwear", "slides": "footwear",
    # Accessories — bags, hats, belts, eyewear, jewelry, wallets
    "accessories": "accessories", "accessory": "accessories",
    "bag": "accessories", "bags": "accessories",
    "tote": "accessories", "totes": "accessories",
    "backpack": "accessories", "backpacks": "accessories",
    "sling": "accessories", "duffel": "accessories",
    "clutch": "accessories", "clutches": "accessories",
    "pouch": "accessories", "pouches": "accessories",
    "wallet": "accessories", "wallets": "accessories",
    "cardholder": "accessories", "cardholders": "accessories",
    "hat": "accessories", "hats": "accessories",
    "cap": "accessories", "caps": "accessories",
    "beanie": "accessories", "beanies": "accessories",
    "bucket hat": "accessories", "snapback": "accessories",
    "belt": "accessories", "belts": "accessories",
    "sunglasses": "accessories", "eyewear": "accessories",
    "scarf": "accessories", "scarves": "accessories",
    "necklace": "accessories", "necklaces": "accessories",
    "earring": "accessories", "earrings": "accessories",
    "ring": "accessories", "rings": "accessories",
    "bracelet": "accessories", "bracelets": "accessories",
    "charm": "accessories", "charms": "accessories",
    "jewelry": "accessories", "jewellery": "accessories",
    "pendant": "accessories", "pendants": "accessories",
    "leather goods": "accessories",
    "soft goods": "accessories",
    # Swimwear — bikinis, swim shorts, swim tops
    "swim": "swimwear", "swimwear": "swimwear", "swimsuit": "swimwear",
    "bikini": "swimwear", "bikinis": "swimwear",
    "bikini top": "swimwear", "bikini tops": "swimwear",
    "bikini bottom": "swimwear", "bikini bottoms": "swimwear",
    "one-piece": "swimwear", "one piece": "swimwear",
    "swim short": "swimwear", "swim shorts": "swimwear",
    # Underwear — briefs, boxers, bras, lingerie
    "underwear": "underwear",
    "brief": "underwear", "briefs": "underwear",
    "boxer": "underwear", "boxers": "underwear",
    "bra": "underwear", "bras": "underwear",
    "bralette": "underwear", "lingerie": "underwear",
    "panty": "underwear", "panties": "underwear",
    "thong": "underwear", "thongs": "underwear",
    "intimate": "underwear", "intimates": "underwear",
    "sock": "underwear", "socks": "underwear",  # bundle socks into underwear vs accessories
    # Rompers & playsuits — fold into dresses (they're whole-body women's pieces)
    "romper": "dresses", "rompers": "dresses",
    "playsuit": "dresses", "playsuits": "dresses",
    "jumpsuit": "dresses", "jumpsuits": "dresses",
    "shortall": "dresses", "shortalls": "dresses",
    "coverall": "dresses", "coveralls": "dresses",
    "onesie": "dresses", "onesies": "dresses",
    "one piece": "dresses", "one pieces": "dresses",
    "one-piece": "dresses", "one-pieces": "dresses",
    # Misc remaining
    "jersey": "tshirts", "jerseys": "tshirts",  # team jerseys = oversized tees
}

# Categories whose presence implies a gender even when tags don't say so.
# Used as a last-step inference after vendor/tag/title scans yielded nothing
# more specific.
CATEGORY_IMPLIED_GENDER: dict[str, str] = {
    "dresses": "women",   # incl. rompers/playsuits/jumpsuits via alias
    "skirts": "women",
    "swimwear": "women",  # weak — many stores DO carry men's swim, but ours
                          # mostly Kith's "Kith Women X Bikini" line
}


def normalize_category(product_type: str | None) -> str | None:
    """Return the canonical category token for a vendor `product_type`, or
    None if no alias matches.

    Matching uses whole-word boundaries (not raw substring), then picks
    the LATEST-ending match — the head noun of an English noun phrase
    typically lives at the end. Length tie-break.

    Why both rules matter:
      - whole-word: "Short Sleeve Tees" must not return shorts via the
        substring "short". With boundaries, "short" doesn't match a
        token of the phrase ("short" the standalone word IS however
        present in "Shorts" — separate case).
      - last-position: "Mini Skirt" and "skirt" both match; we want
        "skirt" via the multi-word "mini skirt" mapping. Latest-ending
        beats earlier matches.
      - length tiebreak: "tank top" and "top" both end at the same
        position; longer alias wins so the more specific phrase routes.
    """
    if not product_type:
        return None
    key = product_type.lower().strip()
    if key in CATEGORY_ALIASES:
        return CATEGORY_ALIASES[key]

    # Find every alias that matches as a whole-word span. Collect
    # (end_pos, alias_length, canonical) and pick latest-ending +
    # longest. Mirrors text_categorize.categorize_by_text's tournament.
    matches: list[tuple[int, int, str]] = []
    for alias in CATEGORY_ALIASES:
        pat = _alias_re(alias)
        for m in pat.finditer(key):
            matches.append((m.end(), len(alias), CATEGORY_ALIASES[alias]))
    if not matches:
        return None
    matches.sort(key=lambda t: (t[0], t[1]))
    return matches[-1][2]


@lru_cache(maxsize=None)
def _alias_re(alias: str) -> "re.Pattern[str]":
    # Word-boundary regex per alias. Cached so repeated calls don't
    # recompile. `re.escape` handles "high top" / "t-shirt" / "button-up"
    # safely.
    return re.compile(rf"(?<!\w){re.escape(alias)}(?!\w)", re.IGNORECASE)


# Gender canonicalization — handles common vendor spellings.
# Includes industry-standard "WMNS" (Nike/Jordan/adidas footwear) and "MNS".
GENDER_ALIASES: dict[str, Gender] = {
    "men": "men", "mens": "men", "men's": "men", "man": "men", "male": "men",
    "guys": "men", "guy": "men", "mns": "men",
    "women": "women", "womens": "women", "women's": "women", "woman": "women",
    "female": "women", "ladies": "women", "ladies'": "women", "wmns": "women",
    "girls": "women", "girl": "women",
    "unisex": "unisex", "uni": "unisex", "neutral": "unisex",
    "all-gender": "unisex", "any": "unisex",
}


def normalize_gender(raw: str | None) -> Gender | None:
    """Map a vendor gender string to our canonical set. Returns None if no
    match (caller may apply an adapter-level `assume_gender` fallback).
    """
    if not raw:
        return None
    return GENDER_ALIASES.get(raw.lower().strip())


_WHITESPACE_RE = re.compile(r"\s+")


def strip_html(html: str | None, *, max_chars: int = 600) -> str | None:
    """Extract plain text from `body_html`, collapse whitespace, and trim to
    `max_chars`. Returns None if the input is empty or trims to nothing.
    """
    if not html:
        return None
    text = HTMLParser(html).text(separator=" ", strip=True)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    if not text:
        return None
    if len(text) > max_chars:
        text = text[: max_chars - 1].rstrip() + "…"
    return text


# Common color synonyms — vendors use varied vocabulary; we collapse to a
# single canonical token. Keys are lowercased substrings present in vendor
# option values.
_COLOR_CANONICAL: dict[str, str] = {
    "black": "black",
    "white": "white", "ivory": "white", "snow": "white", "off-white": "white",
    "cream": "cream", "ecru": "cream", "natural": "cream", "oat": "cream",
    "grey": "grey", "gray": "grey", "charcoal": "charcoal", "heather": "grey",
    "navy": "navy", "midnight": "navy",
    "blue": "blue", "denim": "blue", "indigo": "indigo", "cobalt": "blue",
    "light blue": "light-blue", "sky": "light-blue", "powder": "light-blue",
    "green": "green", "forest": "forest", "olive": "olive", "khaki": "khaki",
    "sage": "green",
    "red": "red", "burgundy": "burgundy", "wine": "burgundy", "crimson": "red",
    "rust": "rust", "terracotta": "rust",
    "orange": "orange",
    "yellow": "yellow", "gold": "gold",
    "pink": "pink", "blush": "pink", "rose": "pink",
    "purple": "purple", "violet": "purple", "lavender": "purple",
    "brown": "brown", "chocolate": "brown",
    "tan": "tan", "camel": "camel", "beige": "beige", "sand": "sand",
    "stone": "stone",
}


def normalize_color(raw: str | None) -> str | None:
    """Compress a vendor color string (e.g. "Heathered Onyx") to a canonical
    token in our palette. Returns lowercase original if nothing matches.
    """
    if not raw:
        return None
    key = raw.lower().strip()
    if not key or key in ("default", "default title"):
        return None
    # Direct hit
    if key in _COLOR_CANONICAL:
        return _COLOR_CANONICAL[key]
    # Substring scan — descriptive colors like "Heathered Onyx" → "onyx"-ish.
    # First, look for the longest matching substring (so "light blue" beats "blue").
    matches = sorted(
        (alias for alias in _COLOR_CANONICAL if alias in key),
        key=len,
        reverse=True,
    )
    if matches:
        return _COLOR_CANONICAL[matches[0]]
    # Fallback — strip punctuation/whitespace, keep first 24 chars.
    cleaned = re.sub(r"[^a-z0-9-]+", "-", key).strip("-")
    return cleaned[:24] or None
