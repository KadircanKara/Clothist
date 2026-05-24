"use client";

import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import Image from "next/image";
import Link from "next/link";
import { useMemo, useState } from "react";

import { CatalogSidebar, type CatalogFilters } from "@/components/commerce/catalog-sidebar";
import { CommerceHeader } from "@/components/commerce/commerce-header";
import { getFacets, searchProducts } from "@/lib/api";
import type { Product, SortKey } from "@/lib/types";

const PAGE_SIZE = 48;

type Props = {
  title: string;
  eyebrow: string;
  // Omit to show ALL products regardless of gender (the /products tab).
  gender?: "men" | "women" | "unisex";
};

const SORT_LABELS: { value: SortKey; label: string }[] = [
  { value: "relevance", label: "Featured" },
  { value: "newest", label: "Newest" },
  { value: "price_asc", label: "Price ↑" },
  { value: "price_desc", label: "Price ↓" },
];

export function CatalogView({ title, eyebrow, gender }: Props) {
  const [filters, setFilters] = useState<CatalogFilters>({
    categories: [],
    color: undefined,
    features: [],
    inStockOnly: false,
  });
  const [sort, setSort] = useState<SortKey>("relevance");

  // Refetch facets when the page's gender changes — /men, /women, /unisex,
  // and /products each get their own filter chip counts so an empty
  // section never advertises a non-zero number.
  const facets = useQuery({
    queryKey: ["facets", gender ?? null],
    queryFn: () => getFacets(gender),
    staleTime: 60_000,
  });

  // Unfiltered total for the "All" chip in the sidebar. Sum the facet
  // category counts (already gender-scoped, "excluded" already dropped).
  const allCount = useMemo(
    () => (facets.data?.categories ?? []).reduce((sum, c) => sum + c.count, 0),
    [facets.data],
  );

  const baseParams = useMemo(
    () => ({
      // gender omitted on the /products tab → backend doesn't filter
      ...(gender ? { gender } : {}),
      // Multi-select: pass the array; the API accepts repeated
      // ?category= keys via FastAPI's Query(default_factory=list).
      ...(filters.categories.length ? { category: filters.categories } : {}),
      color: filters.color,
      features: filters.features.length ? filters.features : undefined,
      in_stock_only: filters.inStockOnly || undefined,
      sort,
    }),
    [gender, filters, sort],
  );

  // Infinite pagination so categories with >48 products are fully
  // browsable. Each page fetches PAGE_SIZE; load-more appends the next.
  const results = useInfiniteQuery({
    queryKey: ["catalog", baseParams],
    queryFn: ({ pageParam = 0 }) =>
      searchProducts({ ...baseParams, limit: PAGE_SIZE, offset: pageParam }),
    initialPageParam: 0,
    getNextPageParam: (lastPage, allPages) => {
      const loaded = allPages.reduce((n, p) => n + p.items.length, 0);
      return loaded < lastPage.total ? loaded : undefined;
    },
  });

  const items = useMemo(
    () => results.data?.pages.flatMap((p) => p.items) ?? [],
    [results.data],
  );
  const total = results.data?.pages[0]?.total ?? 0;

  return (
    <div className="commerce relative z-10 min-h-screen">
      <CommerceHeader />

      <section className="mx-auto max-w-[1600px] px-6 pt-10 lg:px-12 lg:pt-14">
        <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted">
          {eyebrow}
        </p>
        <h1 className="font-display-tight text-[64px] sm:text-[88px] lg:text-[112px] leading-[0.92] tracking-[-0.04em] mt-3">
          {title}
        </h1>
      </section>

      <section className="mx-auto max-w-[1600px] px-6 pb-32 pt-8 lg:px-12">
        <div className="grid grid-cols-1 gap-10 lg:grid-cols-[220px_minmax(0,1fr)] lg:gap-14">
          <div className="hidden lg:block">
            <CatalogSidebar
              facets={facets.data}
              filters={filters}
              onChange={setFilters}
              allCount={allCount}
            />
          </div>

          <div>
            <div className="border-t border-line/10 flex flex-wrap items-center justify-between gap-4 py-4">
              <span className="font-mono text-[11px] uppercase tracking-[0.18em] text-muted">
                {total} {total === 1 ? "piece" : "pieces"}
              </span>
              <label className="inline-flex items-center gap-2">
                <span className="sr-only">Sort</span>
                <select
                  value={sort}
                  onChange={(e) => setSort(e.target.value as SortKey)}
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

            {results.isLoading ? (
              <Skeleton />
            ) : items.length === 0 ? (
              <div className="border border-line/10 mt-2 flex flex-col items-center gap-3 py-24 text-center">
                <span className="font-display text-4xl tracking-[-0.04em]">
                  No pieces matched.
                </span>
                <p className="text-sm text-muted">
                  Drop a filter or browse another category.
                </p>
              </div>
            ) : (
              <>
                <ul className="mt-6 grid grid-cols-2 gap-x-6 gap-y-12 sm:grid-cols-2 lg:grid-cols-3">
                  {items.map((p, i) => (
                    <li
                      key={p.id}
                      className="anim-rise"
                      style={{ animationDelay: `${Math.min(i, 8) * 40}ms` }}
                    >
                      <CatalogCard product={p} />
                    </li>
                  ))}
                </ul>
                {results.hasNextPage && (
                  <div className="mt-16 flex flex-col items-center gap-3">
                    <button
                      type="button"
                      onClick={() => results.fetchNextPage()}
                      disabled={results.isFetchingNextPage}
                      className="border border-foreground px-8 py-3 font-mono text-[11px] uppercase tracking-[0.22em] hover:bg-foreground hover:text-background transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {results.isFetchingNextPage ? "Loading…" : "Load more"}
                    </button>
                    <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted">
                      Showing {items.length} of {total}
                    </p>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}

function CatalogCard({ product }: { product: Product }) {
  const v = product.attributes?.variants;
  const hero = v && v.length > 0 ? v[0].image_url : product.image_url;
  const onSale =
    product.original_price &&
    product.price &&
    product.original_price !== product.price;

  return (
    <Link href={`/product/${product.retailer_product_id}`} className="group block">
      <div className="relative aspect-[4/5] w-full overflow-hidden bg-bg-alt">
        {hero ? (
          <Image
            src={hero}
            alt={product.title}
            fill
            sizes="(max-width: 768px) 50vw, (max-width: 1280px) 33vw, 25vw"
            className="object-cover transition-transform duration-[900ms] ease-[cubic-bezier(0.16,1,0.3,1)] group-hover:scale-[1.05]"
          />
        ) : (
          <div className="grid h-full place-items-center font-mono text-[10px] uppercase tracking-[0.22em] text-muted">
            No image
          </div>
        )}
        {!product.in_stock && (
          <span className="absolute top-3 left-3 bg-background/95 px-2 py-1 font-mono text-[9px] uppercase tracking-[0.18em] text-foreground">
            Out of stock
          </span>
        )}
        {onSale && (
          <span className="absolute top-3 right-3 bg-foreground text-background px-2 py-1 font-mono text-[9px] uppercase tracking-[0.18em]">
            Sale
          </span>
        )}
      </div>
      <div className="pt-4 space-y-1.5">
        <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted truncate">
          {product.brand ?? product.retailer}
        </p>
        <h3 className="line-clamp-2 text-[15px] font-medium leading-snug">
          <span className="underline-offset-4 decoration-1 group-hover:underline">
            {product.title}
          </span>
        </h3>
        <p className="font-mono text-[13px] pt-1">
          {product.price} <span className="text-muted">{product.currency}</span>
        </p>
        {v && v.length > 1 && (
          <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted">
            +{v.length - 1} {v.length - 1 === 1 ? "color" : "colors"}
          </p>
        )}
      </div>
    </Link>
  );
}

function Skeleton() {
  return (
    <ul className="mt-6 grid grid-cols-2 gap-x-6 gap-y-12 sm:grid-cols-2 lg:grid-cols-3">
      {Array.from({ length: 6 }).map((_, i) => (
        <li key={i} aria-hidden>
          <div className="skeleton aspect-[4/5] w-full" />
          <div className="mt-3 space-y-2">
            <div className="skeleton h-3 w-1/3" />
            <div className="skeleton h-4 w-2/3" />
            <div className="skeleton h-4 w-1/4" />
          </div>
        </li>
      ))}
    </ul>
  );
}
