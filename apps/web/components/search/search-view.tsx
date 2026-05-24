"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  CatalogSidebar,
  type CatalogFilters,
} from "@/components/commerce/catalog-sidebar";
import { CommerceHeader } from "@/components/commerce/commerce-header";
import { AmbiguityNudge } from "./ambiguity-nudge";
import { DegradedBanner } from "./degraded-banner";
import { ExampleQueries } from "./example-queries";
import { IntentChips } from "./intent-chips";
import { ProductCard } from "./product-card";
import { SkeletonGrid } from "./skeleton-grid";
import { StagedLoader, type LoaderStage } from "./staged-loader";
import { ApiError, parseIntent, searchProducts } from "@/lib/api";
import { deriveFacets } from "@/lib/derive-facets";
import type {
  IntentResponse,
  SearchParams,
  SortKey,
} from "@/lib/types";

function toArr(v: string | string[] | undefined): string[] {
  if (!v) return [];
  return Array.isArray(v) ? v : [v];
}

const PAGE_SIZE = 24;

const SORT_LABELS: { value: SortKey; label: string }[] = [
  { value: "relevance", label: "Featured" },
  { value: "newest", label: "Newest" },
  { value: "price_asc", label: "Price ↑" },
  { value: "price_desc", label: "Price ↓" },
];

function paramsFromUrl(sp: URLSearchParams): SearchParams {
  const num = (k: string) => {
    const v = sp.get(k);
    return v ? Number(v) : undefined;
  };
  const features = sp.getAll("features");
  const excluded = sp.getAll("excluded_features");
  const sortRaw = sp.get("sort") ?? undefined;
  const sort = (
    sortRaw && ["relevance", "price_asc", "price_desc", "newest", "highest_rated"].includes(sortRaw)
      ? (sortRaw as SortKey)
      : undefined
  );
  return {
    q: sp.get("q") ?? undefined,
    category: (() => {
      const all = sp.getAll("category");
      return all.length === 0 ? undefined : all.length === 1 ? all[0] : all;
    })(),
    brand: (() => {
      const all = sp.getAll("brand");
      return all.length === 0 ? undefined : all.length === 1 ? all[0] : all;
    })(),
    color: sp.get("color") ?? undefined,
    min_price: num("min_price"),
    max_price: num("max_price"),
    in_stock_only: sp.get("in_stock_only") === "true" || undefined,
    features: features.length ? features : undefined,
    excluded_features: excluded.length ? excluded : undefined,
    sort,
    limit: PAGE_SIZE,
    offset: num("offset") ?? 0,
  };
}

function paramsToUrl(p: SearchParams): string {
  const usp = new URLSearchParams();
  if (p.q) usp.set("q", p.q);
  if (p.category) {
    for (const c of Array.isArray(p.category) ? p.category : [p.category]) {
      usp.append("category", c);
    }
  }
  if (p.brand) {
    for (const b of Array.isArray(p.brand) ? p.brand : [p.brand]) {
      usp.append("brand", b);
    }
  }
  if (p.color) usp.set("color", p.color);
  if (p.min_price !== undefined) usp.set("min_price", String(p.min_price));
  if (p.max_price !== undefined) usp.set("max_price", String(p.max_price));
  if (p.in_stock_only) usp.set("in_stock_only", "true");
  if (p.features) for (const f of p.features) usp.append("features", f);
  if (p.excluded_features)
    for (const f of p.excluded_features) usp.append("excluded_features", f);
  if (p.sort && p.sort !== "relevance") usp.set("sort", p.sort);
  if (p.offset) usp.set("offset", String(p.offset));
  const qs = usp.toString();
  return qs ? `/search?${qs}` : "/search";
}

/** Has the user actually run a search? Used to switch between the
 * landing-style hero and the results-grid layout. */
function hasSearchInput(p: SearchParams): boolean {
  return Boolean(
    p.q ||
      (Array.isArray(p.category) ? p.category.length > 0 : p.category) ||
      (Array.isArray(p.brand) ? p.brand.length > 0 : p.brand) ||
      p.color ||
      (p.features && p.features.length > 0) ||
      p.min_price !== undefined ||
      p.max_price !== undefined ||
      p.in_stock_only,
  );
}

export function SearchView() {
  const router = useRouter();
  const urlParams = useSearchParams();
  const filters = useMemo(() => paramsFromUrl(urlParams), [urlParams]);

  const [queryInput, setQueryInput] = useState(filters.q ?? "");
  const [intent, setIntent] = useState<IntentResponse | null>(null);
  const [parsing, setParsing] = useState(false);
  const [rateLimited, setRateLimited] = useState(false);
  const [networkError, setNetworkError] = useState<string | null>(null);
  // True from the moment the user submits until results land. Drives
  // both the staged loader and the "hide hero, show grid" layout
  // transition.
  const [activeSearch, setActiveSearch] = useState(false);

  useEffect(() => {
    setQueryInput(filters.q ?? "");
  }, [filters.q]);

  const pushFilters = useCallback(
    (next: SearchParams) => {
      router.replace(paramsToUrl(next), { scroll: false });
    },
    [router],
  );

  const applyIntent = useCallback(
    (res: IntentResponse) => {
      const p = res.parsed;
      pushFilters({
        ...filters,
        category: p.category ?? undefined,
        brand: p.brand ?? undefined,
        color: p.color ? p.color.toLowerCase() : undefined,
        min_price: p.min_price ?? undefined,
        max_price: p.max_price ?? undefined,
        in_stock_only: p.in_stock_only || undefined,
        features: p.features.length ? p.features : undefined,
        excluded_features: p.excluded_features.length ? p.excluded_features : undefined,
        sort: p.sort,
        q: p.refined_query?.trim() || undefined,
        offset: 0,
      });
    },
    [filters, pushFilters],
  );

  const submitSearch = async (e?: React.FormEvent, qOverride?: string) => {
    e?.preventDefault();
    const trimmed = (qOverride ?? queryInput).trim();
    setNetworkError(null);
    setRateLimited(false);

    if (!trimmed) return;

    setActiveSearch(true);
    setParsing(true);
    try {
      const res = await parseIntent(trimmed);
      setIntent(res);
      applyIntent(res);
    } catch (err) {
      if (err instanceof ApiError && err.status === 429) {
        setRateLimited(true);
      } else {
        setNetworkError("Couldn't reach the AI parser. Falling back to keyword search.");
      }
      setIntent(null);
      pushFilters({ ...filters, q: trimmed, offset: 0 });
    } finally {
      setParsing(false);
    }
  };

  const pickExample = (q: string) => {
    setQueryInput(q);
    void submitSearch(undefined, q);
  };

  const clearSearch = () => {
    setQueryInput("");
    setIntent(null);
    setRateLimited(false);
    setNetworkError(null);
    setActiveSearch(false);
    pushFilters({});
  };

  // Live URL state determines whether we render the hero or the grid.
  const showHero = !hasSearchInput(filters) && !activeSearch;

  // Translate URL filters to the catalog-sidebar's multi-select shape.
  const sidebarFilters: CatalogFilters = useMemo(
    () => ({
      categories: toArr(filters.category),
      brands: toArr(filters.brand),
      color: filters.color,
      features: filters.features ?? [],
      inStockOnly: !!filters.in_stock_only,
    }),
    [filters],
  );

  const onSidebarChange = (next: CatalogFilters) => {
    pushFilters({
      ...filters,
      category: next.categories.length ? next.categories : undefined,
      brand: next.brands.length ? next.brands : undefined,
      color: next.color,
      features: next.features.length ? next.features : undefined,
      in_stock_only: next.inStockOnly || undefined,
      offset: 0,
    });
  };

  // Only fetch when there's an actual query or filter — keeps /search
  // clean before the user types anything.
  const search = useQuery({
    queryKey: ["search", filters],
    queryFn: () => searchProducts(filters),
    enabled: hasSearchInput(filters),
  });

  // Once results arrive (or fail) we can release activeSearch — the
  // grid takes over.
  useEffect(() => {
    if (activeSearch && !parsing && !search.isFetching) {
      // Brief dwell so the third loader stage actually reads instead of
      // flashing past.
      const t = setTimeout(() => setActiveSearch(false), 380);
      return () => clearTimeout(t);
    }
  }, [activeSearch, parsing, search.isFetching]);

  // Staged loader signal: stage 1 = parsing, stage 2 = catalog fetch,
  // stage 3 = post-fetch dwell before reveal.
  const stage: LoaderStage = parsing
    ? 1
    : search.isFetching
      ? 2
      : activeSearch
        ? 3
        : 0;

  const total = search.data?.total ?? 0;
  const items = search.data?.items ?? [];
  const offset = filters.offset ?? 0;
  const hasNext = offset + items.length < total;
  const hasPrev = offset > 0;
  const currentSort: SortKey = filters.sort ?? "relevance";
  const requestedFeatures = filters.features ?? intent?.parsed.features ?? [];

  // Derived facets — only chips that actually appear in the returned
  // products. Falls back to an empty shape while loading.
  const derivedFacets = useMemo(
    () => (items.length > 0 ? deriveFacets(items) : null),
    [items],
  );
  const allCount = items.length;

  return (
    <div className="relative z-10 min-h-screen">
      <CommerceHeader />

      {showHero ? (
        <HeroPane
          queryInput={queryInput}
          onChange={setQueryInput}
          onSubmit={submitSearch}
          onPickExample={pickExample}
          stage={stage}
          parsing={parsing}
        />
      ) : (
        <ResultsPane
          queryInput={queryInput}
          onChange={setQueryInput}
          onSubmit={submitSearch}
          onClear={clearSearch}
          parsing={parsing}
          stage={stage}
          rateLimited={rateLimited}
          networkError={networkError}
          intent={intent}
          filters={filters}
          pushFilters={pushFilters}
          search={search}
          requestedFeatures={requestedFeatures}
          currentSort={currentSort}
          total={total}
          items={items}
          offset={offset}
          hasNext={hasNext}
          hasPrev={hasPrev}
          sidebarFilters={sidebarFilters}
          onSidebarChange={onSidebarChange}
          derivedFacets={derivedFacets}
          allCount={allCount}
          acceptAmbiguity={(alt) => {
            const original = intent?.raw_query ?? queryInput;
            const hintToken = intent?.parsed.ambiguity_hint?.token;
            if (!hintToken) return;
            const rewritten = original.replace(
              hintToken,
              hintToken.replace(/[\d.,]+/, alt),
            );
            setQueryInput(rewritten);
            void submitSearch(undefined, rewritten);
          }}
        />
      )}
    </div>
  );
}

/* -----------------------------------------------------------------
 * Hero pane — landing-style entry state
 * ---------------------------------------------------------------- */

function HeroPane({
  queryInput,
  onChange,
  onSubmit,
  onPickExample,
  stage,
  parsing,
}: {
  queryInput: string;
  onChange: (v: string) => void;
  onSubmit: (e?: React.FormEvent) => void;
  onPickExample: (q: string) => void;
  stage: LoaderStage;
  parsing: boolean;
}) {
  return (
    <section className="relative px-6 pt-16 pb-32 lg:px-12 lg:pt-24 lg:pb-44">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-y-0 left-6 right-6 lg:left-12 lg:right-12"
      >
        <div className="absolute inset-y-0 left-0 w-px bg-line/[0.06]" />
        <div className="absolute inset-y-0 right-0 w-px bg-line/[0.06]" />
      </div>

      <div className="relative mx-auto max-w-[1280px]">
        <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted">
          — Try the search
        </p>
        <h1
          className="
            mt-10 font-display-tight leading-[0.86] tracking-[-0.045em] text-foreground
          "
          style={{ fontSize: "clamp(48px, 9vw, 140px)" }}
        >
          <span className="block anim-rise" style={{ animationDelay: "60ms" }}>
            Describe it.
          </span>
          <span className="block anim-rise" style={{ animationDelay: "180ms" }}>
            <span className="text-foreground/30">Find it.</span>{" "}
            <span>Wear it.</span>
          </span>
        </h1>

        <form
          onSubmit={onSubmit}
          role="search"
          className="mt-16 anim-rise"
          style={{ animationDelay: "320ms" }}
        >
          <div className="hairline-b grid grid-cols-[minmax(0,1fr)_auto] gap-3 items-stretch">
            <div className="relative flex items-center">
              <span
                aria-hidden
                className="font-mono text-base text-muted/70 pr-3 select-none"
              >
                /
              </span>
              <input
                type="text"
                value={queryInput}
                onChange={(e) => onChange(e.target.value)}
                placeholder="vintage washed denim, loose fit"
                autoFocus
                enterKeyHint="search"
                className="
                  w-full bg-transparent
                  font-sans text-[clamp(20px,2.2vw,28px)] leading-tight
                  text-foreground placeholder:text-muted/55
                  py-5 pr-4 outline-none
                "
                spellCheck={false}
                aria-label="Describe what you're looking for"
              />
            </div>
            <button
              type="submit"
              disabled={parsing || !queryInput.trim()}
              className="
                self-center my-3 px-7 py-3
                bg-foreground text-background
                font-mono text-[11px] uppercase tracking-[0.22em]
                hover:bg-foreground/90 transition-colors
                disabled:opacity-40 disabled:pointer-events-none
                inline-flex items-center gap-2
              "
            >
              {parsing ? "Reading…" : "Search"}
              <svg
                viewBox="0 0 14 14"
                className="h-3.5 w-3.5"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden
              >
                <path d="M3 11L11 3" />
                <path d="M5 3h6v6" />
              </svg>
            </button>
          </div>
          <p className="mt-4 font-mono text-[10px] uppercase tracking-[0.22em] text-muted/80">
            ↵ Submits · AI parses to filters, then ranks across the catalog
          </p>
        </form>

        {stage > 0 && <StagedLoader stage={stage} />}

        {stage === 0 && (
          <div className="mt-14 anim-fade">
            <ExampleQueries onPick={onPickExample} fxDate={null} />
          </div>
        )}
      </div>
    </section>
  );
}

/* -----------------------------------------------------------------
 * Results pane — compact bar on top, grid + sidebar below
 * ---------------------------------------------------------------- */

type ResultsPaneProps = {
  queryInput: string;
  onChange: (v: string) => void;
  onSubmit: (e?: React.FormEvent) => void;
  onClear: () => void;
  parsing: boolean;
  stage: LoaderStage;
  rateLimited: boolean;
  networkError: string | null;
  intent: IntentResponse | null;
  filters: SearchParams;
  pushFilters: (next: SearchParams) => void;
  search: ReturnType<typeof useQuery>;
  requestedFeatures: string[];
  currentSort: SortKey;
  total: number;
  items: import("@/lib/types").Product[];
  offset: number;
  hasNext: boolean;
  hasPrev: boolean;
  sidebarFilters: CatalogFilters;
  onSidebarChange: (next: CatalogFilters) => void;
  derivedFacets: ReturnType<typeof deriveFacets> | null;
  allCount: number;
  acceptAmbiguity: (alt: string) => void;
};

function ResultsPane({
  queryInput,
  onChange,
  onSubmit,
  onClear,
  parsing,
  stage,
  rateLimited,
  networkError,
  intent,
  filters,
  pushFilters,
  search,
  requestedFeatures,
  currentSort,
  total,
  items,
  offset,
  hasNext,
  hasPrev,
  sidebarFilters,
  onSidebarChange,
  derivedFacets,
  allCount,
  acceptAmbiguity,
}: ResultsPaneProps) {
  return (
    <>
      {/* Compact search bar — sticks to the top of the results area */}
      <section className="hairline-b mx-auto max-w-[1600px] px-6 pt-8 pb-6 lg:px-12">
        <form
          onSubmit={onSubmit}
          role="search"
          className="grid grid-cols-[minmax(0,1fr)_auto] gap-3 items-center"
        >
          <div className="relative flex items-center hairline-b">
            <span aria-hidden className="font-mono text-sm text-muted/70 pr-2.5 select-none">
              /
            </span>
            <input
              type="text"
              value={queryInput}
              onChange={(e) => onChange(e.target.value)}
              placeholder="Describe what you're after…"
              enterKeyHint="search"
              spellCheck={false}
              className="w-full bg-transparent text-lg py-3 pr-3 outline-none placeholder:text-muted/55"
              aria-label="Describe what you're looking for"
            />
            {queryInput && (
              <button
                type="button"
                onClick={onClear}
                aria-label="Clear search"
                className="font-mono text-xs text-muted hover:text-foreground transition-colors px-2"
              >
                ×
              </button>
            )}
          </div>
          <button
            type="submit"
            disabled={parsing || !queryInput.trim()}
            className="
              shrink-0 px-5 py-3
              bg-foreground text-background
              font-mono text-[11px] uppercase tracking-[0.22em]
              hover:bg-foreground/90 transition-colors
              disabled:opacity-40 disabled:pointer-events-none
            "
          >
            {parsing ? "Reading…" : "Search"}
          </button>
        </form>
      </section>

      {/* Mid-flight: staged loader overlay sits where the grid will be */}
      {stage > 0 && (
        <section className="mx-auto max-w-[1600px] px-6 pt-16 pb-32 lg:px-12">
          <StagedLoader stage={stage} />
        </section>
      )}

      {stage === 0 && (
        <section className="mx-auto max-w-[1600px] px-6 pb-32 pt-10 lg:px-12">
          {intent?.degraded && intent.degraded_reason && (
            <DegradedBanner reason={intent.degraded_reason} />
          )}
          {rateLimited && (
            <div className="anim-fade mb-4 px-4 py-3 text-sm bg-bg-alt/40 border-l-[3px] border-warn">
              <span className="font-mono text-[11px] uppercase tracking-[0.18em] text-warn">
                Rate limited — retry in 60s
              </span>
            </div>
          )}
          {networkError && (
            <div className="anim-fade mb-4 px-4 py-3 text-sm bg-bg-alt/40 border-l-[3px] border-warn">
              <span className="font-mono text-[11px] uppercase tracking-[0.18em] text-warn">
                {networkError}
              </span>
            </div>
          )}

          <div className="grid grid-cols-1 gap-10 lg:grid-cols-[220px_minmax(0,1fr)] lg:gap-14">
            <div className="hidden lg:block">
              {derivedFacets ? (
                <CatalogSidebar
                  facets={derivedFacets}
                  filters={sidebarFilters}
                  onChange={onSidebarChange}
                  allCount={allCount}
                />
              ) : (
                <div className="space-y-3">
                  <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted">
                    Filters appear once results land.
                  </p>
                </div>
              )}
            </div>

            <div>
              <div className="flex flex-wrap items-center justify-between gap-4 pb-4">
                <span className="font-mono text-[11px] uppercase tracking-[0.22em] text-muted">
                  {total} {total === 1 ? "piece" : "pieces"}
                  {intent?.parsed.explanation
                    ? ` · ${intent.parsed.explanation}`
                    : ""}
                </span>
                <label className="inline-flex items-center gap-2">
                  <span className="sr-only">Sort</span>
                  <select
                    value={currentSort}
                    onChange={(e) =>
                      pushFilters({
                        ...filters,
                        sort: e.target.value as SortKey,
                        offset: 0,
                      })
                    }
                    className="bg-transparent border border-line/15 px-3 py-1.5 font-mono text-[11px] uppercase tracking-[0.18em] focus:outline-none focus:border-foreground transition-colors cursor-pointer"
                  >
                    {SORT_LABELS.map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              <IntentChips
                parsed={intent?.parsed ?? null}
                filters={filters}
                fxDate={null}
                onChange={pushFilters}
              />
              {intent?.parsed.ambiguity_hint && (
                <AmbiguityNudge
                  hint={intent.parsed.ambiguity_hint}
                  onAccept={acceptAmbiguity}
                />
              )}

              {search.isLoading ? (
                <SkeletonGrid />
              ) : items.length === 0 ? (
                <div className="border border-line/10 mt-2 flex flex-col items-center gap-3 py-24 text-center">
                  <span className="font-display text-4xl tracking-[-0.04em]">
                    Nothing matched.
                  </span>
                  <p className="text-sm text-muted">
                    Drop a filter or refine your query.
                  </p>
                  <button
                    type="button"
                    onClick={onClear}
                    className="mt-2 font-mono text-[10px] uppercase tracking-[0.22em] text-muted hover:text-foreground underline underline-offset-4"
                  >
                    Clear all
                  </button>
                </div>
              ) : (
                <ul className="mt-6 grid grid-cols-2 gap-x-6 gap-y-12 sm:grid-cols-2 lg:grid-cols-3">
                  {items.map((p, idx) => (
                    <li
                      key={p.id}
                      className="anim-rise"
                      style={{ animationDelay: `${Math.min(idx, 8) * 40}ms` }}
                    >
                      <ProductCard product={p} requestedFeatures={requestedFeatures} />
                    </li>
                  ))}
                </ul>
              )}

              {(hasNext || hasPrev) && (
                <div className="border-t border-line/10 mt-12 flex items-center justify-between pt-6">
                  <span className="font-mono text-[11px] uppercase tracking-[0.18em] text-muted">
                    {offset + 1}–{Math.min(offset + items.length, total)} / {total}
                  </span>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      disabled={!hasPrev}
                      onClick={() =>
                        pushFilters({
                          ...filters,
                          offset: Math.max(0, offset - PAGE_SIZE),
                        })
                      }
                      className="border border-line/15 px-3 py-2 font-mono text-[11px] uppercase tracking-[0.22em] hover:border-foreground transition-colors disabled:opacity-30 disabled:pointer-events-none"
                    >
                      ← Prev
                    </button>
                    <button
                      type="button"
                      disabled={!hasNext}
                      onClick={() =>
                        pushFilters({ ...filters, offset: offset + PAGE_SIZE })
                      }
                      className="border border-line/15 px-3 py-2 font-mono text-[11px] uppercase tracking-[0.22em] hover:border-foreground transition-colors disabled:opacity-30 disabled:pointer-events-none"
                    >
                      Next →
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </section>
      )}
    </>
  );
}
