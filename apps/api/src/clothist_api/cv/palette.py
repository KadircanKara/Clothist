"""Canonical color palette + CIELAB ΔE-76 nearest-color lookup.

Reads `data/taxonomy/colors.json` — the single source of truth shared with
`apps/web/lib/colors.ts`. The sync test in tests/test_color_palette_sync.py
guarantees both sides stay in step.

Pure Python; no numpy/torch deps. Safe to import from anywhere.
"""
from __future__ import annotations

import json
from pathlib import Path


def _palette_path() -> Path:
    # cv/palette.py  →  parents[0]=cv  parents[1]=clothist_api
    # parents[2]=src parents[3]=api parents[4]=apps parents[5]=repo-root
    return Path(__file__).resolve().parents[5] / "data" / "taxonomy" / "colors.json"


def _load_palette() -> dict[str, str]:
    data = json.loads(_palette_path().read_text())
    return {c["name"]: c["hex"] for c in data["colors"]}


COLOR_HEX: dict[str, str] = _load_palette()


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


# Precompute every palette color's LAB representation once at import time —
# the per-image quantizer maps thousands of pixels into the LAB space and
# repeats this lookup; caching saves ~milliseconds per image.
def _rgb_to_xyz(r: int, g: int, b: int) -> tuple[float, float, float]:
    def lin(c: float) -> float:
        c = c / 255.0
        return ((c + 0.055) / 1.055) ** 2.4 if c > 0.04045 else c / 12.92
    rl, gl, bl = lin(r), lin(g), lin(b)
    x = rl * 0.4124564 + gl * 0.3575761 + bl * 0.1804375
    y = rl * 0.2126729 + gl * 0.7151522 + bl * 0.0721750
    z = rl * 0.0193339 + gl * 0.1191920 + bl * 0.9503041
    return x, y, z


def _xyz_to_lab(x: float, y: float, z: float) -> tuple[float, float, float]:
    # D65 reference white
    xn, yn, zn = 0.95047, 1.0, 1.08883

    def f(t: float) -> float:
        return t ** (1 / 3) if t > 0.008856 else (7.787 * t + 16 / 116)
    fx, fy, fz = f(x / xn), f(y / yn), f(z / zn)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def rgb_to_lab(c: tuple[int, int, int]) -> tuple[float, float, float]:
    return _xyz_to_lab(*_rgb_to_xyz(*c))


def delta_e_76(c1: tuple[int, int, int], c2: tuple[int, int, int]) -> float:
    """Euclidean distance in CIELAB. ΔE76 is good enough for fashion-color
    bucketing where the palette tokens are well-separated; ΔE2000 would be
    technically better but is ~20× slower and overkill for our 31-token map.
    """
    l1, a1, b1 = rgb_to_lab(c1)
    l2, a2, b2 = rgb_to_lab(c2)
    return ((l1 - l2) ** 2 + (a1 - a2) ** 2 + (b1 - b2) ** 2) ** 0.5


_PALETTE_LAB: dict[str, tuple[float, float, float]] = {
    name: rgb_to_lab(hex_to_rgb(hex_str)) for name, hex_str in COLOR_HEX.items()
}


def nearest_palette_color(rgb: tuple[int, int, int]) -> str:
    """Return the palette color name closest to `rgb` by ΔE-76."""
    target_lab = rgb_to_lab(rgb)
    best_name = ""
    best_dist = float("inf")
    for name, lab in _PALETTE_LAB.items():
        dist = (
            (target_lab[0] - lab[0]) ** 2
            + (target_lab[1] - lab[1]) ** 2
            + (target_lab[2] - lab[2]) ** 2
        ) ** 0.5
        if dist < best_dist:
            best_dist = dist
            best_name = name
    return best_name
