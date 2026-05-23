"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { AmbiguityNudge } from "./ambiguity-nudge";
import { DegradedBanner } from "./degraded-banner";
import { EmptyState } from "./empty-state";
import { ExampleQueries } from "./example-queries";
import { FilterSidebar } from "./filter-sidebar";
import { HeroBackdrop } from "./hero-backdrop";
import { IntentChips } from "./intent-chips";
import { MobileFilterSheet } from "./mobile-filter-sheet";
import { ProductCard } from "./product-card";
import { SkeletonGrid } from "./skeleton-grid";
import { SortControl } from "./sort-control";
import { StickySearchBar } from "./sticky-search-bar";
import { Wordmark } from "./wordmark";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import { ApiError, getFacets, parseIntent, searchProducts } from "@/lib/api";
import type { IntentResponse, SearchParams, SortKey } from "@/lib/types";

const PAGE_SIZE = 24;

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
    category: sp.get("category") ?? undefined,
    brand: sp.get("brand") ?? undefined,
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
  if (p.category) usp.set("category", p.category);
  if (p.brand) usp.set("brand", p.brand);
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
  return qs ? `/?${qs}` : "/";
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
  const [filterSheetOpen, setFilterSheetOpen] = useState(false);
  const [sortHint, setSortHint] = useState<string | null>(null);

  const heroSentinelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setQueryInput(filters.q ?? "");
  }, [filters.q]);

  const pushFilters = useCallback(
    (next: SearchParams) => {
      router.replace(paramsToUrl(next), { scroll: false });
    },
    [router],
  );

  const submitPlainSearch = (rawQ: string) => {
    pushFilters({ ...filters, q: rawQ || undefined, offset: 0 });
  };

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

    if (!trimmed) {
      setIntent(null);
      submitPlainSearch("");
      return;
    }

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
      submitPlainSearch(trimmed);
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
    setSortHint(null);
    pushFilters({});
  };

  const onSortChange = (next: SortKey, hint?: string) => {
    setSortHint(hint ?? null);
    pushFilters({ ...filters, sort: next, offset: 0 });
  };

  const acceptAmbiguity = (alternative: string) => {
    const original = intent?.raw_query ?? queryInput;
    const hintToken = intent?.parsed.ambiguity_hint?.token;
    if (!hintToken) return;
    // Replace the token in the raw query with the alternative form and re-submit.
    const rewritten = original.replace(hintToken, hintToken.replace(/[\d.,]+/, alternative));
    setQueryInput(rewritten);
    void submitSearch(undefined, rewritten);
  };

  const dirty = (queryInput.trim() || undefined) !== (filters.q || undefined);

  const search = useQuery({
    queryKey: ["search", filters],
    queryFn: () => searchProducts(filters),
  });

  const facets = useQuery({
    queryKey: ["facets"],
    queryFn: getFacets,
    staleTime: 60_000,
  });

  const total = search.data?.total ?? 0;
  const items = search.data?.items ?? [];
  const offset = filters.offset ?? 0;
  const hasNext = offset + items.length < total;
  const hasPrev = offset > 0;
  const fxDate = facets.data?.fx_date ?? null;
  const currentSort: SortKey = filters.sort ?? "relevance";
  const requestedFeatures = filters.features ?? intent?.parsed.features ?? [];

  return (
    <div className="relative z-10">
      <StickySearchBar
        value={queryInput}
        onChange={setQueryInput}
        onSubmit={() => void submitSearch()}
        onOpenFilters={() => setFilterSheetOpen(true)}
        sentinelTarget={heroSentinelRef}
      />

      {/* -------- Utility bar -------- */}
      <div className="mx-auto max-w-[1600px] px-6 pt-6 lg:px-10">
        <div className="flex items-center justify-between">
          <div className="kicker anim-fade">
            CLOTHIST <span className="text-foreground/40">·</span> 01 / Discovery
          </div>
          <ThemeToggle className="anim-fade delay-100" />
        </div>
      </div>

      {/* -------- Hero band -------- */}
      <section
        className="relative mx-auto max-w-[1600px] overflow-hidden px-6 pb-14 pt-10 lg:px-10"
      >
        <HeroBackdrop />

        <div className="relative z-10 grid grid-cols-1 gap-10 lg:grid-cols-12 lg:items-end">
          <div className="lg:col-span-8">
            <p className="kicker anim-fade delay-200">
              AI-native fashion meta-commerce — est. 2026
            </p>
            <div className="anim-rise delay-300 mt-3">
              <Wordmark />
            </div>
            <p className="anim-rise delay-500 mt-6 max-w-xl text-base leading-relaxed text-muted">
              Type the piece you&rsquo;re picturing. Cargo pants with six pockets, a
              minimalist hoodie with a hidden zip, a waterproof shell that
              actually lasts. We search across the retailers — you skip the
              tabs.
            </p>

            {!filters.q && !intent && (
              <ExampleQueries onPick={pickExample} fxDate={fxDate} />
            )}
          </div>

          <div className="lg:col-span-4 anim-rise delay-700">
            <label htmlFor="clothist-search" className="kicker block">
              Search
            </label>
            <form onSubmit={(e) => void submitSearch(e)} role="search">
              <div className="mt-2 flex items-center gap-3 border-b border-line/20 py-1 focus-within:border-foreground transition-colors">
                <span className="font-mono text-sm text-muted">/</span>
                <Input
                  id="clothist-search"
                  value={queryInput}
                  onChange={(e) => setQueryInput(e.target.value)}
                  placeholder="black cargo pants under $100"
                  autoFocus
                  enterKeyHint="search"
                  className="h-12 border-b-0 px-0 text-lg placeholder:text-muted/70 focus-visible:border-b-0"
                />
                {queryInput && (
                  <button
                    type="button"
                    onClick={clearSearch}
                    aria-label="Clear search"
                    className="font-mono text-xs text-muted hover:text-foreground transition-colors"
                  >
                    ×
                  </button>
                )}
                <Button
                  type="submit"
                  size="sm"
                  variant={dirty ? "default" : "outline"}
                  className="shrink-0"
                  disabled={parsing || (!queryInput.trim() && !filters.q)}
                >
                  {parsing ? "Parsing…" : "Search"}
                </Button>
              </div>
            </form>
            <p className="kicker mt-2 text-foreground/60">
              {parsing
                ? "Asking the AI to interpret…"
                : rateLimited
                  ? "Rate limited — try again in 60s"
                  : networkError
                    ? networkError
                    : dirty
                      ? "Press Enter — AI extracts category, brand, color, price, features"
                      : "↵ Submits — AI parses to filters, then ranks"}
            </p>
          </div>
        </div>

        {/* Sentinel for the mobile sticky-bar IntersectionObserver. */}
        <div ref={heroSentinelRef} aria-hidden className="h-1 w-full" />
      </section>

      {/* -------- Results section -------- */}
      <section className="mx-auto max-w-[1600px] px-6 pb-24 lg:px-10">
        <div className="hairline-t flex items-center justify-between py-5 gap-4">
          <span className="kicker">
            02 / Results
            <span className="ml-3 text-foreground">{total.toLocaleString()}</span>
            <span className="ml-1 text-foreground/40">
              {total === 1 ? "item" : "items"}
            </span>
          </span>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setFilterSheetOpen(true)}
              className="md:hidden hairline rounded-full px-3 h-8 font-mono text-[11px] uppercase tracking-widest"
            >
              Filters
            </button>
            <SortControl value={currentSort} onChange={onSortChange} />
          </div>
        </div>

        {intent?.degraded && intent.degraded_reason && (
          <DegradedBanner reason={intent.degraded_reason} />
        )}
        {rateLimited && (
          <div className="anim-fade hairline mb-4 px-4 py-3 text-sm bg-bg-alt/40" style={{ borderLeft: "4px solid rgb(var(--warn))" }}>
            <span className="font-mono text-[11px] uppercase tracking-widest text-warn">
              Rate limited — retry in 60s
            </span>
          </div>
        )}

        <div className="grid grid-cols-1 gap-12 md:grid-cols-[200px_1fr] lg:grid-cols-[220px_1fr] lg:gap-16">
          <div className="hidden md:block">
            <FilterSidebar
              facets={facets.data}
              filters={filters}
              onChange={pushFilters}
            />
          </div>

          <main>
            <IntentChips
              parsed={intent?.parsed ?? null}
              filters={filters}
              fxDate={fxDate}
              onChange={pushFilters}
            />
            {intent?.parsed.ambiguity_hint && (
              <AmbiguityNudge
                hint={intent.parsed.ambiguity_hint}
                onAccept={acceptAmbiguity}
              />
            )}
            {sortHint && (
              <div className="mb-4">
                <span className="hairline inline-flex items-center gap-2 rounded-full px-3 py-1 font-mono text-[11px] uppercase tracking-widest text-muted">
                  Sort hint: {sortHint}
                  <button
                    type="button"
                    aria-label="Dismiss sort hint"
                    onClick={() => setSortHint(null)}
                    className="text-muted hover:text-foreground"
                  >
                    ×
                  </button>
                </span>
              </div>
            )}

            {search.isLoading ? (
              <SkeletonGrid />
            ) : items.length === 0 ? (
              <EmptyState
                filters={filters}
                onClear={clearSearch}
                onDrop={pushFilters}
              />
            ) : (
              <div className="grid grid-cols-2 gap-x-6 gap-y-10 sm:grid-cols-3 lg:grid-cols-4">
                {items.map((p, idx) => (
                  <div
                    key={p.id}
                    className="anim-rise"
                    style={{ animationDelay: `${Math.min(idx, 8) * 40}ms` }}
                  >
                    <ProductCard product={p} requestedFeatures={requestedFeatures} />
                  </div>
                ))}
              </div>
            )}

            {(hasNext || hasPrev) && (
              <div className="hairline-t mt-12 flex items-center justify-between pt-6">
                <span className="kicker">
                  {offset + 1}–{Math.min(offset + items.length, total)} / {total}
                </span>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={!hasPrev}
                    onClick={() =>
                      pushFilters({
                        ...filters,
                        offset: Math.max(0, offset - PAGE_SIZE),
                      })
                    }
                  >
                    ← Prev
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={!hasNext}
                    onClick={() =>
                      pushFilters({ ...filters, offset: offset + PAGE_SIZE })
                    }
                  >
                    Next →
                  </Button>
                </div>
              </div>
            )}
          </main>
        </div>
      </section>

      <MobileFilterSheet
        open={filterSheetOpen}
        onClose={() => setFilterSheetOpen(false)}
        facets={facets.data}
        filters={filters}
        onApply={pushFilters}
      />

      {/* -------- Footer -------- */}
      <footer className="hairline-t mx-auto max-w-[1600px] px-6 py-8 lg:px-10">
        <div className="flex flex-col items-start justify-between gap-2 text-sm text-muted sm:flex-row sm:items-center">
          <span className="font-mono uppercase tracking-widest">
            Clothist — vertical slice
          </span>
          <span className="font-mono uppercase tracking-widest">
            {intent && !intent.degraded
              ? `AI: ${intent.model} · ${intent.duration_ms}ms${fxDate ? ` · FX ${fxDate}` : ""}`
              : intent?.degraded
                ? `AI: offline — keyword fallback${fxDate ? ` · FX ${fxDate}` : ""}`
                : "Prototype · No purchases happen here"}
          </span>
        </div>
      </footer>
    </div>
  );
}
