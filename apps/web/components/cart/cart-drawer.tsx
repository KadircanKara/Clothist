"use client";

import Link from "next/link";
import Image from "next/image";
import { useEffect } from "react";
import { Button } from "@/components/ui/button";
import { cartTotals, useCart } from "@/lib/cart-store";

export function CartDrawer() {
  const lines = useCart((s) => s.lines);
  const isOpen = useCart((s) => s.isOpen);
  const close = useCart((s) => s.close);
  const setQty = useCart((s) => s.setQty);
  const remove = useCart((s) => s.remove);

  const { count, subtotalUsd } = cartTotals(lines);

  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    document.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [isOpen, close]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50" role="dialog" aria-modal="true" aria-label="Cart">
      <button
        type="button"
        aria-label="Close cart"
        onClick={close}
        className="absolute inset-0 bg-foreground/40"
        tabIndex={-1}
      />
      <aside className="anim-fade absolute right-0 top-0 flex h-full w-full max-w-[440px] flex-col bg-background hairline-l shadow-2xl">
        <header className="flex items-center justify-between px-6 py-5 hairline-b">
          <h2 className="font-medium text-lg">
            Your Bag{" "}
            <span className="font-mono text-sm text-muted">({count})</span>
          </h2>
          <button
            type="button"
            aria-label="Close cart"
            onClick={close}
            className="grid h-9 w-9 place-items-center rounded-full hairline text-muted hover:text-foreground hover:bg-bg-alt transition-colors"
          >
            ×
          </button>
        </header>

        {lines.length === 0 ? (
          <div className="flex grow flex-col items-center justify-center gap-3 px-8 text-center">
            <span className="font-serif italic text-2xl">Your bag is empty.</span>
            <p className="text-sm text-muted">Browse the catalog and add a piece.</p>
            <Button variant="default" size="sm" onClick={close} className="mt-2">
              Keep shopping
            </Button>
          </div>
        ) : (
          <ul className="grow space-y-5 overflow-y-auto px-6 py-5">
            {lines.map((l) => (
              <li key={l.key} className="flex gap-4">
                <div className="relative h-28 w-22 shrink-0 overflow-hidden bg-bg-alt hairline">
                  {l.image_url && (
                    <Image
                      src={l.image_url}
                      alt={l.title}
                      fill
                      sizes="88px"
                      className="object-cover"
                    />
                  )}
                </div>
                <div className="grow space-y-1">
                  <p className="font-mono text-[10px] uppercase tracking-widest text-muted">
                    {l.brand ?? "—"}
                  </p>
                  <p className="text-sm font-medium leading-snug line-clamp-2">
                    {l.title}
                  </p>
                  <p className="font-mono text-sm">
                    {l.price ? `${l.price} ${l.currency ?? ""}` : "—"}
                  </p>
                  <p className="font-mono text-[10px] uppercase tracking-widest text-muted">
                    {l.color && <>Color · {l.color}</>}
                    {l.color && l.size && <span className="mx-2">·</span>}
                    {l.size && <>Size · {l.size}</>}
                  </p>
                  <div className="flex items-center gap-3 pt-2">
                    <div className="inline-flex items-center hairline">
                      <button
                        type="button"
                        onClick={() => setQty(l.key, l.qty - 1)}
                        aria-label="Decrease quantity"
                        className="grid h-7 w-7 place-items-center text-muted hover:text-foreground"
                      >
                        −
                      </button>
                      <span className="font-mono text-xs px-2 min-w-[24px] text-center">
                        {String(l.qty).padStart(2, "0")}
                      </span>
                      <button
                        type="button"
                        onClick={() => setQty(l.key, l.qty + 1)}
                        aria-label="Increase quantity"
                        className="grid h-7 w-7 place-items-center text-muted hover:text-foreground"
                      >
                        +
                      </button>
                    </div>
                    <button
                      type="button"
                      onClick={() => remove(l.key)}
                      aria-label="Remove from bag"
                      className="ml-auto font-mono text-[10px] uppercase tracking-widest text-muted hover:text-warn"
                    >
                      Remove
                    </button>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}

        <footer className="border-t border-line/15 px-6 py-5 space-y-3">
          <div className="flex items-baseline justify-between">
            <div className="space-y-0.5">
              <p className="font-medium">Subtotal</p>
              <p className="text-xs text-muted">Tax & shipping at checkout.</p>
            </div>
            <p className="font-mono text-xl">${subtotalUsd.toFixed(2)}</p>
          </div>
          <Link
            href="/cart"
            onClick={close}
            className="block w-full bg-foreground text-background text-center py-3 font-mono text-[11px] uppercase tracking-widest hover:bg-foreground/90 transition-colors"
          >
            View cart
          </Link>
        </footer>
      </aside>
    </div>
  );
}
