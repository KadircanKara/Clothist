/**
 * Compute filter facets from a returned product list.
 *
 * The catalog sidebar normally consumes /search/facets, which is
 * scoped to the current gender (and excludes non-clothing). On the
 * conversational /search page we don't want pre-baked global facets —
 * we want chips that ONLY reflect what came back for THIS query. So
 * we derive them clientside from the search response.
 *
 * Counts are inclusive (a 3-color product contributes 1 to each color
 * group's count). Sort order:
 *   - categories / brands: count desc
 *   - colors: canonical group order (MAIN_COLOR_GROUPS)
 */
import { COLOR_TO_GROUP, MAIN_COLOR_GROUPS } from "./colors";
import type { FacetsResponse, Product } from "./types";

export function deriveFacets(items: Product[]): FacetsResponse {
  const catCounts = new Map<string, number>();
  const brandCounts = new Map<string, number>();
  const colorGroupCounts = new Map<string, number>();
  let priceMin: number | null = null;
  let priceMax: number | null = null;

  for (const p of items) {
    if (p.category) catCounts.set(p.category, (catCounts.get(p.category) ?? 0) + 1);
    if (p.brand) brandCounts.set(p.brand, (brandCounts.get(p.brand) ?? 0) + 1);
    if (p.colors) {
      // De-dupe per-product so a product with [navy, blue, light-blue]
      // doesn't triple-count the "blue" group.
      const groupsHere = new Set<string>();
      for (const c of p.colors) {
        const g = COLOR_TO_GROUP[c];
        if (g) groupsHere.add(g);
      }
      for (const g of groupsHere) {
        colorGroupCounts.set(g, (colorGroupCounts.get(g) ?? 0) + 1);
      }
    }
    const priceN = priceToNumber(p.price);
    if (priceN !== null) {
      priceMin = priceMin === null ? priceN : Math.min(priceMin, priceN);
      priceMax = priceMax === null ? priceN : Math.max(priceMax, priceN);
    }
  }

  return {
    categories: sortByCountDesc([...catCounts.entries()]),
    brands: sortByCountDesc([...brandCounts.entries()]),
    colors: MAIN_COLOR_GROUPS
      .filter((g) => (colorGroupCounts.get(g) ?? 0) > 0)
      .map((g) => ({ value: g, count: colorGroupCounts.get(g) ?? 0 })),
    price: {
      min: priceMin === null ? null : priceMin.toFixed(2),
      max: priceMax === null ? null : priceMax.toFixed(2),
    },
    features: [],
    fx_date: null,
  };
}

function sortByCountDesc(rows: [string, number][]): FacetsResponse["categories"] {
  return rows
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .map(([value, count]) => ({ value, count }));
}

function priceToNumber(p: string | null): number | null {
  if (!p) return null;
  const n = Number(p);
  return Number.isFinite(n) ? n : null;
}
