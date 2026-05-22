"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { FilterSidebar } from "./filter-sidebar";
import { HeroBackdrop } from "./hero-backdrop";
import { IntentChips } from "./intent-chips";
import { ProductCard } from "./product-card";
import { Wordmark } from "./wordmark";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import { ApiError, getFacets, parseIntent, searchProducts } from "@/lib/api";
import type { IntentResponse, SearchParams } from "@/lib/types";

const PAGE_SIZE = 24;

function paramsFromUrl(sp: URLSearchParams): SearchParams {
  const num = (k: string) => {
    const v = sp.get(k);
    return v ? Number(v) : undefined;
  };
  return {
    q: sp.get("q") ?? undefined,
    category: sp.get("category") ?? undefined,
    brand: sp.get("brand") ?? undefined,
    color: sp.get("color") ?? undefined,
    min_price: num("min_price"),
    max_price: num("max_price"),
    in_stock_only: sp.get("in_stock_only") === "true" || undefined,
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
  const [parseError, setParseError] = useState<string | null>(null);

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
    pushFilters({
      ...filters,
      q: rawQ || undefined,
      // Keep prior structured filters; sidebar-set values shouldn't blow away.
      offset: 0,
    });
  };

  const submitSearch = async (e?: React.FormEvent) => {
    e?.preventDefault();
    const trimmed = queryInput.trim();

    if (!trimmed) {
      setIntent(null);
      submitPlainSearch("");
      return;
    }

    setParsing(true);
    setParseError(null);

    try {
      const res = await parseIntent(trimmed);
      setIntent(res);
      const p = res.parsed;
      pushFilters({
        ...filters,
        // AI-extracted structured fields REPLACE any previous values — a new
        // search is a fresh intent. Sidebar tweaks happen after, on top.
        category: p.category ?? undefined,
        brand: p.brand ?? undefined,
        color: p.color ? p.color.toLowerCase() : undefined,
        min_price: p.min_price ?? undefined,
        max_price: p.max_price ?? undefined,
        in_stock_only: p.in_stock_only || undefined,
        q: p.refined_query?.trim() || undefined,
        offset: 0,
      });
    } catch (err) {
      // 503 = LLM disabled (no API key). 502 = upstream error. Both: fall back
      // to plain keyword search so the box still works.
      if (err instanceof ApiError && (err.status === 503 || err.status === 502)) {
        setParseError(
          err.status === 503
            ? "AI parsing is disabled — set XAI_API_KEY to enable."
            : "AI parser had an issue. Using plain keyword search.",
        );
      } else {
        setParseError("Couldn't reach the AI parser. Using plain keyword search.");
      }
      setIntent(null);
      submitPlainSearch(trimmed);
    } finally {
      setParsing(false);
    }
  };

  const clearSearch = () => {
    setQueryInput("");
    setIntent(null);
    setParseError(null);
    pushFilters({ ...filters, q: undefined, offset: 0 });
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

  return (
    <div className="relative z-10">
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
      <section className="relative mx-auto max-w-[1600px] overflow-hidden px-6 pb-14 pt-10 lg:px-10">
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
              Type the piece you're picturing. Cargo pants with six pockets, a
              minimalist hoodie with a hidden zip, a waterproof shell that
              actually lasts. We search across the retailers — you skip the
              tabs.
            </p>
          </div>

          <div className="lg:col-span-4 anim-rise delay-700">
            <label htmlFor="clothist-search" className="kicker block">
              Search
            </label>
            <form onSubmit={submitSearch} role="search">
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
                ? "Asking Grok to interpret…"
                : parseError
                  ? parseError
                  : dirty
                    ? "Press Enter — AI extracts category, brand, color, price"
                    : "↵ Submits — AI parses to filters, then ranks by FTS"}
            </p>
          </div>
        </div>
      </section>

      {/* -------- Results section -------- */}
      <section className="mx-auto max-w-[1600px] px-6 pb-24 lg:px-10">
        <div className="hairline-t flex items-baseline justify-between py-5">
          <span className="kicker">
            02 / Results
            <span className="ml-3 text-foreground">{total.toLocaleString()}</span>
            <span className="ml-1 text-foreground/40">
              {total === 1 ? "item" : "items"}
            </span>
          </span>
          {search.isError && (
            <span className="font-mono text-[10px] uppercase tracking-widest text-accent">
              {(search.error as Error).message}
            </span>
          )}
        </div>

        <div className="grid grid-cols-1 gap-12 md:grid-cols-[200px_1fr] lg:grid-cols-[220px_1fr] lg:gap-16">
          <FilterSidebar
            facets={facets.data}
            filters={filters}
            onChange={pushFilters}
          />

          <main>
            <IntentChips
              parsed={intent?.parsed ?? null}
              filters={filters}
              onChange={pushFilters}
            />

            {items.length === 0 && !search.isLoading ? (
              <div className="hairline flex flex-col items-center justify-center gap-3 px-6 py-20 text-center">
                <span className="font-serif text-4xl">Nothing matched.</span>
                <p className="max-w-sm text-base text-muted">
                  Loosen a filter, or run the H&M scraper to pull in more
                  inventory.
                </p>
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-x-6 gap-y-10 sm:grid-cols-3 lg:grid-cols-4">
                {items.map((p, idx) => (
                  <div
                    key={p.id}
                    className="anim-rise"
                    style={{ animationDelay: `${Math.min(idx, 8) * 40}ms` }}
                  >
                    <ProductCard product={p} />
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

      {/* -------- Footer -------- */}
      <footer className="hairline-t mx-auto max-w-[1600px] px-6 py-8 lg:px-10">
        <div className="flex flex-col items-start justify-between gap-2 text-sm text-muted sm:flex-row sm:items-center">
          <span className="font-mono uppercase tracking-widest">
            Clothist — vertical slice
          </span>
          <span className="font-mono uppercase tracking-widest">
            {intent && `AI: ${intent.model} · ${intent.duration_ms}ms`}
            {!intent && "Prototype · No purchases happen here"}
          </span>
        </div>
      </footer>
    </div>
  );
}
