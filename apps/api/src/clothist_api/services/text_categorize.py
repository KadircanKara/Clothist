"""Title-based product categorization with confidence.

The first stage of the cascading hybrid categorizer. Pure-Python, sub-ms
per product — runs synchronously over the entire batch before any LLM or
CV call is made. Products that hit the 0.95 confidence threshold here
skip the LLM stage entirely (saves a Groq call) and CV's category vote
is ignored downstream.

Why not just reuse scrapers/normalize.py:normalize_category?
  - That function reads the vendor's `product_type` string, which is often
    wrong or missing (an ALD "Striped Beach Towel" comes back as product
    type "Top" → tshirts, by way of the alias scan, despite being a towel).
  - We need a confidence number; the old function returns just a label.
  - We need TITLE-driven matching (with whole-word boundaries so "Towel"
    doesn't trigger the "Tee" alias by substring leak).

Tiered confidence
  0.97 — the canonical category word appears as a standalone token in the
         title (e.g. "Cotton T-Shirt" → tshirts).
  0.90 — a strong multi-word alias matches (e.g. "Mini Skirt", "Air Jordan").
  0.80 — a single-word non-canonical alias matches (e.g. "tee", "polo",
         "loafer").
  0.0  — no match.

Confidence floors are chosen so that:
  - 0.97 beats the user's 0.95 cascade threshold → text takes the answer.
  - 0.90 and 0.80 fall through to the LLM, which can correct edge cases
    where a single-word alias is misleading (a "Beach Towel" matches "tee"
    via substring of "between" — wait, we use word boundaries so this
    won't happen; but a product literally named "Polo Bag" would match
    "polo" → tshirts at 0.80, then LLM corrects to accessories).

Spec: user request 2026-05-24 (Striped Beach Towel regression).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from clothist_api.scrapers.normalize import CANONICAL_CATEGORIES, CATEGORY_ALIASES


# Canonical singular/plural pairs we want to recognize as the "canonical
# token in the title" case (confidence 0.97). These are the unambiguous
# garment names — when one of these appears in the product title, the
# vendor told us the category in plain English.
_CANONICAL_TITLE_TOKENS: dict[str, str] = {
    # canonical → set of tokens (whole-word matches) that mean it
}
_CANONICAL_TOKEN_SETS = {
    "tshirts":     {"t-shirt", "t-shirts", "tshirt", "tshirts", "tee", "tees",
                    "tank", "tanks", "polo", "polos", "shirt", "bodysuit",
                    "bodysuits", "cami", "top", "tops", "jersey", "jerseys",
                    "crew", "crewneck"},
    "hoodies":     {"hoodie", "hoodies", "sweatshirt", "sweatshirts"},
    "sweaters":    {"sweater", "sweaters", "cardigan", "cardigans"},
    "jackets":     {"jacket", "jackets", "blazer", "blazers", "coat", "coats",
                    "parka", "windbreaker", "vest", "vests"},
    "pants":       {"pant", "pants", "trousers", "trouser", "chino", "chinos",
                    "jogger", "joggers", "sweatpant", "sweatpants", "leggings"},
    "jeans":       {"jean", "jeans", "denim"},
    "shorts":      {"short", "shorts", "shorty", "shorties", "boardshort",
                    "boardshorts"},
    "skirts":      {"skirt", "skirts"},
    "dresses":     {"dress", "dresses", "gown", "gowns", "romper", "rompers",
                    "playsuit", "playsuits", "babydoll"},
    "sneakers":    # Footwear of every kind rolls into sneakers (the MVP taxonomy
                   # bundles boots / flats / loafers / sandals here — see
                   # scrapers/normalize.py:CATEGORY_ALIASES comment).
                   # Also includes a few brand model names that are
                   # unambiguous footwear: "Jordan", "Piper(s)".
                   {"sneaker", "sneakers", "trainer", "trainers", "runner",
                    "runners", "sandal", "sandals", "loafer", "loafers",
                    "espadrille", "espadrilles", "ballerina", "ballerinas",
                    "flyer", "flyers", "lounger", "loungers", "clog", "clogs",
                    "mule", "mules", "slipper", "slippers", "flip-flop",
                    "flip-flops", "moccasin", "moccasins", "moc", "mocs",
                    "heel", "heels", "stiletto", "stilettos", "pump", "pumps",
                    "oxford", "oxfords", "derby", "derbies", "slide", "slides",
                    "jordan", "piper", "pipers"},
    "accessories": # Anything non-garment goes here. The list is broader than
                   # the obvious bags/hats because the corpus has many
                   # adjacent items (laces, insoles, lighters, ceramic
                   # homewares, golf gear) that the prior tighter mapping
                   # was dumping into "other".
                   {"belt", "belts", "hat", "hats", "cap", "caps", "snapback",
                    "snapbacks", "beanie", "beanies", "scarf", "scarves",
                    "bag", "bags", "tote", "totes", "backpack", "backpacks",
                    "duffel", "duffels", "sling", "slings", "pouch", "pouches",
                    "clutch", "clutches", "crossbody", "satchel", "satchels",
                    "wallet", "wallets", "cardholder", "card", "keychain",
                    "keychains", "bandana", "bandanas", "glove", "gloves",
                    "mitten", "mittens", "sunglasses", "glasses", "goggle",
                    "goggles", "jewelry", "necklace", "necklaces", "bracelet",
                    "bracelets", "ring", "rings", "earring", "earrings",
                    "watch", "watches", "towel", "towels", "cover", "covers",
                    "case", "cases", "mask", "masks", "sock", "socks",
                    "lace", "laces", "strap", "straps", "insole", "insoles",
                    "flask", "flasks", "lighter", "lighters", "cutter",
                    "cutters", "tool", "tools", "holder", "holders",
                    "ceramic", "basket", "baskets", "pin", "pins",
                    "patch", "patches", "umbrella", "umbrellas",
                    "headband", "headbands", "wristband", "wristbands",
                    "charm", "charms"},
    "swimwear":    {"bikini", "bikinis", "swimsuit", "swimsuits", "swimwear"},
    "underwear":   {"underwear", "lingerie", "bra", "bras", "briefs", "boxer",
                    "boxers", "trunk", "trunks"},
}


# Multi-word aliases (≥2 tokens) → canonical. These hit at 0.97 confidence.
_STRONG_MULTI_WORD_ALIASES: dict[str, str] = {
    "tank top": "tshirts",
    "crop top": "tshirts",
    "polo shirt": "tshirts",
    "button up": "tshirts",
    "button-up": "tshirts",
    "button down": "tshirts",
    "camp shirt": "tshirts",
    "midi skirt": "skirts",
    "maxi skirt": "skirts",
    "mini skirt": "skirts",
    "midi dress": "dresses",
    "maxi dress": "dresses",
    "mini dress": "dresses",
    "high top": "sneakers",
    "low top": "sneakers",
    "air jordan": "sneakers",
    "mary jane": "sneakers",
    "flip flop": "sneakers",
    "flip flops": "sneakers",
    "slip on": "sneakers",
    "slip-on": "sneakers",
    "track pant": "pants",
    "track pants": "pants",
    "board shorts": "swimwear",
    "swim shorts": "swimwear",
    "swim trunks": "swimwear",
    "beach towel": "accessories",  # the Striped Beach Towel case
    "tote bag": "accessories",
    "duffel bag": "accessories",
    "bucket bag": "accessories",
    "pint basket": "accessories",
    "card case": "accessories",
    "card holder": "accessories",
    "face mask": "accessories",
    "tie top": "swimwear",          # Kith Women bikini tops
    "tie bottom": "swimwear",       # Kith Women bikini bottoms
    "triangle top": "swimwear",
    "halter top": "tshirts",
    "strapless top": "tshirts",
}


# Single-word "weak" aliases that still match (0.80). Pulled from the
# existing CATEGORY_ALIASES but only the truly single-word, non-canonical
# entries. Excludes anything ambiguous like "top" (matches "topshop"
# substrings) or "short" (which we let "shorts" catch via the canonical
# tokens above).
_WEAK_SINGLE_WORD_ALIASES: dict[str, str] = {
    "polo": "tshirts",
    "blouse": "tshirts",
    "knit": "sweaters",
    "knits": "sweaters",
    "pullover": "hoodies",
    "pullovers": "hoodies",
    "shoe": "sneakers",
    "shoes": "sneakers",
    "boot": "sneakers",
    "boots": "sneakers",
    "flat": "sneakers",
    "flats": "sneakers",
    "sandal": "sneakers",
    "sandals": "sneakers",
    "loafer": "sneakers",
    "loafers": "sneakers",
    "vest": "jackets",
    "vests": "jackets",
}


# Pre-compiled regex patterns. Order matters: we test multi-word patterns
# FIRST so "tank top" wins over "tank" alone if both could match.
_MULTI_WORD_RE = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in _STRONG_MULTI_WORD_ALIASES) + r")\b",
    re.IGNORECASE,
)

_CANONICAL_TOKEN_RE: dict[str, re.Pattern[str]] = {
    cat: re.compile(
        r"\b(" + "|".join(re.escape(t) for t in toks) + r")\b",
        re.IGNORECASE,
    )
    for cat, toks in _CANONICAL_TOKEN_SETS.items()
}

_WEAK_RE = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in _WEAK_SINGLE_WORD_ALIASES) + r")\b",
    re.IGNORECASE,
)


@dataclass(slots=True)
class TextCategoryVerdict:
    """Title-based categorization output."""

    category: str | None
    confidence: float
    matched_alias: str | None = None  # for debugging / audit only


CANONICAL_TITLE_CONF = 0.97   # canonical-token OR strong-multi-word match
WEAK_ALIAS_CONF = 0.80


def categorize_by_text(*, title: str, brand: str | None = None) -> TextCategoryVerdict:
    """Classify a product by its title (+ optionally brand).

    Match algorithm:
      1. Among ALL canonical-token + strong-multi-word matches, pick the
         one whose match starts LATEST in the title. English noun phrases
         put the head noun at the end ("Windbreaker Pant" → pants, not
         jackets; "Polo Shirt" → tshirts via either polo or shirt). 0.97.
      2. If no strong match, try weak single-word aliases (also
         last-position). 0.80.
      3. No match → (None, 0.0).
    """
    haystack = title.lower()

    # 1. Gather every strong match (canonical-token or multi-word) with
    #    its (end_pos, length, category, alias). Pick the LAST-ending
    #    winner. Sorting by end-pos (rather than start-pos) means
    #    "Swim Trunks Navy" routes via "swim trunks" → swimwear instead
    #    of bare "trunks" → underwear: both end at the same position, so
    #    the longer (more specific) alias wins the tiebreak.
    strong_matches: list[tuple[int, int, str, str]] = []
    for m in _MULTI_WORD_RE.finditer(haystack):
        alias = m.group(1).lower()
        strong_matches.append((m.end(), len(alias),
                                _STRONG_MULTI_WORD_ALIASES[alias], alias))
    for cat, pattern in _CANONICAL_TOKEN_RE.items():
        for m in pattern.finditer(haystack):
            strong_matches.append((m.end(), len(m.group(1)),
                                    cat, m.group(1).lower()))
    if strong_matches:
        strong_matches.sort(key=lambda t: (t[0], t[1]))
        _, _, cat, alias = strong_matches[-1]
        return TextCategoryVerdict(
            category=cat,
            confidence=CANONICAL_TITLE_CONF,
            matched_alias=alias,
        )

    # 2. Weak single-word alias — also end-position + length tiebreak.
    weak_matches: list[tuple[int, int, str, str]] = []
    for m in _WEAK_RE.finditer(haystack):
        alias = m.group(1).lower()
        weak_matches.append((m.end(), len(alias),
                              _WEAK_SINGLE_WORD_ALIASES[alias], alias))
    if weak_matches:
        weak_matches.sort(key=lambda t: (t[0], t[1]))
        _, _, cat, alias = weak_matches[-1]
        return TextCategoryVerdict(
            category=cat,
            confidence=WEAK_ALIAS_CONF,
            matched_alias=alias,
        )

    return TextCategoryVerdict(category=None, confidence=0.0, matched_alias=None)
