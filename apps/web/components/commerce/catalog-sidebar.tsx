"use client";

import { useState } from "react";
import { colorBackground, humanizeColor } from "@/lib/colors";
import type { FacetsResponse } from "@/lib/types";

export type CatalogFilters = {
  // Multi-select. Empty = "All" (the implicit catch-all state).
  categories: string[];
  // Multi-select brand. Same shape as categories.
  brands: string[];
  color?: string;
  features: string[];
  inStockOnly: boolean;
};

type Props = {
  facets: FacetsResponse | undefined;
  filters: CatalogFilters;
  onChange: (next: CatalogFilters) => void;
  // The unfiltered total for the current GENDER context — what should
  // appear next to the "All" chip. Distinct from the filtered total
  // that the page header shows next to the eyebrow.
  allCount: number;
};

export function CatalogSidebar({ facets, filters, onChange, allCount }: Props) {
  const selectedCategories = new Set(filters.categories);
  const selectedBrands = new Set(filters.brands);
  return (
    <aside
      aria-label="Catalog filters"
      className="self-start lg:sticky lg:top-32 space-y-10 lg:max-h-[calc(100vh-180px)] lg:overflow-y-auto lg:pr-4"
    >
      <Section title="Category" index="01">
        <ul className="space-y-px">
          <FacetRow
            label="All"
            count={allCount}
            active={selectedCategories.size === 0}
            onClick={() => onChange({ ...filters, categories: [] })}
          />
          {facets?.categories.map((c) => {
            const checked = selectedCategories.has(c.value);
            return (
              <FacetRow
                key={c.value}
                label={c.value}
                count={c.count}
                active={checked}
                checkbox
                onClick={() => {
                  // Multi-select toggle: clicking adds the category if
                  // missing, removes it if already selected. Empty array
                  // = the implicit "All" state.
                  const next = checked
                    ? filters.categories.filter((x) => x !== c.value)
                    : [...filters.categories, c.value];
                  onChange({ ...filters, categories: next });
                }}
              />
            );
          })}
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

      <Section title="Brand" index="03" collapsible defaultOpen={false}>
        <ul className="space-y-px">
          {facets?.brands.map((b) => {
            const checked = selectedBrands.has(b.value);
            return (
              <FacetRow
                key={b.value}
                label={b.value}
                count={b.count}
                active={checked}
                checkbox
                onClick={() => {
                  // Multi-select toggle, mirrors the Category section.
                  const next = checked
                    ? filters.brands.filter((x) => x !== b.value)
                    : [...filters.brands, b.value];
                  onChange({ ...filters, brands: next });
                }}
              />
            );
          })}
        </ul>
      </Section>

      {/* Features and Availability sections removed per UX feedback —
          they added noise without driving meaningful filter behavior on
          the current catalog. The CatalogFilters type still carries
          `features` and `inStockOnly` so URL state round-trips, but the
          sidebar no longer surfaces controls for them. */}

      {(filters.categories.length > 0 || filters.brands.length > 0 || filters.color || filters.features.length > 0 || filters.inStockOnly) && (
        <button
          type="button"
          onClick={() =>
            onChange({
              categories: [],
              brands: [],
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

function FacetCheckbox({ checked }: { checked: boolean }) {
  // Matches the Features section's checkbox style so multi-select
  // categories read consistently as "tickable" rather than a one-of
  // selection.
  return (
    <span
      aria-hidden
      className={[
        "grid h-4 w-4 shrink-0 place-items-center border transition-colors",
        checked
          ? "bg-foreground border-foreground"
          : "border-line/25 group-hover:border-foreground",
      ].join(" ")}
    >
      {checked && (
        <svg
          viewBox="0 0 10 10"
          className="h-2.5 w-2.5 stroke-background"
          strokeWidth="2"
          fill="none"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M1.5 5.5 L4 8 L8.5 2.5" />
        </svg>
      )}
    </span>
  );
}

function FacetRow({
  label,
  count,
  active,
  checkbox = false,
  onClick,
}: {
  label: string;
  count: number;
  active: boolean;
  // When true, show a visible checkbox indicator on the left so the
  // multi-select state is obvious at a glance. Used for category chips;
  // omitted for the "All" reset row which is a one-shot action.
  checkbox?: boolean;
  onClick: () => void;
}) {
  return (
    <li>
      <button
        type="button"
        onClick={onClick}
        aria-pressed={active}
        className={[
          "group flex w-full items-center justify-between gap-3 py-1.5 text-left transition-colors",
          active ? "text-foreground" : "text-muted hover:text-foreground",
        ].join(" ")}
      >
        <span className="flex min-w-0 items-center gap-3">
          {checkbox && <FacetCheckbox checked={active} />}
          <span className="truncate text-[14px] capitalize">{label}</span>
        </span>
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
