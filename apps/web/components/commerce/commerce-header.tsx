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
    <header className="sticky top-0 z-40 bg-background/85 backdrop-blur-md hairline-b">
      <div className="mx-auto grid max-w-[1600px] grid-cols-[1fr_auto_1fr] items-center gap-6 px-6 py-5 lg:px-12 lg:py-6">
        {/* Left: nav (desktop) */}
        <nav
          className="hidden md:flex items-center gap-9"
          aria-label="Catalog navigation"
        >
          {NAV.map((n) => {
            const active = pathname === n.href || pathname.startsWith(`${n.href}/`);
            return (
              <Link
                key={n.href}
                href={n.href}
                className={[
                  "relative font-mono text-[11px] uppercase tracking-[0.18em] transition-colors",
                  active ? "text-foreground" : "text-muted hover:text-foreground",
                ].join(" ")}
              >
                {n.label}
                {active && (
                  <span
                    aria-hidden
                    className="absolute -bottom-1.5 left-0 right-0 h-px bg-foreground"
                  />
                )}
              </Link>
            );
          })}
        </nav>

        {/* Center: wordmark */}
        <Link
          href="/"
          aria-label="Clothist — home"
          className="font-display text-[26px] sm:text-[30px] leading-none tracking-[-0.06em] lowercase justify-self-center"
        >
          clothist<span className="text-accent">.</span>
        </Link>

        {/* Right: icons */}
        <div className="flex items-center justify-end gap-1">
          <ThemeToggle />
          <Link
            href="/"
            aria-label="AI search"
            className="grid h-10 w-10 place-items-center rounded-full text-muted hover:text-foreground hover:bg-bg-alt transition-colors"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="20"
              height="20"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden
            >
              <circle cx="11" cy="11" r="7" />
              <path d="m21 21-4.3-4.3" />
            </svg>
          </Link>
          <span
            aria-hidden
            className="mx-1 h-5 w-px bg-muted/30"
          />
          <button
            type="button"
            onClick={open}
            aria-label={`Open cart (${count} items)`}
            className="relative grid h-10 w-10 place-items-center rounded-full text-muted hover:text-foreground hover:bg-bg-alt transition-colors"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="20"
              height="20"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden
            >
              <path d="M6 7h12l-1.5 11a2 2 0 0 1-2 1.7H9.5a2 2 0 0 1-2-1.7L6 7Z" />
              <path d="M9 7a3 3 0 0 1 6 0" />
            </svg>
            {count > 0 && (
              <span className="absolute -top-0.5 -right-0.5 grid min-w-[18px] h-[18px] place-items-center rounded-full bg-foreground px-1 font-mono text-[9px] text-background">
                {count}
              </span>
            )}
          </button>
        </div>
      </div>

      {/* Mobile nav row */}
      <nav
        className="md:hidden hairline-t flex items-center justify-around px-6 py-3"
        aria-label="Catalog navigation, mobile"
      >
        {NAV.map((n) => {
          const active = pathname === n.href || pathname.startsWith(`${n.href}/`);
          return (
            <Link
              key={n.href}
              href={n.href}
              className={[
                "font-mono text-[11px] uppercase tracking-[0.18em]",
                active ? "text-foreground" : "text-muted",
              ].join(" ")}
            >
              {n.label}
            </Link>
          );
        })}
      </nav>
    </header>
  );
}
