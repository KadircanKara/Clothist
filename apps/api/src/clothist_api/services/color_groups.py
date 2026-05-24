"""Coarse color-group mapping for filter UIs.

The granular 31-token palette (data/taxonomy/colors.json) is great for
product cards and PDPs but produces too many filter chips on the
Home/Men/Women/Unisex pages. This module loads the 12-bucket coarse
grouping so the search facets + color filter can collapse e.g.
{navy, light-blue, vintage-blue, indigo, stone-wash} → "blue".

Pure stdlib; safe to import from anywhere (no CV or DB deps).
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path


def _palette_path() -> Path:
    # services/color_groups.py  →  parents[0]=services parents[1]=clothist_api
    # parents[2]=src  parents[3]=api  parents[4]=apps  parents[5]=repo-root
    return Path(__file__).resolve().parents[5] / "data" / "taxonomy" / "colors.json"


@lru_cache(maxsize=1)
def _load() -> tuple[list[str], dict[str, str], dict[str, list[str]]]:
    """Returns (group_order, color→group, group→[colors])."""
    data = json.loads(_palette_path().read_text())
    group_order = [g["name"] for g in data["groups"]]
    by_color = {c["name"]: c["group"] for c in data["colors"]}
    by_group: dict[str, list[str]] = {g: [] for g in group_order}
    for c in data["colors"]:
        by_group[c["group"]].append(c["name"])
    return group_order, by_color, by_group


MAIN_COLOR_GROUPS: list[str] = _load()[0]
COLOR_TO_GROUP: dict[str, str] = _load()[1]
GROUP_TO_COLORS: dict[str, list[str]] = _load()[2]


def expand_to_group_members(group: str) -> list[str]:
    """Return the granular colors that belong to a coarse group. Falls back
    to `[group]` if the input is already a granular color name (so the
    filter still works against legacy product rows that store the granular
    name directly, e.g. "navy"). Returns `[]` only for unknown tokens."""
    if group in GROUP_TO_COLORS:
        return GROUP_TO_COLORS[group]
    # Granular color passed through (e.g. older bookmarks with ?color=navy).
    if group in COLOR_TO_GROUP:
        return [group]
    return []
