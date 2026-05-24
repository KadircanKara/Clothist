"""T3 — verify data/taxonomy/colors.json and apps/web/lib/colors.ts agree.

The TS file reads from the same JSON via a relative import, so once both
sides go through the file they trivially match. But a future contributor
might inline a hex into the TS file and forget to update the JSON. This
test catches that.

Mechanism: parse the JSON. Parse the TS file for any literal hex codes
inside `Object.fromEntries`-style declarations. Assert the JSON's mapping
is a superset of every literal hex that appears in the TS file.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
PALETTE_JSON = REPO_ROOT / "data" / "taxonomy" / "colors.json"
COLORS_TS = REPO_ROOT / "apps" / "web" / "lib" / "colors.ts"


def _load_json_palette() -> dict[str, str]:
    data = json.loads(PALETTE_JSON.read_text())
    return {c["name"]: c["hex"].lower() for c in data["colors"]}


_TS_LITERAL_HEX_RE = re.compile(r'"(#[0-9a-fA-F]{6})"')


def test_json_palette_loads():
    palette = _load_json_palette()
    assert len(palette) >= 25, "Palette unexpectedly small"
    assert "black" in palette
    assert "navy" in palette


def test_ts_imports_from_json():
    """TS file must `import colorsData from "...colors.json"` so it can't
    silently diverge. A regression where someone hardcodes a palette inline
    would break the test below; this is the early-warning."""
    ts = COLORS_TS.read_text()
    assert "data/taxonomy/colors.json" in ts, (
        "apps/web/lib/colors.ts must import from data/taxonomy/colors.json — "
        "do not hardcode the palette inline."
    )


def test_ts_literal_hex_codes_match_json():
    """If anyone hand-inlines a hex code in colors.ts, the JSON must also
    contain that exact hex. Catches the silent-divergence regression."""
    palette = _load_json_palette()
    json_hexes = {h.lower() for h in palette.values()}
    ts_text = COLORS_TS.read_text()
    ts_literals = {h.lower() for h in _TS_LITERAL_HEX_RE.findall(ts_text)}
    # The "floral" and fallback gradients use their own hexes intentionally.
    # Those should also be in the palette (they're #e9a4ad pink, #f0e8d4 cream,
    # #3a8045 green, #c39a64 camel, #e2d5b8 beige, #d6cfc0 stone).
    leaked = ts_literals - json_hexes
    assert not leaked, (
        f"hex codes in colors.ts not present in data/taxonomy/colors.json: "
        f"{sorted(leaked)}. Either add them to the JSON or remove the inline "
        f"literal."
    )
