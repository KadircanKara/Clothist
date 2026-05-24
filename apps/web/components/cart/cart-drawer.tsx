"use client";

import Link from "next/link";
import Image from "next/image";
import { useEffect } from "react";
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
        className="absolute inset-0 bg-black/30 backdrop-blur-[2px] anim-fade"
        tabIndex={-1}
      />
      <aside className="commerce anim-rise absolute right-0 top-0 flex h-full w-full max-w-[460px] flex-col shadow-2xl">
        <header className="flex items-center justify-between px-6 py-5 border-b border-line/10">
          <h2 className="font-display text-2xl tracking-[-0.04em]">
            Your Bag <span className="font-mono text-xs text-muted align-middle ml-1">({count})</span>
          </h2>
          <button
            type="button"
            aria-label="Close cart"
            onClick={close}
            className="grid h-9 w-9 place-items-center rounded-full border border-line/15 text-muted hover:border-foreground hover:text-foreground transition-colors"
          >
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              aria-hidden
            >
              <path d="M6 6l12 12M6 18L18 6" />
            </svg>
          </button>
        </header>

        {lines.length === 0 ? (
          <div className="flex grow flex-col items-center justify-center gap-4 px-8 text-center">
            <span className="font-display text-3xl tracking-[-0.04em]">Empty.</span>
            <p className="text-sm text-muted">Browse the catalog and add a piece.</p>
            <button
              type="button"
              onClick={close}
              className="mt-2 bg-foreground text-background px-5 py-3 font-mono text-[11px] uppercase tracking-[0.18em] hover:bg-foreground/90 transition-colors"
            >
              Keep shopping
            </button>
          </div>
        ) : (
          <ul className="grow space-y-6 overflow-y-auto px-6 py-6">
            {lines.map((l) => (
              <li key={l.key} className="flex gap-4 border-b border-line/10 pb-6 last:border-b-0">
                <div className="relative h-32 w-24 shrink-0 overflow-hidden bg-bg-alt">
                  {l.image_url && (
                    <Image
                      src={l.image_url}
                      alt={l.title}
                      fill
                      sizes="96px"
                      className="object-cover"
                    />
                  )}
                </div>
                <div className="grow space-y-1.5 min-w-0">
                  <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted">
                    {l.brand ?? "—"}
                  </p>
                  <p className="text-[14px] font-medium leading-snug line-clamp-2">
                    {l.title}
                  </p>
                  <p className="font-mono text-[13px]">
                    {l.price ? `${l.price} ${l.currency ?? ""}` : "—"}
                  </p>
                  <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted">
                    {l.color && <>{l.color}</>}
                    {l.color && l.size && <span className="mx-1.5">·</span>}
                    {l.size && <>Size {l.size}</>}
                  </p>
                  <div className="flex items-center gap-3 pt-2">
                    <div className="inline-flex items-center border border-line/15">
                      <button
                        type="button"
                        onClick={() => setQty(l.key, l.qty - 1)}
                        aria-label="Decrease quantity"
                        className="grid h-8 w-8 place-items-center text-muted hover:text-foreground"
                      >
                        −
                      </button>
                      <span className="font-mono text-[11px] px-2 min-w-[28px] text-center">
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
                      aria-label="Remove from bag"
                      className="ml-auto font-mono text-[10px] uppercase tracking-[0.22em] text-muted hover:text-foreground underline underline-offset-4 decoration-line/20 hover:decoration-foreground"
                    >
                      Remove
                    </button>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}

        {lines.length > 0 && (
          <footer className="border-t border-line/10 px-6 py-5 space-y-4 bg-background">
            <div className="flex items-baseline justify-between">
              <div className="space-y-0.5">
                <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted">
                  Subtotal
                </p>
                <p className="text-[11px] text-muted">Tax & shipping at checkout.</p>
              </div>
              <p className="font-display text-2xl tracking-[-0.04em]">
                ${subtotalUsd.toFixed(2)}
              </p>
            </div>
            <Link
              href="/cart"
              onClick={close}
              className="block w-full bg-foreground text-background text-center py-4 font-mono text-[11px] uppercase tracking-[0.18em] hover:bg-foreground/90 transition-colors"
            >
              View cart
            </Link>
          </footer>
        )}
      </aside>
    </div>
  );
}
