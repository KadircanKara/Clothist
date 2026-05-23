"use client";

import { formatPrice } from "@/lib/utils";
import type { ParsedIntent, SearchParams } from "@/lib/types";

const CURRENCY_SYMBOL: Record<string, string> = {
  USD: "$",
  EUR: "€",
  GBP: "£",
  TRY: "₺",
  JPY: "¥",
  CAD: "C$",
  AUD: "A$",
};

type Chip = {
  key: string;
  label: React.ReactNode;
  ariaLabel?: string;
  remove: () => void;
  rich?: boolean;
};

function buildChips(
  parsed: ParsedIntent,
  filters: SearchParams,
  fxDate: string | null,
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

  // Currency-conversion chip (combined for min/max). Renders the native
  // amount + USD equivalent + FX snapshot date when the user typed in a
  // non-USD currency.
  const currency = parsed.detected_currency;
  const nativeAmount = parsed.detected_amount_native;
  if (parsed.max_price !== null && filters.max_price === parsed.max_price) {
    if (currency && currency !== "USD" && nativeAmount) {
      const sym = CURRENCY_SYMBOL[currency] ?? currency;
      chips.push({
        key: "max_price",
        rich: true,
        label: (
          <div className="text-left">
            <div className="font-mono text-[11px] uppercase tracking-widest">
              {nativeAmount} {sym} ≤ MAX
            </div>
            <div className="mono-fx mt-1 normal-case">
              ≈ {formatPrice(parsed.max_price, "USD")} USD
              {fxDate && <> · fx {fxDate}</>}
            </div>
          </div>
        ),
        ariaLabel: `Maximum price ${nativeAmount} ${currency}, approximately ${formatPrice(parsed.max_price, "USD")}. Click to remove.`,
        remove: clear("max_price"),
      });
    } else {
      chips.push({
        key: "max_price",
        label: `≤ ${formatPrice(parsed.max_price, "USD")}`,
        remove: clear("max_price"),
      });
    }
  }
  if (parsed.min_price !== null && filters.min_price === parsed.min_price) {
    if (currency && currency !== "USD" && nativeAmount && parsed.max_price === null) {
      const sym = CURRENCY_SYMBOL[currency] ?? currency;
      chips.push({
        key: "min_price",
        rich: true,
        label: (
          <div className="text-left">
            <div className="font-mono text-[11px] uppercase tracking-widest">
              {nativeAmount} {sym} ≥ MIN
            </div>
            <div className="mono-fx mt-1 normal-case">
              ≈ {formatPrice(parsed.min_price, "USD")} USD
              {fxDate && <> · fx {fxDate}</>}
            </div>
          </div>
        ),
        ariaLabel: `Minimum price ${nativeAmount} ${currency}, approximately ${formatPrice(parsed.min_price, "USD")}. Click to remove.`,
        remove: clear("min_price"),
      });
    } else {
      chips.push({
        key: "min_price",
        label: `≥ ${formatPrice(parsed.min_price, "USD")}`,
        remove: clear("min_price"),
      });
    }
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
      label: `Refined: “${parsed.refined_query}”`,
      remove: clear("q"),
    });
  }

  // Feature chips (must-have)
  for (const feature of parsed.features) {
    const list = filters.features ?? [];
    if (!list.includes(feature)) continue;
    chips.push({
      key: `feature:${feature}`,
      label: `✓ ${humanizeFeature(feature)}`,
      remove: () =>
        onChange({
          ...filters,
          features: list.filter((f) => f !== feature),
          offset: 0,
        }),
    });
  }

  // Excluded feature chips
  for (const feature of parsed.excluded_features) {
    const list = filters.excluded_features ?? [];
    if (!list.includes(feature)) continue;
    chips.push({
      key: `excluded_feature:${feature}`,
      label: (
        <span>
          <span aria-hidden>✗ </span>
          <span className="line-through opacity-80">{humanizeFeature(feature)}</span>
        </span>
      ),
      remove: () =>
        onChange({
          ...filters,
          excluded_features: list.filter((f) => f !== feature),
          offset: 0,
        }),
    });
  }

  return chips;
}

function humanizeFeature(token: string): string {
  return token.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}

type Props = {
  parsed: ParsedIntent | null;
  filters: SearchParams;
  fxDate: string | null;
  onChange: (next: SearchParams) => void;
};

export function IntentChips({ parsed, filters, fxDate, onChange }: Props) {
  if (!parsed) return null;
  const chips = buildChips(parsed, filters, fxDate, onChange);
  if (chips.length === 0 && !parsed.explanation) return null;

  return (
    <div className="anim-fade hairline rounded-sm bg-bg-alt/40 px-4 py-3 mb-4">
      <div className="flex items-baseline justify-between gap-4">
        <span className="kicker">Interpreted by AI</span>
        {parsed.explanation && (
          <span className="serif-eyebrow text-right">
            &ldquo;{parsed.explanation}&rdquo;
          </span>
        )}
      </div>
      {chips.length > 0 && (
        <ul
          role="group"
          aria-label="Active AI-derived filters"
          className="mt-3 flex flex-wrap items-stretch gap-2"
        >
          {chips.map((c) => (
            <li key={c.key}>
              <button
                type="button"
                onClick={c.remove}
                className={[
                  "group inline-flex items-center gap-2 hairline rounded-full",
                  c.rich ? "px-3 py-1.5" : "px-3 py-1 h-8",
                  "font-mono text-[11px] uppercase tracking-widest text-foreground",
                  "hover:bg-foreground hover:text-background transition-colors",
                ].join(" ")}
                aria-label={c.ariaLabel ?? (typeof c.label === "string" ? `Remove filter: ${c.label}` : "Remove filter")}
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
