"use client";

import Image from "next/image";
import Link from "next/link";
import { CommerceHeader } from "@/components/commerce/commerce-header";
import { cartTotals, useCart } from "@/lib/cart-store";

export default function CartPage() {
  const lines = useCart((s) => s.lines);
  const setQty = useCart((s) => s.setQty);
  const remove = useCart((s) => s.remove);
  const { count, subtotalUsd } = cartTotals(lines);

  return (
    <div className="commerce relative z-10 min-h-screen">
      <CommerceHeader />

      <section className="mx-auto max-w-[1480px] px-6 pt-10 pb-4 lg:px-12 lg:pt-16">
        <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted">
          02 / Cart · {count} {count === 1 ? "item" : "items"}
        </p>
        <h1 className="font-display-tight text-[18vw] sm:text-[14vw] lg:text-[11vw] leading-[0.86] tracking-[-0.06em] mt-4">
          Your bag.
        </h1>
      </section>

      <section className="mx-auto max-w-[1480px] px-6 pb-32 lg:px-12">
        {lines.length === 0 ? (
          <div className="border border-line/10 mt-10 flex flex-col items-center gap-4 py-24 text-center">
            <span className="font-display text-4xl tracking-[-0.05em]">Empty.</span>
            <p className="text-sm text-muted max-w-sm">
              Browse the catalog, add a piece you actually want, then come back here.
            </p>
            <Link
              href="/products"
              className="bg-foreground text-background px-6 py-3 font-mono text-[11px] uppercase tracking-[0.18em] hover:bg-foreground/90 transition-colors mt-2"
            >
              Browse products
            </Link>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-12 lg:grid-cols-[1fr_380px] lg:gap-20 border-t border-line/10 pt-10 mt-6">
            <ul className="space-y-8">
              {lines.map((l) => (
                <li key={l.key} className="flex gap-6 border-b border-line/10 pb-8">
                  <Link
                    href={`/product/${l.retailer_product_id}`}
                    className="relative h-48 w-36 shrink-0 overflow-hidden bg-bg-alt"
                  >
                    {l.image_url && (
                      <Image
                        src={l.image_url}
                        alt={l.title}
                        fill
                        sizes="144px"
                        className="object-cover"
                      />
                    )}
                  </Link>
                  <div className="grow space-y-2.5 min-w-0">
                    <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted">
                      {l.brand ?? "—"}
                    </p>
                    <Link href={`/product/${l.retailer_product_id}`}>
                      <p className="text-xl font-medium leading-snug">
                        {l.title}
                      </p>
                    </Link>
                    <p className="font-mono text-[13px]">
                      {l.price ? `${l.price} ${l.currency ?? ""}` : "—"}
                      {l.price_usd && l.currency !== "USD" && (
                        <span className="mono-fx normal-case ml-3">
                          ≈ ${Number(l.price_usd).toFixed(2)} USD
                        </span>
                      )}
                    </p>
                    <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted">
                      {l.color && <>{l.color}</>}
                      {l.color && l.size && <span className="mx-1.5">·</span>}
                      {l.size && <>Size {l.size}</>}
                    </p>
                    <div className="flex items-center gap-5 pt-3">
                      <div className="inline-flex items-center border border-line/15">
                        <button
                          type="button"
                          onClick={() => setQty(l.key, l.qty - 1)}
                          aria-label="Decrease quantity"
                          className="grid h-9 w-9 place-items-center text-muted hover:text-foreground"
                        >
                          −
                        </button>
                        <span className="font-mono text-[11px] px-2 min-w-[32px] text-center">
                          {String(l.qty).padStart(2, "0")}
                        </span>
                        <button
                          type="button"
                          onClick={() => setQty(l.key, l.qty + 1)}
                          aria-label="Increase quantity"
                          className="grid h-9 w-9 place-items-center text-muted hover:text-foreground"
                        >
                          +
                        </button>
                      </div>
                      <button
                        type="button"
                        onClick={() => remove(l.key)}
                        className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted hover:text-foreground underline underline-offset-4 decoration-line/20 hover:decoration-foreground"
                      >
                        Remove
                      </button>
                    </div>
                  </div>
                </li>
              ))}
            </ul>

            <aside className="self-start lg:sticky lg:top-32 space-y-6 border border-line/10 p-7">
              <h2 className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted">
                Order summary
              </h2>
              <dl className="space-y-3">
                <div className="flex items-baseline justify-between text-[14px]">
                  <dt className="text-muted">Items</dt>
                  <dd className="font-mono">{count}</dd>
                </div>
                <div className="flex items-baseline justify-between text-[14px]">
                  <dt className="text-muted">Subtotal (USD)</dt>
                  <dd className="font-mono">${subtotalUsd.toFixed(2)}</dd>
                </div>
                <div className="flex items-baseline justify-between text-[11px] text-muted font-mono uppercase tracking-[0.18em]">
                  <dt>Shipping</dt>
                  <dd>at checkout</dd>
                </div>
              </dl>
              <div className="border-t border-line/10 pt-5">
                <div className="flex items-baseline justify-between">
                  <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted">
                    Total
                  </span>
                  <span className="font-display text-3xl tracking-[-0.04em]">
                    ${subtotalUsd.toFixed(2)}
                  </span>
                </div>
              </div>
              <button
                type="button"
                disabled
                className="w-full bg-foreground/30 text-background py-4 font-mono text-[11px] uppercase tracking-[0.18em] cursor-not-allowed"
              >
                Checkout — coming soon
              </button>
              <p className="text-[10px] text-muted text-center font-mono uppercase tracking-[0.18em]">
                Prototype build · No purchases here
              </p>
            </aside>
          </div>
        )}
      </section>
    </div>
  );
}
