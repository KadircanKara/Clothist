"use client";

import Image from "next/image";
import Link from "next/link";
import { CommerceHeader } from "@/components/commerce/commerce-header";
import { Button } from "@/components/ui/button";
import { cartTotals, useCart } from "@/lib/cart-store";

export default function CartPage() {
  const lines = useCart((s) => s.lines);
  const setQty = useCart((s) => s.setQty);
  const remove = useCart((s) => s.remove);
  const { count, subtotalUsd } = cartTotals(lines);

  return (
    <div className="relative z-10">
      <CommerceHeader />

      <main className="mx-auto max-w-[1280px] px-6 pb-24 pt-10 lg:px-10">
        <div className="flex items-baseline justify-between hairline-b pb-4">
          <h1 className="font-serif italic text-5xl">Your bag.</h1>
          <span className="kicker">{count} {count === 1 ? "item" : "items"}</span>
        </div>

        {lines.length === 0 ? (
          <div className="hairline flex flex-col items-center justify-center gap-4 px-6 py-24 text-center mt-10">
            <span className="font-serif italic text-3xl">Empty.</span>
            <p className="text-sm text-muted max-w-sm">
              Browse the catalog, add a piece you actually want, then come back here.
            </p>
            <Link
              href="/products"
              className="bg-foreground text-background px-6 py-3 font-mono text-[11px] uppercase tracking-widest hover:bg-foreground/90 transition-colors mt-2"
            >
              Browse products
            </Link>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-12 lg:grid-cols-[1fr_360px] lg:gap-16 mt-10">
            <ul className="space-y-6">
              {lines.map((l) => (
                <li key={l.key} className="flex gap-5 hairline-b pb-6">
                  <Link
                    href={`/product/${l.retailer_product_id}`}
                    className="relative h-40 w-32 shrink-0 overflow-hidden bg-bg-alt hairline"
                  >
                    {l.image_url && (
                      <Image
                        src={l.image_url}
                        alt={l.title}
                        fill
                        sizes="128px"
                        className="object-cover"
                      />
                    )}
                  </Link>
                  <div className="grow space-y-2">
                    <p className="font-mono text-[10px] uppercase tracking-widest text-muted">
                      {l.brand ?? "—"}
                    </p>
                    <Link href={`/product/${l.retailer_product_id}`}>
                      <p className="text-lg font-medium leading-snug link-reveal inline">
                        {l.title}
                      </p>
                    </Link>
                    <p className="font-mono text-sm">
                      {l.price ? `${l.price} ${l.currency ?? ""}` : "—"}
                      {l.price_usd && l.currency !== "USD" && (
                        <span className="mono-fx normal-case ml-2">
                          ≈ ${Number(l.price_usd).toFixed(2)} USD
                        </span>
                      )}
                    </p>
                    <p className="font-mono text-[10px] uppercase tracking-widest text-muted">
                      {l.color && <>Color · {l.color}</>}
                      {l.color && l.size && <span className="mx-2">·</span>}
                      {l.size && <>Size · {l.size}</>}
                    </p>
                    <div className="flex items-center gap-4 pt-2">
                      <div className="inline-flex items-center hairline">
                        <button
                          type="button"
                          onClick={() => setQty(l.key, l.qty - 1)}
                          aria-label="Decrease quantity"
                          className="grid h-8 w-8 place-items-center text-muted hover:text-foreground"
                        >
                          −
                        </button>
                        <span className="font-mono text-xs px-2 min-w-[28px] text-center">
                          {String(l.qty).padStart(2, "0")}
                        </span>
                        <button
                          type="button"
                          onClick={() => setQty(l.key, l.qty + 1)}
                          aria-label="Increase quantity"
                          className="grid h-8 w-8 place-items-center text-muted hover:text-foreground"
                        >
                          +
                        </button>
                      </div>
                      <button
                        type="button"
                        onClick={() => remove(l.key)}
                        className="font-mono text-[10px] uppercase tracking-widest text-muted hover:text-warn"
                      >
                        Remove
                      </button>
                    </div>
                  </div>
                </li>
              ))}
            </ul>

            <aside className="self-start sticky top-10 space-y-5 hairline p-6">
              <h2 className="kicker">Order summary</h2>
              <dl className="space-y-2 text-sm">
                <div className="flex items-baseline justify-between">
                  <dt className="text-muted">Items</dt>
                  <dd className="font-mono">{count}</dd>
                </div>
                <div className="flex items-baseline justify-between">
                  <dt className="text-muted">Subtotal (USD)</dt>
                  <dd className="font-mono">${subtotalUsd.toFixed(2)}</dd>
                </div>
                <div className="flex items-baseline justify-between text-xs text-muted">
                  <dt>Shipping</dt>
                  <dd>at checkout</dd>
                </div>
              </dl>
              <Button variant="default" size="lg" className="w-full" disabled>
                Checkout — coming soon
              </Button>
              <p className="text-[10px] text-muted text-center">
                Prototype build. No purchases happen here.
              </p>
            </aside>
          </div>
        )}
      </main>
    </div>
  );
}
