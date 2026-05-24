"""Non-clothing detection — keep Clothist true to its name.

The user's calibration (2026-05-24):
  towel ✓   keychain ✗   flask ✗   cigar cutter ✗   bag ✓   putter cover ✗

The detector lives in services/text_categorize.py and routes matched
items to the "excluded" category, which services/search.py hides from
listing pages and facets.
"""
from __future__ import annotations

import pytest

from clothist_api.services.text_categorize import (
    EXCLUDED_CATEGORY,
    NON_CLOTHING_MULTI_WORD,
    NON_CLOTHING_TOKENS,
    categorize_by_text,
)


# ---------------- Calibration examples ---------------- #


@pytest.mark.parametrize("title,expected", [
    # User's "OK" list — wearable or made of cloth.
    ("Striped Beach Towel",                                   "accessories"),
    ("Marina Bottle Tote",                                    "accessories"),
    ("Kith Kids Water Bottle Holder Bag",                     "accessories"),
    ("ALD Golf Bucket Hat",                                   "accessories"),
    ("ALD Golf Swing Bandana",                                "accessories"),
    ("ALD Golf Caddy Towel",                                  "accessories"),
    ("Phone Case Navy",                                       "accessories"),
    ("Card Holder Black",                                     "accessories"),
])
def test_clothing_kept(title: str, expected: str):
    v = categorize_by_text(title=title)
    assert v.category == expected, (
        f"Expected {title!r} to land in {expected}, got {v.category} "
        f"(via {v.matched_alias})"
    )


@pytest.mark.parametrize("title,expected_alias", [
    # User's "NOT OK" list — not wearable AND not cloth.
    ("ALD Golf 19th Flask",                                   "flask"),
    ("ALD Golf Cigar Cutter",                                 "cutter"),
    ("ALD Golf Cigar Torch Lighter",                          "lighter"),
    ("ALD Golf Divot Tool",                                   "divot tool"),
    ("ALD Golf Driver Cover",                                 "driver cover"),
    ("ALD Golf Keychain",                                     "keychain"),
    ("ALD Golf Leather Cigar Case",                           "cigar case"),
    ("ALD Golf Putter Cover",                                 "putter cover"),
    ("Kith Kids 3-Pack Summer Charms",                        "charms"),
    ("Kith Treats Farmers Market Ceramic Half Dozen Egg Holder",
        "egg holder"),
    ("Kith Treats Farmers Market Ceramic Pint Basket",        "basket"),
    ("Walnut Model Sailboat",                                 "model sailboat"),
    ("Hot & Unbothered Fan Pink",                             "fan"),
])
def test_non_clothing_excluded(title: str, expected_alias: str):
    v = categorize_by_text(title=title)
    assert v.category == EXCLUDED_CATEGORY, (
        f"Expected {title!r} to be excluded, got {v.category} "
        f"(via {v.matched_alias})"
    )
    assert v.matched_alias == expected_alias, (
        f"Expected alias {expected_alias!r}, got {v.matched_alias!r}"
    )


# ---------------- Head-noun disambiguation ---------------- #


def test_bottle_in_bag_title_stays_clothing():
    """The head-noun heuristic must keep "Bottle Holder Bag" in
    accessories: "bag" ends later than the non-clothing "bottle holder",
    so the latest-ending match wins."""
    v = categorize_by_text(title="Kith Kids Water Bottle Holder Bag")
    assert v.category == "accessories"
    assert v.matched_alias == "bag"


def test_bottle_tote_stays_clothing():
    """Marina Bottle Tote — "tote" later than any non-clothing token."""
    v = categorize_by_text(title="Marina Bottle Tote")
    assert v.category == "accessories"
    assert v.matched_alias == "tote"


def test_putter_cover_excluded():
    """Putter Cover — "putter cover" multi-word is the only strong match;
    the bare "cover" token has been removed from clothing canonical, so
    no clothing token competes."""
    v = categorize_by_text(title="ALD Golf Putter Cover")
    assert v.category == EXCLUDED_CATEGORY


def test_caddy_towel_kept():
    """The bare word "Towel" should still classify as accessories
    regardless of golf context (the user said towels are OK)."""
    v = categorize_by_text(title="ALD Golf Caddy Towel")
    assert v.category == "accessories"


# ---------------- Vocabulary contract ---------------- #


def test_non_clothing_tokens_disjoint_from_canonical():
    """A token can't be both clothing AND non-clothing — that would make
    the cascade nondeterministic on edge cases."""
    from clothist_api.services.text_categorize import _CANONICAL_TOKEN_SETS
    all_clothing = set()
    for toks in _CANONICAL_TOKEN_SETS.values():
        all_clothing.update(toks)
    overlap = NON_CLOTHING_TOKENS & all_clothing
    assert not overlap, (
        f"Tokens appear in both clothing canonical AND NON_CLOTHING_TOKENS: "
        f"{sorted(overlap)}"
    )


def test_excluded_constant_is_excluded_string():
    assert EXCLUDED_CATEGORY == "excluded"


def test_non_clothing_multi_word_contains_user_examples():
    """The user's calibration list is the contract."""
    assert "putter cover" in NON_CLOTHING_MULTI_WORD
    assert "model sailboat" in NON_CLOTHING_MULTI_WORD


def test_non_clothing_tokens_contains_user_examples():
    assert "flask" in NON_CLOTHING_TOKENS
    assert "cutter" in NON_CLOTHING_TOKENS
    assert "keychain" in NON_CLOTHING_TOKENS
