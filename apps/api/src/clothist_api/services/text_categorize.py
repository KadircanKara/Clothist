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
    "footwear":    # Footwear of every kind rolls into footwear (the MVP taxonomy
                   # bundles boots / flats / loafers / sandals here — see
                   # scrapers/normalize.py:CATEGORY_ALIASES comment).
                   # Brand model names like "Jordan" and "Piper" are NOT
                   # in this set — bare "piper" wrongly caught the Kith
                   # Women "Stripe Raffia Piper" (a handbag). Those live
                   # as specific multi-word aliases below ("air jordan",
                   # "jordan 12", "tree piper", "wool piper", etc.).
                   {"sneaker", "footwear", "trainer", "trainers", "runner",
                    "runners", "sandal", "sandals", "loafer", "loafers",
                    "espadrille", "espadrilles", "ballerina", "ballerinas",
                    "flyer", "flyers", "lounger", "loungers", "clog", "clogs",
                    "mule", "mules", "slipper", "slippers", "flip-flop",
                    "flip-flops", "moccasin", "moccasins", "moc", "mocs",
                    "heel", "heels", "stiletto", "stilettos", "pump", "pumps",
                    "oxford", "oxfords", "derby", "derbies", "slide", "slides",
                    # Footwear-only brand names — safe additions because
                    # these brands don't sell apparel.
                    "hoka", "asics"},
    "accessories": # Clothing-adjacent items: wearable (hats, jewelry, watches,
                   # gloves, sunglasses) OR made of cloth/leather (bags,
                   # wallets, scarves, socks, towels). Non-clothing items
                   # (flasks, lighters, ceramics, keychains, golf gear) live
                   # in NON_CLOTHING_TOKENS below and route to "excluded".
                   {"belt", "belts", "hat", "hats", "cap", "caps", "snapback",
                    "snapbacks", "beanie", "beanies", "scarf", "scarves",
                    "bag", "bags", "tote", "totes", "backpack", "backpacks",
                    "duffel", "duffels", "sling", "slings", "pouch", "pouches",
                    "clutch", "clutches", "crossbody", "satchel", "satchels",
                    "wallet", "wallets", "cardholder",
                    "bandana", "bandanas", "glove", "gloves",
                    "mitten", "mittens", "sunglasses", "glasses", "goggle",
                    "goggles", "jewelry", "necklace", "necklaces", "bracelet",
                    "bracelets", "ring", "rings", "earring", "earrings",
                    "watch", "watches", "towel", "towels",
                    "sock", "socks", "lace", "laces", "strap", "straps",
                    "insole", "insoles", "pin", "pins", "patch", "patches",
                    "headband", "headbands", "wristband", "wristbands"},
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
    "high top": "footwear",
    "low top": "footwear",
    "mary jane": "footwear",
    "flip flop": "footwear",
    "flip flops": "footwear",
    "slip on": "footwear",
    "slip-on": "footwear",
    # Brand+model patterns. Specific enough that they can't false-positive
    # on the Kith "Raffia Piper" handbag or a hypothetical "Jordan Tee".
    "air jordan": "footwear",
    "jordan 1": "footwear",
    "jordan 3": "footwear",
    "jordan 4": "footwear",
    "jordan 5": "footwear",
    "jordan 6": "footwear",
    "jordan 11": "footwear",
    "jordan 12": "footwear",
    "jordan retro": "footwear",
    # Allbirds Piper family — "Tree Piper", "Wool Piper", "Piper Mid",
    # "Piper Woven", plus plural variants.
    "tree piper": "footwear",
    "tree pipers": "footwear",
    "wool piper": "footwear",
    "wool pipers": "footwear",
    "piper mid": "footwear",
    "piper mids": "footwear",
    "piper woven": "footwear",
    "track pant": "pants",
    "track pants": "pants",
    "board shorts": "swimwear",
    "swim shorts": "swimwear",
    "swim trunks": "swimwear",
    "beach towel": "accessories",  # the Striped Beach Towel case
    "tote bag": "accessories",
    "duffel bag": "accessories",
    "bucket bag": "accessories",
    # `card case` / `card holder` / `phone case` are leather/cloth wallet-
    # adjacent items so they get a clothing slot. Bare "case" / "cover" /
    # "holder" are too generic (cigar case, putter cover, egg holder) and
    # so are NOT in the canonical tokens — non-clothing equivalents in
    # NON_CLOTHING_MULTI_WORD catch those.
    "card case": "accessories",
    "card holder": "accessories",
    "phone case": "accessories",
    "phone cover": "accessories",
    "face mask": "accessories",
    "ski mask": "accessories",
    "tie top": "swimwear",          # Kith Women bikini tops
    "tie bottom": "swimwear",       # Kith Women bikini bottoms
    "triangle top": "swimwear",
    "halter top": "tshirts",
    "strapless top": "tshirts",
}


# ----------------------- Non-clothing detection ----------------------- #
#
# The app is Clothist — it only carries clothing. Items that are neither
# wearable nor made of cloth (a paper fan, a wooden model sailboat, a
# ceramic egg holder, a golf cigar cutter) route to the "excluded"
# category instead of trying to force-fit a clothing label, and the
# search API hides them from filter facets + browse pages.
#
# Inspired by the user's calibration examples (2026-05-24):
#   towel ✓   keychain ✗   flask ✗   cigar cutter ✗   bag ✓   putter cover ✗
#
# The detection uses the same end-position + length tiebreak as the
# clothing matcher so "Marina Bottle Tote" routes via the later-ending
# clothing token "tote" instead of the non-clothing "bottle".

EXCLUDED_CATEGORY = "excluded"

NON_CLOTHING_TOKENS: set[str] = {
    # Drinkware / kitchenware
    "flask", "flasks", "tumbler", "tumblers", "mug", "mugs",
    "ashtray", "ashtrays", "candle", "candles",
    # Tools + metal trinkets (the ALD Golf line — cigar cutters, divot
    # tools, lighters, keychains, charms are all non-clothing).
    "lighter", "lighters", "cutter", "cutters", "opener", "openers",
    "keychain", "keychains", "charm", "charms",
    # Homewares (Kith Treats Farmers Market ceramic line)
    "ceramic", "ceramics", "basket", "baskets",
    # Sports gear that isn't apparel
    "putter", "putters", "divot",
    # Tobacco
    "cigar", "cigars",
    # Wood/decor model items
    "sailboat", "sailboats",
    # Paper fans (Princess Polly novelty item) — NOT ceiling/sports fan;
    # apparel catalogues rarely use "fan" any other way.
    "fan", "fans",
    # Umbrella — polyester technically a "cloth" but the user's strict
    # reading is "wearable OR cloth used in clothing"; umbrellas don't
    # qualify.
    "umbrella", "umbrellas",
}

NON_CLOTHING_MULTI_WORD: set[str] = {
    # Golf club covers — fabric-ish but for clubs, not people
    "putter cover", "driver cover", "club cover", "head cover",
    # Tools
    "divot tool",
    # Homewares with non-clothing head noun
    "bottle holder", "egg holder", "cigar holder",
    # Cigar/Tobacco accessories
    "cigar case",
    # Wood decor
    "model sailboat",
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
    "shoe": "footwear",
    "shoes": "footwear",
    "boot": "footwear",
    "boots": "footwear",
    "flat": "footwear",
    "flats": "footwear",
    "sandal": "footwear",
    "sandals": "footwear",
    "loafer": "footwear",
    "loafers": "footwear",
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

# Non-clothing detection patterns.
_NON_CLOTHING_TOKEN_RE = re.compile(
    r"\b(" + "|".join(re.escape(t) for t in NON_CLOTHING_TOKENS) + r")\b",
    re.IGNORECASE,
)
_NON_CLOTHING_MULTI_WORD_RE = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in NON_CLOTHING_MULTI_WORD) + r")\b",
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
      1. Gather ALL strong matches across the clothing AND non-clothing
         vocabularies. The latest-ending match wins (with length as a
         tiebreak). Clothing matches return their normal category at
         0.97; non-clothing matches return "excluded" at 0.97.
      2. If no strong match, try weak single-word clothing aliases at 0.80.
      3. No match → (None, 0.0).

    The head-noun heuristic (latest position wins) handles tricky cases:
      - "Marina Bottle Tote" → "tote" ends later than the non-clothing
        "bottle" → accessories (kept).
      - "ALD Golf Putter Cover" → "putter cover" (non-clothing) is the
        only strong match → excluded (filtered out).
      - "Swim Trunks Navy" → "swim trunks" beats bare "trunks" on length
        tiebreak → swimwear.
    """
    haystack = title.lower()

    # 1. Gather every strong match (clothing canonical/multi-word AND
    #    non-clothing). Each entry: (end_pos, length, category, alias).
    #    Latest-ending winner with longer-alias tiebreak.
    strong_matches: list[tuple[int, int, str, str]] = []
    for m in _MULTI_WORD_RE.finditer(haystack):
        alias = m.group(1).lower()
        strong_matches.append((m.end(), len(alias),
                                _STRONG_MULTI_WORD_ALIASES[alias], alias))
    for cat, pattern in _CANONICAL_TOKEN_RE.items():
        for m in pattern.finditer(haystack):
            strong_matches.append((m.end(), len(m.group(1)),
                                    cat, m.group(1).lower()))
    # Non-clothing matches use the SAME comparison pool — they only win
    # when they appear later than any clothing match.
    for m in _NON_CLOTHING_MULTI_WORD_RE.finditer(haystack):
        alias = m.group(1).lower()
        strong_matches.append((m.end(), len(alias),
                                EXCLUDED_CATEGORY, alias))
    for m in _NON_CLOTHING_TOKEN_RE.finditer(haystack):
        strong_matches.append((m.end(), len(m.group(1)),
                                EXCLUDED_CATEGORY, m.group(1).lower()))
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
