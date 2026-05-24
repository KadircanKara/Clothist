"use client";

import { useQuery } from "@tanstack/react-query";
import Image from "next/image";
import Link from "next/link";
import { useMemo, useState } from "react";

import { CommerceHeader } from "@/components/commerce/commerce-header";
import { getFacets, searchProducts } from "@/lib/api";
import type { Product, SortKey } from "@/lib/types";

type Props = {
  title: string;
  eyebrow: string;
  gender?: "men" | "women";
};

const SORT_LABELS: { value: SortKey; label: string }[] = [
  { value: "relevance", label: "Featured" },
  { value: "newest", label: "Newest" },
  { value: "price_asc", label: "Price ↑" },
  { value: "price_desc", label: "Price ↓" },
];

export function CatalogView({ title, eyebrow, gender }: Props) {
  const [category, setCategory] = useState<string | undefined>(undefined);
  const [sort, setSort] = useState<SortKey>("relevance");

  const facets = useQuery({ queryKey: ["facets"], queryFn: getFacets, staleTime: 60_000 });

  const params = useMemo(
    () => ({ gender, category, sort, limit: 48 }),
    [gender, category, sort],
  );
  const results = useQuery({
    queryKey: ["catalog", params],
    queryFn: () => searchProducts(params),
  });

  const items = results.data?.items ?? [];
  const total = results.data?.total ?? 0;

  return (
    <div className="relative z-10">
      <CommerceHeader />

      <section className="mx-auto max-w-[1600px] px-6 pb-6 pt-10 lg:px-10">
        <p className="kicker">{eyebrow}</p>
        <h1 className="font-serif italic text-6xl mt-3 lg:text-7xl">{title}</h1>
      </section>

      <section className="mx-auto max-w-[1600px] px-6 pb-24 lg:px-10">
        <div className="hairline-b flex flex-wrap items-center justify-between gap-4 py-4">
          <div className="flex items-center gap-2 overflow-x-auto">
            <button
              type="button"
              onClick={() => setCategory(undefined)}
              aria-pressed={!category}
              className={[
                "shrink-0 rounded-full px-3 h-8 font-mono text-[10px] uppercase tracking-widest transition-colors",
                !category
                  ? "bg-foreground text-background"
                  : "hairline text-muted hover:text-foreground",
              ].join(" ")}
            >
              All
            </button>
            {facets.data?.categories.map((c) => {
              const active = category === c.value;
              return (
                <button
                  key={c.value}
                  type="button"
                  onClick={() => setCategory(c.value)}
                  aria-pressed={active}
                  className={[
                    "shrink-0 rounded-full px-3 h-8 font-mono text-[10px] uppercase tracking-widest transition-colors",
                    active
                      ? "bg-foreground text-background"
                      : "hairline text-muted hover:text-foreground",
                  ].join(" ")}
                >
                  {c.value}{" "}
                  <span className={active ? "text-background/70" : "text-muted/70"}>
                    {c.count}
                  </span>
                </button>
              );
            })}
          </div>
          <div className="flex items-center gap-3">
            <span className="kicker">{total} {total === 1 ? "piece" : "pieces"}</span>
            <label className="inline-flex items-center gap-2">
              <span className="sr-only">Sort</span>
              <select
                value={sort}
                onChange={(e) => setSort(e.target.value as SortKey)}
                className="hairline rounded-full bg-transparent px-3 py-1 font-mono text-[11px] uppercase tracking-widest focus:outline-none focus:ring-1 focus:ring-foreground"
              >
                {SORT_LABELS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </div>

        {results.isLoading ? (
          <Skeleton />
        ) : items.length === 0 ? (
          <div className="hairline mt-10 flex flex-col items-center gap-3 py-20 text-center">
            <span className="font-serif italic text-3xl">No pieces matched.</span>
            <p className="text-sm text-muted">Try a different category.</p>
          </div>
        ) : (
          <ul className="mt-8 grid grid-cols-2 gap-x-6 gap-y-10 sm:grid-cols-3 lg:grid-cols-4">
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
        )}
      </section>
    </div>
  );
}

function CatalogCard({ product }: { product: Product }) {
  const v = product.attributes?.variants;
  const hero = v && v.length > 0 ? v[0].image_url : product.image_url;
  return (
    <Link href={`/product/${product.retailer_product_id}`} className="group block">
      <div className="relative aspect-[3/4] w-full overflow-hidden bg-bg-alt hairline">
        {hero && (
          <Image
            src={hero}
            alt={product.title}
            fill
            sizes="(max-width: 768px) 50vw, (max-width: 1280px) 33vw, 25vw"
            className="object-cover transition-transform duration-[700ms] ease-[cubic-bezier(0.16,1,0.3,1)] group-hover:scale-[1.04]"
          />
        )}
      </div>
      <div className="pt-3 space-y-1">
        <p className="font-mono text-[10px] uppercase tracking-widest text-muted truncate">
          {product.brand ?? product.retailer}
        </p>
        <h3 className="line-clamp-2 text-[15px] font-medium leading-snug">
          <span className="link-reveal">{product.title}</span>
        </h3>
        <p className="font-mono text-sm pt-1">
          {product.price} <span className="text-muted">{product.currency}</span>
        </p>
        {v && v.length > 1 && (
          <p className="font-mono text-[10px] uppercase tracking-widest text-muted">
            +{v.length - 1} {v.length - 1 === 1 ? "color" : "colors"}
          </p>
        )}
      </div>
    </Link>
  );
}

function Skeleton() {
  return (
    <ul className="mt-8 grid grid-cols-2 gap-x-6 gap-y-10 sm:grid-cols-3 lg:grid-cols-4">
      {Array.from({ length: 8 }).map((_, i) => (
        <li key={i} aria-hidden>
          <div className="skeleton aspect-[3/4] w-full hairline" />
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
