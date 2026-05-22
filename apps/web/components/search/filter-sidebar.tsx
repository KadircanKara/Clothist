"use client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { FacetsResponse, SearchParams } from "@/lib/types";

type Props = {
  facets: FacetsResponse | undefined;
  filters: SearchParams;
  onChange: (next: SearchParams) => void;
};

export function FilterSidebar({ facets, filters, onChange }: Props) {
  const update = (patch: Partial<SearchParams>) =>
    onChange({ ...filters, ...patch, offset: 0 });

  return (
    <aside className="sticky top-6 space-y-8 self-start">
      <SectionHeader index="01" label="Category" />
      <ul className="space-y-px">
        <FacetItem
          label="All"
          active={!filters.category}
          onClick={() => update({ category: undefined })}
        />
        {facets?.categories.map((c) => (
          <FacetItem
            key={c.value}
            label={c.value}
            count={c.count}
            active={filters.category === c.value}
            onClick={() => update({ category: c.value })}
          />
        ))}
      </ul>

      <SectionHeader index="02" label="Brand" />
      <ul className="max-h-72 space-y-px overflow-y-auto pr-1">
        <FacetItem
          label="All"
          active={!filters.brand}
          onClick={() => update({ brand: undefined })}
        />
        {facets?.brands.map((b) => (
          <FacetItem
            key={b.value}
            label={b.value}
            count={b.count}
            active={filters.brand === b.value}
            onClick={() => update({ brand: b.value })}
          />
        ))}
      </ul>

      <div>
        <SectionHeader index="03" label="Price" />
        <div className="mt-3 flex items-center gap-3">
          <Input
            type="number"
            inputMode="decimal"
            placeholder="MIN"
            value={filters.min_price ?? ""}
            onChange={(e) =>
              update({ min_price: e.target.value ? Number(e.target.value) : undefined })
            }
            className="font-mono text-xs uppercase tracking-widest"
          />
          <span className="font-mono text-muted text-sm">—</span>
          <Input
            type="number"
            inputMode="decimal"
            placeholder="MAX"
            value={filters.max_price ?? ""}
            onChange={(e) =>
              update({ max_price: e.target.value ? Number(e.target.value) : undefined })
            }
            className="font-mono text-xs uppercase tracking-widest"
          />
        </div>
      </div>

      <div>
        <SectionHeader index="04" label="Availability" />
        <label className="mt-3 flex cursor-pointer items-center gap-3 select-none">
          <input
            type="checkbox"
            className="h-4 w-4 appearance-none border border-line/40 checked:border-accent checked:bg-accent transition-colors"
            checked={!!filters.in_stock_only}
            onChange={(e) => update({ in_stock_only: e.target.checked || undefined })}
          />
          <span className="font-mono text-xs uppercase tracking-widest">In stock only</span>
        </label>
      </div>

      <Button
        variant="outline"
        size="sm"
        className="w-full"
        onClick={() => onChange({ q: filters.q, offset: 0 })}
      >
        Reset filters
      </Button>
    </aside>
  );
}

function SectionHeader({ index, label }: { index: string; label: string }) {
  return (
    <div className="flex items-baseline justify-between hairline-b pb-2">
      <span className="kicker">
        {index} <span className="opacity-50">/</span> {label}
      </span>
    </div>
  );
}

function FacetItem({
  label,
  count,
  active,
  onClick,
}: {
  label: string;
  count?: number;
  active?: boolean;
  onClick: () => void;
}) {
  return (
    <li>
      <button
        onClick={onClick}
        className={[
          "flex w-full items-center justify-between py-1.5 text-left text-base transition-colors",
          active ? "text-accent" : "text-foreground hover:text-accent",
        ].join(" ")}
      >
        <span className="capitalize">{label}</span>
        {count !== undefined && (
          <span className="font-mono text-xs tracking-widest text-muted">{count}</span>
        )}
      </button>
    </li>
  );
}
