"use client";

import type { SortKey } from "@/lib/types";

const LABELS: Array<{ value: SortKey; label: string; disabledHint?: string }> = [
  { value: "relevance", label: "Relevance" },
  { value: "price_asc", label: "Price ↑" },
  { value: "price_desc", label: "Price ↓" },
  { value: "newest", label: "Newest" },
  { value: "highest_rated", label: "Highest rated — soon", disabledHint: "reviews coming soon" },
];

type Props = {
  value: SortKey;
  onChange: (next: SortKey, uiHint?: string) => void;
};

export function SortControl({ value, onChange }: Props) {
  return (
    <label className="inline-flex items-center gap-3">
      <span className="kicker">Sort</span>
      <span className="sr-only">Sort by</span>
      <select
        className="hairline rounded-full bg-transparent px-3 py-1 font-mono text-[11px] uppercase tracking-widest text-foreground focus:outline-none focus:ring-1 focus:ring-foreground"
        value={value}
        onChange={(e) => {
          const next = e.target.value as SortKey;
          const meta = LABELS.find((l) => l.value === next);
          if (next === "highest_rated") {
            onChange("relevance", meta?.disabledHint);
          } else {
            onChange(next);
          }
        }}
        aria-label="Sort results"
      >
        {LABELS.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </label>
  );
}
