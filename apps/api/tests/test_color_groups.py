"""Tests for the coarse color-group mapping.

The granular 31-token palette in data/taxonomy/colors.json is bucketed into
12 main groups for the filter UI. These tests pin the contract:
  - every granular color belongs to exactly one group
  - every group has at least one granular member
  - the public helpers behave per the docstrings
"""
from __future__ import annotations

import json
from pathlib import Path

from clothist_api.services.color_groups import (
    COLOR_TO_GROUP,
    GROUP_TO_COLORS,
    MAIN_COLOR_GROUPS,
    expand_to_group_members,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
PALETTE_JSON = REPO_ROOT / "data" / "taxonomy" / "colors.json"


def test_every_color_has_a_group():
    """Catches the regression of adding a color to the palette without
    setting its group field. Would silently drop the new color from filter
    facets — exactly the kind of slow leak you don't notice in code review."""
    data = json.loads(PALETTE_JSON.read_text())
    for c in data["colors"]:
        assert c.get("group"), f"color {c['name']!r} missing `group` field"
        assert c["group"] in MAIN_COLOR_GROUPS, (
            f"color {c['name']!r} points to unknown group {c['group']!r}"
        )


def test_every_group_has_at_least_one_color():
    """No empty buckets — they'd render as dead filter chips."""
    for g in MAIN_COLOR_GROUPS:
        assert GROUP_TO_COLORS[g], f"group {g!r} has no granular members"


def test_expand_main_group_returns_members():
    """The blue group should expand to navy, light-blue, etc."""
    members = expand_to_group_members("blue")
    # We don't pin the exact set because the palette evolves; we pin the
    # contract: navy must roll up to blue.
    assert "blue" in members
    assert "navy" in members
    assert "light-blue" in members


def test_expand_granular_color_passes_through():
    """Legacy callers that send a granular color (e.g. from a saved URL)
    keep working: a single-color match instead of group expansion."""
    members = expand_to_group_members("navy")
    assert members == ["navy"]


def test_expand_unknown_returns_empty_list():
    """Caller can detect an unknown token and decide whether to skip the
    filter or fall back to a literal match. We just contract that the
    return is `[]`, not None."""
    assert expand_to_group_members("not-a-real-color") == []
    assert expand_to_group_members("") == []


def test_group_count_is_twelve():
    """Pinning the count so a future palette refactor that doubles the
    bucket size is caught before it ships."""
    assert len(MAIN_COLOR_GROUPS) == 12


def test_canonical_groups_are_subset_of_color_names():
    """Each main group's name MUST also exist as a granular color so the
    same hex+swatch rendering code works for both. (e.g. group "blue" and
    granular "blue" share #3b5bdb.)"""
    for g in MAIN_COLOR_GROUPS:
        assert g in COLOR_TO_GROUP, f"group {g!r} not present as a granular color"


def test_groups_array_in_json_matches_main_color_groups():
    """The `groups` array in colors.json is what we expose to the frontend's
    main-color helpers; this test pins ordering and content."""
    data = json.loads(PALETTE_JSON.read_text())
    assert [g["name"] for g in data["groups"]] == MAIN_COLOR_GROUPS
