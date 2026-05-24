"use client";

import { useState } from "react";
import { colorBackground, humanizeColor } from "@/lib/colors";
import type { FacetsResponse } from "@/lib/types";

export type CatalogFilters = {
  category?: string;
  color?: string;
  features: string[];
  inStockOnly: boolean;
};

type Props = {
  facets: FacetsResponse | undefined;
  filters: CatalogFilters;
  onChange: (next: CatalogFilters) => void;
  totalCount: number;
};

export function CatalogSidebar({ facets, filters, onChange, totalCount }: Props) {
  return (
    <aside
      aria-label="Catalog filters"
      className="self-start lg:sticky lg:top-32 space-y-10 lg:max-h-[calc(100vh-180px)] lg:overflow-y-auto lg:pr-4"
    >
      <Section title="Category" index="01">
        <ul className="space-y-px">
          <FacetRow
            label="All"
            count={totalCount}
            active={!filters.category}
            onClick={() => onChange({ ...filters, category: undefined })}
          />
          {facets?.categories.map((c) => (
            <FacetRow
              key={c.value}
              label={c.value}
              count={c.count}
              active={filters.category === c.value}
              onClick={() => onChange({ ...filters, category: c.value })}
            />
          ))}
        </ul>
      </Section>

      <Section title="Color" index="02">
        <ul className="flex flex-wrap gap-2">
          <ColorDot
            label="Any"
            active={!filters.color}
            onClick={() => onChange({ ...filters, color: undefined })}
          />
          {facets?.colors.map((c) => (
            <ColorDot
              key={c.value}
              label={c.value}
              active={filters.color === c.value}
              onClick={() => onChange({ ...filters, color: c.value })}
            />
          ))}
        </ul>
      </Section>

      <Section title="Features" index="03" collapsible defaultOpen={false}>
        <ul className="grid grid-cols-1 gap-1.5">
          {facets?.features.map((f) => {
            const checked = filters.features.includes(f);
            return (
              <li key={f}>
                <label className="flex cursor-pointer items-center gap-3 select-none py-1 group">
                  <span
                    className={[
                      "grid h-4 w-4 place-items-center border transition-colors",
                      checked
                        ? "bg-foreground border-foreground"
                        : "border-line/25 group-hover:border-foreground",
                    ].join(" ")}
                    aria-hidden
                  >
                    {checked && (
                      <span className="block h-[2px] w-[2px] bg-background rounded-full" />
                    )}
                  </span>
                  <input
                    type="checkbox"
                    className="sr-only"
                    checked={checked}
                    onChange={() =>
                      onChange({
                        ...filters,
                        features: checked
                          ? filters.features.filter((x) => x !== f)
                          : [...filters.features, f],
                      })
                    }
                  />
                  <span className="font-mono text-[11px] uppercase tracking-[0.12em] group-hover:text-foreground">
                    {f.replace(/_/g, " ")}
                  </span>
                </label>
              </li>
            );
          })}
        </ul>
      </Section>

      <Section title="Availability" index="04">
        <label className="flex cursor-pointer items-center gap-3 select-none group">
          <span
            className={[
              "grid h-4 w-4 place-items-center border transition-colors",
              filters.inStockOnly
                ? "bg-foreground border-foreground"
                : "border-line/25 group-hover:border-foreground",
            ].join(" ")}
            aria-hidden
          >
            {filters.inStockOnly && (
              <span className="block h-[2px] w-[2px] bg-background rounded-full" />
            )}
          </span>
          <input
            type="checkbox"
            className="sr-only"
            checked={filters.inStockOnly}
            onChange={(e) =>
              onChange({ ...filters, inStockOnly: e.target.checked })
            }
          />
          <span className="font-mono text-[11px] uppercase tracking-[0.12em]">
            In stock only
          </span>
        </label>
      </Section>

      {(filters.category || filters.color || filters.features.length > 0 || filters.inStockOnly) && (
        <button
          type="button"
          onClick={() =>
            onChange({
              category: undefined,
              color: undefined,
              features: [],
              inStockOnly: false,
            })
          }
          className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted hover:text-foreground underline underline-offset-4"
        >
          Reset all filters
        </button>
      )}
    </aside>
  );
}

function Section({
  title,
  index,
  children,
  collapsible = false,
  defaultOpen = true,
}: {
  title: string;
  index: string;
  children: React.ReactNode;
  collapsible?: boolean;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div>
      <button
        type="button"
        onClick={() => collapsible && setOpen((o) => !o)}
        className={[
          "flex items-baseline justify-between w-full pb-2 border-b border-line/10",
          collapsible ? "cursor-pointer" : "cursor-default",
        ].join(" ")}
        aria-expanded={collapsible ? open : undefined}
      >
        <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted">
          {index} <span className="opacity-50">/</span> {title}
        </span>
        {collapsible && (
          <span aria-hidden className="font-mono text-muted text-sm leading-none">
            {open ? "−" : "+"}
          </span>
        )}
      </button>
      {(!collapsible || open) && <div className="mt-3.5">{children}</div>}
    </div>
  );
}

function FacetRow({
  label,
  count,
  active,
  onClick,
}: {
  label: string;
  count: number;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <li>
      <button
        type="button"
        onClick={onClick}
        aria-pressed={active}
        className={[
          "flex w-full items-baseline justify-between py-1.5 text-left transition-colors",
          active ? "text-foreground" : "text-muted hover:text-foreground",
        ].join(" ")}
      >
        <span className="text-[14px] capitalize">{label}</span>
        <span className="font-mono text-[10px] tracking-[0.18em]">{count}</span>
      </button>
    </li>
  );
}

function ColorDot({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  const display = humanizeColor(label);
  const bg = label === "Any" ? "transparent" : colorBackground(label);
  return (
    <li>
      <button
        type="button"
        onClick={onClick}
        aria-pressed={active}
        aria-label={`Filter by color: ${display}`}
        className={[
          "group relative grid h-9 w-9 place-items-center rounded-full transition-all",
          active
            ? "outline outline-1 outline-foreground outline-offset-2"
            : "hover:outline hover:outline-1 hover:outline-foreground/40 hover:outline-offset-2",
        ].join(" ")}
      >
        {label === "Any" ? (
          <span className="block h-7 w-7 rounded-full ring-1 ring-line/30 bg-transparent grid place-items-center font-mono text-[9px] uppercase text-muted">
            ALL
          </span>
        ) : (
          <span
            className="block h-7 w-7 rounded-full ring-1 ring-line/20"
            style={{ background: bg }}
          />
        )}
        {/* Hover tooltip — appears below the swatch */}
        <span
          role="tooltip"
          className="pointer-events-none absolute top-full mt-1.5 left-1/2 -translate-x-1/2 whitespace-nowrap bg-foreground text-background font-mono text-[9px] uppercase tracking-[0.16em] px-2 py-1 opacity-0 group-hover:opacity-100 group-focus-visible:opacity-100 transition-opacity z-10"
        >
          {display}
        </span>
      </button>
    </li>
  );
}
