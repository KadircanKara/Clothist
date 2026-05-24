"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import { cartTotals, useCart } from "@/lib/cart-store";

const NAV = [
  { href: "/products", label: "Products" },
  { href: "/men", label: "Men" },
  { href: "/women", label: "Women" },
];

export function CommerceHeader() {
  const pathname = usePathname();
  const lines = useCart((s) => s.lines);
  const open = useCart((s) => s.open);
  const { count } = cartTotals(lines);

  return (
    <header className="hairline-b bg-background/95 backdrop-blur sticky top-0 z-40">
      <div className="mx-auto max-w-[1600px] flex items-center justify-between gap-6 px-6 py-4 lg:px-10">
        <Link href="/" aria-label="Clothist — home" className="shrink-0">
          <span className="font-serif italic text-2xl leading-none">
            Clothist<span className="text-accent">.</span>
          </span>
        </Link>

        <nav className="hidden md:flex items-center gap-8" aria-label="Catalog navigation">
          {NAV.map((n) => {
            const active = pathname === n.href || pathname.startsWith(`${n.href}/`);
            return (
              <Link
                key={n.href}
                href={n.href}
                className={[
                  "font-mono text-[11px] uppercase tracking-widest transition-colors",
                  active ? "text-foreground" : "text-muted hover:text-foreground",
                ].join(" ")}
              >
                {n.label}
              </Link>
            );
          })}
        </nav>

        <div className="flex items-center gap-2">
          <ThemeToggle />
          <Link
            href="/"
            aria-label="AI search"
            className="grid h-9 w-9 place-items-center rounded-full text-muted hover:text-foreground hover:bg-bg-alt transition-colors"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.6"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden
            >
              <circle cx="11" cy="11" r="7" />
              <path d="m21 21-4.3-4.3" />
            </svg>
          </Link>
          <button
            type="button"
            onClick={open}
            aria-label={`Open cart (${count} items)`}
            className="relative grid h-9 w-9 place-items-center rounded-full text-muted hover:text-foreground hover:bg-bg-alt transition-colors"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.6"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden
            >
              <path d="M6 7h12l-1.5 11a2 2 0 0 1-2 1.7H9.5a2 2 0 0 1-2-1.7L6 7Z" />
              <path d="M9 7a3 3 0 0 1 6 0" />
            </svg>
            {count > 0 && (
              <span className="absolute -top-1 -right-1 bg-accent text-accent-fg font-mono text-[9px] min-w-[16px] h-4 px-1 grid place-items-center rounded-full">
                {count}
              </span>
            )}
          </button>
        </div>
      </div>
    </header>
  );
}
