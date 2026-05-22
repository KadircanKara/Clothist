"use client";

import { formatPrice } from "@/lib/utils";
import type { ParsedIntent, SearchParams } from "@/lib/types";

type Chip = {
  key: keyof SearchParams;
  label: string;
  remove: () => void;
};

function buildChips(
  parsed: ParsedIntent,
  filters: SearchParams,
  onChange: (next: SearchParams) => void,
): Chip[] {
  const clear = (k: keyof SearchParams) => () =>
    onChange({ ...filters, [k]: undefined, offset: 0 });

  const chips: Chip[] = [];

  if (parsed.category && filters.category === parsed.category) {
    chips.push({
      key: "category",
      label: `Category · ${parsed.category}`,
      remove: clear("category"),
    });
  }
  if (parsed.brand && filters.brand === parsed.brand) {
    chips.push({
      key: "brand",
      label: `Brand · ${parsed.brand}`,
      remove: clear("brand"),
    });
  }
  if (parsed.color && filters.color === parsed.color) {
    chips.push({
      key: "color",
      label: `Color · ${parsed.color}`,
      remove: clear("color"),
    });
  }
  if (parsed.min_price !== null && filters.min_price === parsed.min_price) {
    chips.push({
      key: "min_price",
      label: `≥ ${formatPrice(parsed.min_price, "USD")}`,
      remove: clear("min_price"),
    });
  }
  if (parsed.max_price !== null && filters.max_price === parsed.max_price) {
    chips.push({
      key: "max_price",
      label: `≤ ${formatPrice(parsed.max_price, "USD")}`,
      remove: clear("max_price"),
    });
  }
  if (parsed.in_stock_only && filters.in_stock_only) {
    chips.push({
      key: "in_stock_only",
      label: "In stock only",
      remove: clear("in_stock_only"),
    });
  }
  if (parsed.refined_query && filters.q === parsed.refined_query) {
    chips.push({
      key: "q",
      label: `“${parsed.refined_query}”`,
      remove: clear("q"),
    });
  }

  return chips;
}

type Props = {
  parsed: ParsedIntent | null;
  filters: SearchParams;
  onChange: (next: SearchParams) => void;
};

export function IntentChips({ parsed, filters, onChange }: Props) {
  if (!parsed) return null;
  const chips = buildChips(parsed, filters, onChange);
  if (chips.length === 0 && !parsed.explanation) return null;

  return (
    <div className="anim-fade hairline rounded-sm bg-bg-alt/40 px-4 py-3 mb-6">
      <div className="flex items-baseline justify-between gap-4">
        <span className="kicker">Interpreted by AI</span>
        {parsed.explanation && (
          <span className="font-serif italic text-base text-foreground/80 text-right">
            {parsed.explanation}
          </span>
        )}
      </div>
      {chips.length > 0 && (
        <ul className="mt-3 flex flex-wrap gap-2">
          {chips.map((c) => (
            <li key={c.key}>
              <button
                type="button"
                onClick={c.remove}
                className="group inline-flex items-center gap-2 hairline rounded-full px-3 py-1 font-mono text-[11px] uppercase tracking-widest text-foreground hover:bg-foreground hover:text-background transition-colors"
                aria-label={`Remove filter: ${c.label}`}
              >
                <span>{c.label}</span>
                <span aria-hidden className="text-muted group-hover:text-background">
                  ×
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
