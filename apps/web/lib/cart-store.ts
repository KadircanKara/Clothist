"use client";

import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";

export type CartLine = {
  /** Unique line key: `${product_id}::${color}::${size}` so the same SKU in two sizes is two lines. */
  key: string;
  product_id: string;
  retailer_product_id: string;
  title: string;
  brand: string | null;
  image_url: string | null;
  /** Native price string from the product, kept as-is for display. */
  price: string | null;
  /** Canonical USD price (string from Postgres NUMERIC), used for totals. */
  price_usd: string | null;
  currency: string | null;
  color: string | null;
  size: string | null;
  qty: number;
};

type CartState = {
  lines: CartLine[];
  isOpen: boolean;
  addLine: (line: Omit<CartLine, "key" | "qty">, qty?: number) => void;
  setQty: (key: string, qty: number) => void;
  remove: (key: string) => void;
  clear: () => void;
  open: () => void;
  close: () => void;
  toggle: () => void;
};

const lineKey = (l: Pick<CartLine, "product_id" | "color" | "size">) =>
  `${l.product_id}::${l.color ?? ""}::${l.size ?? ""}`;

export const useCart = create<CartState>()(
  persist(
    (set) => ({
      lines: [],
      isOpen: false,
      addLine: (line, qty = 1) =>
        set((s) => {
          const key = lineKey(line);
          const existing = s.lines.find((l) => l.key === key);
          if (existing) {
            return {
              lines: s.lines.map((l) =>
                l.key === key ? { ...l, qty: l.qty + qty } : l,
              ),
              isOpen: true,
            };
          }
          return {
            lines: [...s.lines, { ...line, key, qty }],
            isOpen: true,
          };
        }),
      setQty: (key, qty) =>
        set((s) => ({
          lines:
            qty <= 0
              ? s.lines.filter((l) => l.key !== key)
              : s.lines.map((l) => (l.key === key ? { ...l, qty } : l)),
        })),
      remove: (key) =>
        set((s) => ({ lines: s.lines.filter((l) => l.key !== key) })),
      clear: () => set({ lines: [] }),
      open: () => set({ isOpen: true }),
      close: () => set({ isOpen: false }),
      toggle: () => set((s) => ({ isOpen: !s.isOpen })),
    }),
    {
      name: "clothist:cart",
      storage: createJSONStorage(() => localStorage),
      partialize: (s) => ({ lines: s.lines }),
    },
  ),
);

export function cartTotals(lines: CartLine[]): {
  count: number;
  subtotalUsd: number;
} {
  let count = 0;
  let subtotalUsd = 0;
  for (const l of lines) {
    count += l.qty;
    const usd = l.price_usd ? Number(l.price_usd) : 0;
    subtotalUsd += usd * l.qty;
  }
  return { count, subtotalUsd };
}
