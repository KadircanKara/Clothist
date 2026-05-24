/**
 * Canonical mapping from seed-data color name → CSS background string.
 *
 * The base palette is loaded from `data/taxonomy/colors.json` (the single
 * source of truth shared with the Python CV pipeline at
 * `apps/api/src/clothist_api/cv/palette.py`). Compound entries
 * ("black/white", "navy/white") render as a 50/50 split via a hard-edge
 * linear-gradient. "Floral" gets a soft multi-hue gradient.
 *
 * To add or rename a color: edit `data/taxonomy/colors.json` (NOT this
 * file). The sync test in `apps/api/tests/test_color_palette_sync.py`
 * fails the CI build if the two sources diverge.
 */
// Path resolves from apps/web/lib/colors.ts up to the repo root.
import colorsData from "../../../data/taxonomy/colors.json";

const COLOR_HEX: Record<string, string> = Object.fromEntries(
  colorsData.colors.map((c) => [c.name, c.hex]),
);

/**
 * Granular color → main group lookup. Mirrors the backend
 * services/color_groups.py so the search page can derive its own
 * "result-set facets" without a roundtrip.
 */
export const COLOR_TO_GROUP: Record<string, string> = Object.fromEntries(
  colorsData.colors.map((c) => [c.name, (c as { group: string }).group]),
);

/** Canonical ordering for the 12 main filter chips. */
export const MAIN_COLOR_GROUPS: string[] = colorsData.groups.map(
  (g: { name: string }) => g.name,
);

/**
 * Return a CSS `background` value that visually represents the color. Falls
 * back to a neutral cream→stone gradient for unknown names so the dot never
 * renders as a generic "?" placeholder.
 */
export function colorBackground(color: string | null | undefined): string {
  if (!color) return "linear-gradient(135deg, #e2d5b8 0%, #d6cfc0 100%)";
  const key = color.toLowerCase().trim();

  // Direct hit
  const direct = COLOR_HEX[key];
  if (direct) return direct;

  // Slash-compound (e.g. "black/white", "navy/white") → 50/50 split
  if (key.includes("/")) {
    const parts = key.split("/").map((p) => p.trim());
    const hexes = parts
      .map((p) => COLOR_HEX[p] ?? null)
      .filter((h): h is string => !!h);
    if (hexes.length >= 2) {
      return `linear-gradient(135deg, ${hexes[0]} 0%, ${hexes[0]} 50%, ${hexes[1]} 50%, ${hexes[1]} 100%)`;
    }
    if (hexes.length === 1) return hexes[0];
  }

  // Patterned / multi-color descriptive names
  if (key === "floral") {
    return "linear-gradient(135deg, #e9a4ad 0%, #f0e8d4 35%, #3a8045 65%, #c39a64 100%)";
  }

  // Last-resort neutral so we never paint a "?" tile.
  return "linear-gradient(135deg, #e2d5b8 0%, #d6cfc0 100%)";
}

/**
 * Humanize a snake-case or hyphenated color key for display
 * ("stone-wash" → "Stone wash"). Slash-compounds keep both halves.
 */
export function humanizeColor(color: string | null | undefined): string {
  if (!color) return "Unknown";
  return color
    .split("/")
    .map((part) =>
      part
        .replace(/[-_]+/g, " ")
        .replace(/\b\w/g, (c) => c.toUpperCase()),
    )
    .join(" / ");
}
