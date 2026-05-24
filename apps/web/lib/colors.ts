/**
 * Canonical mapping from seed-data color name → CSS background string.
 *
 * Compound entries ("black/white", "navy/white") render as a 50/50 split
 * via a hard-edge linear-gradient so the swatch shows both hues. "Floral"
 * gets a soft multi-hue gradient that reads as patterned rather than solid.
 *
 * Keep this file in sync with `data/seed/products.json` colors when new
 * shades are introduced — the backend exposes the union of listing +
 * variant colors via /search/facets, so anything in the seed eventually
 * reaches a swatch.
 */
const COLOR_HEX: Record<string, string> = {
  black: "#0a0a09",
  white: "#fafafa",
  cream: "#f0e8d4",
  grey: "#a3a3a3",
  navy: "#1a2440",
  blue: "#3b5bdb",
  "light-blue": "#a4c2e0",
  "vintage-blue": "#6c8aab",
  indigo: "#3b3672",
  green: "#3a8045",
  forest: "#2d4a32",
  olive: "#6b6b32",
  rust: "#b54e21",
  orange: "#e7791f",
  red: "#c62833",
  pink: "#e9a4ad",
  brown: "#6b4a32",
  tan: "#cdab83",
  beige: "#e2d5b8",
  khaki: "#b8a276",
  camel: "#c39a64",
  stone: "#d6cfc0",
  "stone-wash": "#a8b4be",
  "washed-black": "#3d3a36",
  "faded-black": "#2a2724",
  purple: "#7c5edb",
  yellow: "#e9c33d",
  burgundy: "#762a36",
  sand: "#dac7a5",
  gold: "#c9a04a",
  charcoal: "#3a3a3a",
};

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
