"""Shared normalization helpers — category alias map, gender canonicalization,
HTML stripping. Used by every Shopify adapter.

The category alias map lives here (not in each adapter) so when a vendor adds
a new product type we extend the map once and every source benefits.
"""
from __future__ import annotations

import re
from typing import Literal

from selectolax.parser import HTMLParser

Gender = Literal["men", "women", "unisex"]


# Canonical 10-token taxonomy (matches the seed corpus).
CANONICAL_CATEGORIES = frozenset({
    "hoodies", "tshirts", "pants", "jeans", "shorts",
    "skirts", "dresses", "jackets", "sneakers", "sweaters",
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
    "sweatshirt": "hoodies", "sweatshirts": "hoodies",
    "hoodie": "hoodies", "hoodies": "hoodies",
    "pullover": "hoodies", "pullovers": "hoodies",
    "sweater": "sweaters", "sweaters": "sweaters",
    "cardigan": "sweaters", "cardigans": "sweaters",
    "knit": "sweaters", "knits": "sweaters", "knitwear": "sweaters",
    "shirt": "tshirts", "shirts": "tshirts",  # button-up shirts; conflates with tees but workable
    "top": "tshirts", "tops": "tshirts",
    "blouse": "tshirts", "blouses": "tshirts",
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
    # Footwear — boots & flats roll under sneakers for the MVP taxonomy
    "sneaker": "sneakers", "sneakers": "sneakers",
    "shoe": "sneakers", "shoes": "sneakers",
    "boot": "sneakers", "boots": "sneakers",
    "flat": "sneakers", "flats": "sneakers",
    "sandal": "sneakers", "sandals": "sneakers",
    "loafer": "sneakers", "loafers": "sneakers",
    "trainer": "sneakers", "trainers": "sneakers",
    "runner": "sneakers", "runners": "sneakers",
}


def normalize_category(product_type: str | None) -> str | None:
    """Return the canonical category token for a vendor `product_type`, or
    None if no alias matches (caller logs an alias miss).
    """
    if not product_type:
        return None
    key = product_type.lower().strip()
    if key in CATEGORY_ALIASES:
        return CATEGORY_ALIASES[key]
    # Substring search — many vendors use multi-word product types
    # ("Women's Midi Dresses", "Tech Pack Tee").
    for alias, canonical in CATEGORY_ALIASES.items():
        if alias in key:
            return canonical
    return None


# Gender canonicalization — handles common vendor spellings.
GENDER_ALIASES: dict[str, Gender] = {
    "men": "men", "mens": "men", "men's": "men", "man": "men", "male": "men",
    "guys": "men", "guy": "men",
    "women": "women", "womens": "women", "women's": "women", "woman": "women",
    "female": "women", "ladies": "women", "ladies'": "women",
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
