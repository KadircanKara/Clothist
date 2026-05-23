"use client";

import { Button } from "@/components/ui/button";
import type { SearchParams } from "@/lib/types";

type DroppableKey =
  | "max_price"
  | "min_price"
  | "features"
  | "excluded_features"
  | "color"
  | "brand"
  | "category"
  | "q";

type Suggestion = {
  key: DroppableKey;
  label: string;
  apply: () => void;
};

type Props = {
  filters: SearchParams;
  onClear: () => void;
  onDrop: (next: SearchParams) => void;
};

function build(filters: SearchParams, onDrop: (next: SearchParams) => void): Suggestion[] {
  const out: Suggestion[] = [];

  if (filters.max_price !== undefined) {
    out.push({
      key: "max_price",
      label: `Drop ≤ $${filters.max_price}`,
      apply: () => onDrop({ ...filters, max_price: undefined, offset: 0 }),
    });
  }
  if (filters.min_price !== undefined) {
    out.push({
      key: "min_price",
      label: `Drop ≥ $${filters.min_price}`,
      apply: () => onDrop({ ...filters, min_price: undefined, offset: 0 }),
    });
  }
  if (filters.features && filters.features.length > 0) {
    const f = filters.features[0];
    out.push({
      key: "features",
      label: `Drop ✓ ${humanize(f)}`,
      apply: () =>
        onDrop({
          ...filters,
          features: (filters.features ?? []).filter((x) => x !== f),
          offset: 0,
        }),
    });
  }
  if (filters.excluded_features && filters.excluded_features.length > 0) {
    const f = filters.excluded_features[0];
    out.push({
      key: "excluded_features",
      label: `Drop ✗ ${humanize(f)}`,
      apply: () =>
        onDrop({
          ...filters,
          excluded_features: (filters.excluded_features ?? []).filter((x) => x !== f),
          offset: 0,
        }),
    });
  }
  if (filters.color) {
    out.push({
      key: "color",
      label: `Drop ${filters.color}`,
      apply: () => onDrop({ ...filters, color: undefined, offset: 0 }),
    });
  }
  if (filters.brand) {
    out.push({
      key: "brand",
      label: `Drop ${filters.brand}`,
      apply: () => onDrop({ ...filters, brand: undefined, offset: 0 }),
    });
  }
  if (filters.category) {
    out.push({
      key: "category",
      label: `Drop ${filters.category}`,
      apply: () => onDrop({ ...filters, category: undefined, offset: 0 }),
    });
  }

  return out.slice(0, 3);
}

function humanize(token: string): string {
  return token.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}

export function EmptyState({ filters, onClear, onDrop }: Props) {
  const suggestions = build(filters, onDrop);

  return (
    <div className="hairline flex flex-col items-center justify-center gap-4 px-6 py-16 text-center">
      <span className="font-serif italic text-4xl">Nothing matched.</span>
      {suggestions.length > 0 ? (
        <>
          <p className="serif-eyebrow max-w-md text-sm">
            Your query is narrow. Try dropping the most-restrictive constraint:
          </p>
          <div className="flex flex-wrap items-center justify-center gap-2">
            {suggestions.map((s) => (
              <Button
                key={s.key}
                variant="outline"
                size="sm"
                onClick={s.apply}
              >
                {s.label}
              </Button>
            ))}
          </div>
          <button
            type="button"
            onClick={onClear}
            className="link-reveal font-mono text-[11px] uppercase tracking-widest text-muted hover:text-foreground"
          >
            Clear all and start over
          </button>
        </>
      ) : (
        <button
          type="button"
          onClick={onClear}
          className="link-reveal font-mono text-[11px] uppercase tracking-widest text-muted hover:text-foreground"
        >
          Clear search and start over
        </button>
      )}
    </div>
  );
}
