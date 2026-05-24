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
import { ApiError, getFacets, parseIntent, searchProducts } from "@/lib/api";
import type { IntentResponse, SearchParams, SortKey } from "@/lib/types";

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
  const [sortHint, setSortHint] = useState<string | null>(null);

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

  const acceptAmbiguity = (alternative: string) => {
    const original = intent?.raw_query ?? queryInput;
    const hintToken = intent?.parsed.ambiguity_hint?.token;
    if (!hintToken) return;
    const rewritten = original.replace(hintToken, hintToken.replace(/[\d.,]+/, alternative));
    setQueryInput(rewritten);
    void submitSearch(undefined, rewritten);
  };

  // Translate URL-based SearchParams to the catalog-sidebar's filter shape.
  const sidebarFilters: CatalogFilters = useMemo(
    () => ({
      category: filters.category,
      color: filters.color,
      features: filters.features ?? [],
      inStockOnly: !!filters.in_stock_only,
    }),
    [filters],
  );

  const onSidebarChange = (next: CatalogFilters) => {
    pushFilters({
      ...filters,
      category: next.category,
      color: next.color,
      features: next.features.length ? next.features : undefined,
      in_stock_only: next.inStockOnly || undefined,
      offset: 0,
    });
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
    <div className="commerce relative z-10 min-h-screen">
      <CommerceHeader />

      {/* ---------- AI search hero ---------- */}
      <section className="mx-auto max-w-[1600px] px-6 pt-10 lg:px-12 lg:pt-16">
        <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted">
          01 / Discovery · AI search
        </p>
        <h1 className="font-display-tight text-[40px] sm:text-[64px] lg:text-[88px] leading-[0.92] tracking-[-0.04em] mt-3 max-w-[14ch]">
          Type the piece.
        </h1>

        <form
          onSubmit={(e) => void submitSearch(e)}
          role="search"
          className="mt-8 max-w-[820px]"
        >
          <div className="flex items-center gap-3 border-b border-line/40 py-2 focus-within:border-foreground transition-colors">
            <span className="font-mono text-sm text-muted">/</span>
            <input
              id="clothist-search"
              type="text"
              value={queryInput}
              onChange={(e) => setQueryInput(e.target.value)}
              placeholder="black cargo pants under $100"
              autoFocus
              enterKeyHint="search"
              className="flex-1 bg-transparent border-0 outline-none h-12 text-lg placeholder:text-muted/70"
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
            <button
              type="submit"
              disabled={parsing || (!queryInput.trim() && !filters.q)}
              className={[
                "shrink-0 px-5 py-3 font-mono text-[11px] uppercase tracking-[0.18em] transition-colors",
                dirty
                  ? "bg-foreground text-background hover:bg-foreground/90"
                  : "border border-line/20 text-foreground hover:bg-foreground hover:text-background",
                "disabled:opacity-40 disabled:pointer-events-none",
              ].join(" ")}
            >
              {parsing ? "Parsing…" : "Search"}
            </button>
          </div>
          <p className="font-mono text-[11px] uppercase tracking-[0.18em] mt-3 text-muted">
            {parsing
              ? "Asking the AI to interpret…"
              : rateLimited
                ? "Rate limited — try again in 60s"
                : networkError
                  ? networkError
                  : dirty
                    ? "Press Enter — AI extracts category, brand, color, price, features"
                    : "↵ submits — AI parses to filters, then ranks across the catalog"}
          </p>
        </form>

        {!filters.q && !intent && (
          <div className="mt-8 max-w-[820px]">
            <ExampleQueries onPick={pickExample} fxDate={fxDate} />
          </div>
        )}
      </section>

      {/* ---------- Results ---------- */}
      <section className="mx-auto max-w-[1600px] px-6 pb-32 pt-12 lg:px-12">
        {intent?.degraded && intent.degraded_reason && (
          <DegradedBanner reason={intent.degraded_reason} />
        )}
        {rateLimited && (
          <div
            className="anim-fade mb-4 px-4 py-3 text-sm bg-bg-alt/40 border-l-[3px] border-warn"
          >
            <span className="font-mono text-[11px] uppercase tracking-[0.18em] text-warn">
              Rate limited — retry in 60s
            </span>
          </div>
        )}

        <div className="grid grid-cols-1 gap-10 lg:grid-cols-[220px_minmax(0,1fr)] lg:gap-14">
          <div className="hidden lg:block">
            <CatalogSidebar
              facets={facets.data}
              filters={sidebarFilters}
              onChange={onSidebarChange}
              totalCount={total}
            />
          </div>

          <div>
            <div className="border-t border-line/10 flex flex-wrap items-center justify-between gap-4 py-4">
              <span className="font-mono text-[11px] uppercase tracking-[0.18em] text-muted">
                02 / Results · {total} {total === 1 ? "piece" : "pieces"}
              </span>
              <label className="inline-flex items-center gap-2">
                <span className="sr-only">Sort</span>
                <select
                  value={currentSort}
                  onChange={(e) =>
                    pushFilters({ ...filters, sort: e.target.value as SortKey, offset: 0 })
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
              <div className="border border-line/10 mt-2 flex flex-col items-center gap-3 py-24 text-center">
                <span className="font-display text-4xl tracking-[-0.04em]">
                  Nothing matched.
                </span>
                <p className="text-sm text-muted">
                  Drop a filter or refine your query.
                </p>
                <button
                  type="button"
                  onClick={clearSearch}
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
                    className="border border-line/15 px-3 py-2 font-mono text-[11px] uppercase tracking-[0.18em] hover:border-foreground transition-colors disabled:opacity-30 disabled:pointer-events-none"
                  >
                    ← Prev
                  </button>
                  <button
                    type="button"
                    disabled={!hasNext}
                    onClick={() =>
                      pushFilters({ ...filters, offset: offset + PAGE_SIZE })
                    }
                    className="border border-line/15 px-3 py-2 font-mono text-[11px] uppercase tracking-[0.18em] hover:border-foreground transition-colors disabled:opacity-30 disabled:pointer-events-none"
                  >
                    Next →
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </section>

      {/* ---------- Footer ---------- */}
      <footer className="border-t border-line/10 mx-auto max-w-[1600px] px-6 py-8 lg:px-12">
        <div className="flex flex-col items-start justify-between gap-2 text-sm text-muted sm:flex-row sm:items-center">
          <span className="font-mono uppercase tracking-[0.18em] text-[11px]">
            Clothist — prototype build
          </span>
          <span className="font-mono uppercase tracking-[0.18em] text-[11px]">
            {intent && !intent.degraded
              ? `AI: ${intent.model} · ${intent.duration_ms}ms${fxDate ? ` · FX ${fxDate}` : ""}`
              : intent?.degraded
                ? `AI: offline — keyword fallback${fxDate ? ` · FX ${fxDate}` : ""}`
                : `No purchases here${fxDate ? ` · FX ${fxDate}` : ""}`}
          </span>
        </div>
      </footer>
    </div>
  );
}
