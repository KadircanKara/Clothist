"use client";

import { useQuery } from "@tanstack/react-query";
import Image from "next/image";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { CommerceHeader } from "@/components/commerce/commerce-header";
import { getProduct, searchProducts } from "@/lib/api";
import { useCart } from "@/lib/cart-store";
import type { Product, ProductVariant } from "@/lib/types";

const DEFAULT_SIZES = ["XS", "S", "M", "L", "XL", "XXL"];

type Props = { idOrSlug: string };

export function PdpView({ idOrSlug }: Props) {
  const product = useQuery({
    queryKey: ["product", idOrSlug],
    queryFn: () => getProduct(idOrSlug),
  });

  if (product.isLoading) return <Skeleton />;
  if (product.isError || !product.data) return <NotFound id={idOrSlug} />;

  return <PdpBody product={product.data} />;
}

function PdpBody({ product }: { product: Product }) {
  const variants = useMemo<ProductVariant[]>(() => {
    const v = product.attributes?.variants;
    if (v && v.length > 0) return v;
    return [
      {
        color: product.colors?.[0] ?? "default",
        image_url: product.image_url ?? "",
      },
    ];
  }, [product]);

  const [selectedColor, setSelectedColor] = useState(variants[0].color);
  const [selectedSize, setSelectedSize] = useState<string | null>(null);
  const [qty, setQty] = useState(1);
  const [adding, setAdding] = useState(false);
  const [justAdded, setJustAdded] = useState(false);

  const addLine = useCart((s) => s.addLine);
  const openCart = useCart((s) => s.open);

  useEffect(() => {
    setSelectedColor(variants[0].color);
  }, [variants]);

  const activeVariant =
    variants.find((v) => v.color === selectedColor) ?? variants[0];
  const sizes = product.sizes?.length ? product.sizes : DEFAULT_SIZES;
  const onSale =
    product.original_price &&
    product.price &&
    product.original_price !== product.price;
  const usdLabel =
    product.price_usd && product.currency && product.currency !== "USD"
      ? `≈ $${Number(product.price_usd).toFixed(2)} USD`
      : null;

  const handleAddToCart = async () => {
    setAdding(true);
    await new Promise((r) => setTimeout(r, 120));
    addLine(
      {
        product_id: product.id,
        retailer_product_id: product.retailer_product_id,
        title: product.title,
        brand: product.brand,
        image_url: activeVariant.image_url,
        price: product.price,
        price_usd: product.price_usd,
        currency: product.currency,
        color: selectedColor,
        size: selectedSize,
      },
      qty,
    );
    setAdding(false);
    setJustAdded(true);
    setTimeout(() => setJustAdded(false), 1800);
  };

  const handleBuyNow = () => {
    handleAddToCart();
    openCart();
  };

  return (
    <div className="commerce relative z-10 min-h-screen">
      <CommerceHeader />

      <main className="mx-auto max-w-[1480px] px-6 pb-32 pt-6 lg:px-12 lg:pt-10">
        <nav className="font-mono text-[10px] uppercase tracking-[0.18em] mb-8 flex items-center gap-2 text-muted">
          <Link href="/products" className="hover:text-foreground">Products</Link>
          {product.gender && (
            <>
              <span aria-hidden>/</span>
              <Link href={`/${product.gender}`} className="hover:text-foreground capitalize">
                {product.gender}
              </Link>
            </>
          )}
          {product.category && (
            <>
              <span aria-hidden>/</span>
              <span className="text-foreground capitalize">{product.category}</span>
            </>
          )}
        </nav>

        <div className="grid grid-cols-1 gap-10 lg:grid-cols-[minmax(0,1fr)_440px] lg:gap-20">
          <Gallery
            variants={variants}
            activeColor={selectedColor}
            onSelect={setSelectedColor}
            title={product.title}
          />

          <aside className="self-start lg:sticky lg:top-32 space-y-10">
            <header className="space-y-4">
              <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted">
                {product.brand ?? product.retailer}
              </p>
              <h1 className="font-display text-[44px] sm:text-[52px] lg:text-[60px] tracking-[-0.045em] leading-[0.92] text-foreground">
                {product.title}
              </h1>
              <div className="flex items-baseline gap-3 pt-1">
                <p className="font-display text-3xl tracking-tight">
                  {product.price}
                  <span className="text-base text-muted font-normal tracking-normal ml-2">
                    {product.currency}
                  </span>
                </p>
                {onSale && (
                  <p className="font-mono text-sm text-muted line-through">
                    {product.original_price} {product.currency}
                  </p>
                )}
              </div>
              {usdLabel && (
                <p className="mono-fx normal-case">{usdLabel} · fx snapshot</p>
              )}
            </header>

            <section aria-labelledby="color-heading" className="space-y-4">
              <div className="flex items-baseline justify-between">
                <p id="color-heading" className="font-mono text-[10px] uppercase tracking-[0.22em]">
                  Color
                </p>
                <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted capitalize">
                  {selectedColor}
                </p>
              </div>
              <ColorSwatches
                variants={variants}
                active={selectedColor}
                onSelect={setSelectedColor}
              />
            </section>

            <section aria-labelledby="size-heading" className="space-y-4">
              <div className="flex items-center justify-between">
                <p id="size-heading" className="font-mono text-[10px] uppercase tracking-[0.22em]">
                  Size
                </p>
                <button
                  type="button"
                  className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted hover:text-foreground"
                >
                  Size guide →
                </button>
              </div>
              <SizeGrid
                sizes={sizes}
                active={selectedSize}
                onSelect={setSelectedSize}
              />
            </section>

            <section aria-labelledby="qty-heading" className="space-y-4">
              <p id="qty-heading" className="font-mono text-[10px] uppercase tracking-[0.22em]">
                Quantity
              </p>
              <div className="inline-flex items-center border border-line/15">
                <button
                  type="button"
                  onClick={() => setQty((q) => Math.max(1, q - 1))}
                  aria-label="Decrease quantity"
                  className="grid h-12 w-12 place-items-center text-muted hover:text-foreground transition-colors"
                >
                  −
                </button>
                <span className="font-mono text-sm px-4 min-w-[48px] text-center">
                  {String(qty).padStart(2, "0")}
                </span>
                <button
                  type="button"
                  onClick={() => setQty((q) => Math.min(99, q + 1))}
                  aria-label="Increase quantity"
                  className="grid h-12 w-12 place-items-center text-muted hover:text-foreground transition-colors"
                >
                  +
                </button>
              </div>
            </section>

            <div className="space-y-3">
              <button
                type="button"
                onClick={handleAddToCart}
                disabled={adding}
                className="block w-full border border-foreground py-4 font-mono text-[11px] uppercase tracking-[0.18em] text-foreground hover:bg-foreground hover:text-background transition-colors disabled:opacity-50"
              >
                {adding ? "Adding…" : justAdded ? "Added ✓" : "Add to cart"}
              </button>
              <button
                type="button"
                onClick={handleBuyNow}
                className="block w-full bg-foreground py-4 font-mono text-[11px] uppercase tracking-[0.18em] text-background hover:bg-foreground/90 transition-colors"
              >
                Buy it now
              </button>
            </div>

            {product.description && (
              <p className="text-[15px] text-foreground/80 leading-relaxed border-t border-line/10 pt-6">
                {product.description}
              </p>
            )}

            <div>
              <Accordion title="Description">
                <DescriptionDetails product={product} />
              </Accordion>
              <Accordion title="Shipping & returns">
                <ul className="space-y-2 text-sm text-foreground/75">
                  <li>Free shipping on orders over $80 USD.</li>
                  <li>30-day returns. Original tags must be attached.</li>
                  <li>Demo build — no actual shipments are made.</li>
                </ul>
              </Accordion>
              <Accordion title="Provenance">
                <ul className="space-y-1.5 font-mono text-[11px] text-foreground/70">
                  <li>Listing source · {product.retailer}</li>
                  <li>Product ID · {product.retailer_product_id}</li>
                  {product.gender && <li>Tagged audience · {product.gender}</li>}
                  {product.attributes?.features && product.attributes.features.length > 0 && (
                    <li>Features · {product.attributes.features.join(", ")}</li>
                  )}
                </ul>
              </Accordion>
            </div>
          </aside>
        </div>

        <YouMayAlsoLike currentId={product.id} category={product.category} />
      </main>
    </div>
  );
}

function Gallery({
  variants,
  activeColor,
  onSelect,
  title,
}: {
  variants: ProductVariant[];
  activeColor: string;
  onSelect: (c: string) => void;
  title: string;
}) {
  const active = variants.find((v) => v.color === activeColor) ?? variants[0];

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-[96px_minmax(0,1fr)] sm:gap-5">
      <ul className="flex sm:flex-col gap-3 order-2 sm:order-1 overflow-x-auto sm:overflow-visible">
        {variants.map((v) => {
          const isActive = v.color === activeColor;
          return (
            <li key={v.color} className="shrink-0">
              <button
                type="button"
                onClick={() => onSelect(v.color)}
                aria-label={`Show ${v.color} variant`}
                aria-pressed={isActive}
                className={[
                  "relative block h-24 w-24 sm:h-28 sm:w-24 overflow-hidden bg-bg-alt transition-all",
                  isActive
                    ? "outline outline-2 outline-foreground outline-offset-2"
                    : "border border-line/15 hover:border-line/40",
                ].join(" ")}
              >
                {v.image_url && (
                  <Image
                    src={v.image_url}
                    alt={v.color}
                    fill
                    sizes="96px"
                    className="object-cover"
                  />
                )}
              </button>
            </li>
          );
        })}
      </ul>
      <div className="relative aspect-[4/5] w-full overflow-hidden bg-bg-alt order-1 sm:order-2">
        {active.image_url && (
          <Image
            key={active.image_url}
            src={active.image_url}
            alt={`${title} — ${activeColor} colorway`}
            fill
            priority
            sizes="(max-width: 1024px) 100vw, 60vw"
            className="anim-fade object-cover"
          />
        )}
      </div>
    </div>
  );
}

const COLOR_HEX: Record<string, string> = {
  black: "#0a0a09",
  white: "#fafafa",
  cream: "#f0e8d4",
  grey: "#a3a3a3",
  navy: "#1a2440",
  blue: "#3b5bdb",
  indigo: "#3b3672",
  green: "#3a8045",
  olive: "#6b6b32",
  rust: "#b54e21",
  orange: "#e7791f",
  red: "#c62833",
  pink: "#e9a4ad",
  brown: "#6b4a32",
  tan: "#cdab83",
  beige: "#e2d5b8",
  khaki: "#b8a276",
  stone: "#d6cfc0",
  "stone-wash": "#a8b4be",
  purple: "#7c5edb",
  yellow: "#e9c33d",
  burgundy: "#762a36",
};

function ColorSwatches({
  variants,
  active,
  onSelect,
}: {
  variants: ProductVariant[];
  active: string;
  onSelect: (c: string) => void;
}) {
  return (
    <ul className="flex flex-wrap items-center gap-3">
      {variants.map((v) => {
        const isActive = v.color === active;
        const bg = COLOR_HEX[v.color.toLowerCase()] ?? "#888";
        return (
          <li key={v.color}>
            <button
              type="button"
              onClick={() => onSelect(v.color)}
              aria-label={`Color: ${v.color}`}
              aria-pressed={isActive}
              className={[
                "relative grid h-10 w-10 place-items-center rounded-full transition-all",
                isActive
                  ? "outline outline-1 outline-foreground outline-offset-2"
                  : "hover:outline hover:outline-1 hover:outline-foreground/40 hover:outline-offset-2",
              ].join(" ")}
            >
              <span
                className="block h-8 w-8 rounded-full ring-1 ring-line/15"
                style={{ background: bg }}
              />
            </button>
          </li>
        );
      })}
    </ul>
  );
}

function SizeGrid({
  sizes,
  active,
  onSelect,
}: {
  sizes: string[];
  active: string | null;
  onSelect: (s: string) => void;
}) {
  return (
    <ul className="grid grid-cols-6 gap-2">
      {sizes.map((s) => {
        const isActive = active === s;
        return (
          <li key={s}>
            <button
              type="button"
              onClick={() => onSelect(s)}
              aria-pressed={isActive}
              className={[
                "w-full h-12 font-mono text-xs uppercase tracking-[0.14em] transition-colors",
                isActive
                  ? "bg-foreground text-background border border-foreground"
                  : "border border-line/15 text-foreground hover:border-foreground",
              ].join(" ")}
            >
              {s}
            </button>
          </li>
        );
      })}
    </ul>
  );
}

function Accordion({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border-t border-line/10 last:border-b">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex w-full items-center justify-between py-5 text-left font-medium hover:text-foreground transition-colors"
      >
        <span className="text-[15px]">{title}</span>
        <span aria-hidden className="font-mono text-muted text-lg leading-none">
          {open ? "−" : "+"}
        </span>
      </button>
      {open && <div className="anim-fade pb-5">{children}</div>}
    </div>
  );
}

function DescriptionDetails({ product }: { product: Product }) {
  return (
    <div className="space-y-3 text-[14px] text-foreground/80 leading-relaxed">
      <p>{product.description ?? "No description provided by the retailer."}</p>
      {product.colors && product.colors.length > 0 && (
        <p className="font-mono text-[11px]">
          <span className="text-muted uppercase tracking-[0.18em]">
            Listing color
          </span>{" "}
          {product.colors.join(", ")}
        </p>
      )}
    </div>
  );
}

function YouMayAlsoLike({
  currentId,
  category,
}: {
  currentId: string;
  category: string | null;
}) {
  const related = useQuery({
    queryKey: ["related", category],
    queryFn: () =>
      searchProducts({
        category: category ?? undefined,
        limit: 8,
        sort: "newest",
      }),
    enabled: !!category,
  });

  const items = (related.data?.items ?? []).filter((p) => p.id !== currentId).slice(0, 4);
  if (items.length === 0) return null;

  return (
    <section aria-labelledby="related-heading" className="mt-32">
      <div className="flex items-baseline justify-between border-b border-line/10 pb-4">
        <h2
          id="related-heading"
          className="font-display text-4xl sm:text-5xl tracking-[-0.05em]"
        >
          You may also like
        </h2>
        <Link
          href="/products"
          className="font-mono text-[11px] uppercase tracking-[0.18em] text-muted hover:text-foreground"
        >
          View all →
        </Link>
      </div>
      <ul className="mt-8 grid grid-cols-2 gap-x-6 gap-y-10 sm:grid-cols-4">
        {items.map((p) => {
          const v = p.attributes?.variants;
          const hero = v && v.length > 0 ? v[0].image_url : p.image_url;
          return (
            <li key={p.id}>
              <Link href={`/product/${p.retailer_product_id}`} className="group block">
                <div className="relative aspect-[4/5] w-full overflow-hidden bg-bg-alt">
                  {hero && (
                    <Image
                      src={hero}
                      alt={p.title}
                      fill
                      sizes="(max-width: 640px) 50vw, 25vw"
                      className="object-cover transition-transform duration-[700ms] ease-[cubic-bezier(0.16,1,0.3,1)] group-hover:scale-[1.04]"
                    />
                  )}
                </div>
                <div className="pt-3 space-y-1">
                  <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted">
                    {p.brand ?? p.retailer}
                  </p>
                  <p className="text-[15px] font-medium leading-snug line-clamp-2">
                    {p.title}
                  </p>
                  <p className="font-mono text-sm pt-1">
                    {p.price} <span className="text-muted">{p.currency}</span>
                  </p>
                </div>
              </Link>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function Skeleton() {
  return (
    <div className="commerce relative z-10 min-h-screen">
      <CommerceHeader />
      <main className="mx-auto max-w-[1480px] px-6 pb-24 pt-10 lg:px-12">
        <div className="grid grid-cols-1 gap-10 lg:grid-cols-[minmax(0,1fr)_440px] lg:gap-20">
          <div className="skeleton aspect-[4/5] w-full" />
          <div className="space-y-6">
            <div className="skeleton h-3 w-1/3" />
            <div className="skeleton h-14 w-2/3" />
            <div className="skeleton h-8 w-1/3" />
            <div className="skeleton h-14 w-full" />
            <div className="skeleton h-14 w-full" />
          </div>
        </div>
      </main>
    </div>
  );
}

function NotFound({ id }: { id: string }) {
  return (
    <div className="commerce relative z-10 min-h-screen">
      <CommerceHeader />
      <main className="mx-auto max-w-[1280px] px-6 py-32 lg:px-10 text-center space-y-6">
        <h1 className="font-display text-6xl tracking-[-0.05em]">Not found.</h1>
        <p className="text-sm text-muted">No product with id or slug “{id}”.</p>
        <Link
          href="/products"
          className="inline-block bg-foreground text-background px-6 py-3 font-mono text-[11px] uppercase tracking-[0.18em] hover:bg-foreground/90"
        >
          Browse products
        </Link>
      </main>
    </div>
  );
}
