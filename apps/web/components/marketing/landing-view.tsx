"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent } from "react";

import { CommerceHeader } from "@/components/commerce/commerce-header";

// The five storefronts we actively ingest from. Hard-coded rather than
// fetched so the hero strip stays static between renders / SSR.
const SOURCES = [
  "Rothy's",
  "Aimé Leon Dore",
  "Allbirds",
  "Princess Polly",
  "Kith",
];

// Cycled through the hero placeholder so the page nudges fresh prompt
// ideas every few seconds.
const PROMPT_EXAMPLES = [
  "vintage washed denim, loose fit",
  "minimalist white sneakers under $200",
  "waterproof shell, packable, mountain green",
  "oversized merino crewneck, no logos",
  "black cargo pants with hidden pockets",
];

export function LandingView() {
  return (
    <div className="relative z-10 min-h-screen overflow-hidden">
      <CommerceHeader />
      <Hero />
      <HowItWorks />
      <Preview />
      <WhatYouGet />
      <FinalCTA />
      <Footer />
    </div>
  );
}

/* -----------------------------------------------------------------
 * Hero
 * ---------------------------------------------------------------- */

function Hero() {
  const router = useRouter();
  const [value, setValue] = useState("");
  const [phIndex, setPhIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  // Soft placeholder rotation — fades the next prompt into the input
  // after a 3.5s dwell. Pauses while the user has the field focused.
  useEffect(() => {
    const t = setInterval(() => setPhIndex((i) => (i + 1) % PROMPT_EXAMPLES.length), 3500);
    return () => clearInterval(t);
  }, []);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const q = value.trim() || PROMPT_EXAMPLES[phIndex];
    router.push(`/search?q=${encodeURIComponent(q)}`);
  };

  return (
    <section className="relative px-6 pt-14 pb-12 lg:px-12 lg:pt-20 lg:pb-16">
      {/* faint vertical guide rules — lift the layout off pure black */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-y-0 left-6 right-6 lg:left-12 lg:right-12"
      >
        <div className="absolute inset-y-0 left-0 w-px bg-line/[0.06]" />
        <div className="absolute inset-y-0 right-0 w-px bg-line/[0.06]" />
      </div>

      <div className="mx-auto max-w-[1600px] relative">
        <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted">
          — Introducing Clothist AI
        </p>

        <h1 className="mt-12 font-display-tight leading-[0.86] tracking-[-0.045em] text-foreground">
          <span className="block anim-rise" style={{ animationDelay: "60ms", fontSize: "clamp(64px, 14vw, 220px)" }}>
            Describe it.
          </span>
          <span
            className="block anim-rise"
            style={{ animationDelay: "180ms", fontSize: "clamp(60px, 13vw, 200px)" }}
          >
            <span className="text-foreground/30">Find it.</span>{" "}
            <span>Wear it.</span>
          </span>
        </h1>

        {/* Search prompt */}
        <div className="mt-20 anim-rise" style={{ animationDelay: "360ms" }}>
          <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted">
            — Try the search
          </p>
          <form
            onSubmit={submit}
            className="mt-4 grid grid-cols-[minmax(0,1fr)_auto] gap-3 hairline-b items-stretch"
          >
            <div className="relative flex items-center">
              <span
                aria-hidden
                className="font-mono text-base text-muted/70 pr-3 select-none"
              >
                /
              </span>
              <input
                ref={inputRef}
                type="text"
                value={value}
                onChange={(e) => setValue(e.target.value)}
                placeholder={PROMPT_EXAMPLES[phIndex]}
                className="
                  w-full bg-transparent
                  font-sans text-[clamp(20px,2.4vw,32px)] leading-tight
                  text-foreground placeholder:text-muted/55
                  py-5 pr-4 outline-none
                  transition-colors
                "
                autoComplete="off"
                spellCheck={false}
                aria-label="Describe what you're looking for"
              />
            </div>
            <button
              type="submit"
              className="
                self-center px-7 py-3 my-3
                bg-foreground text-background
                font-mono text-[11px] uppercase tracking-[0.22em]
                hover:bg-foreground/90 transition-colors
                inline-flex items-center gap-2
              "
            >
              Search
              <ArrowOutIcon />
            </button>
          </form>
          <p className="mt-4 font-mono text-[10px] uppercase tracking-[0.22em] text-muted/80">
            ↵ Submits · AI parses to filters, then ranks across the catalog
          </p>
        </div>

        {/* Brand strip */}
        <div className="mt-20 lg:mt-32 anim-rise" style={{ animationDelay: "600ms" }}>
          <div className="grid grid-cols-[auto_minmax(0,1fr)] items-baseline gap-x-8">
            <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted shrink-0">
              — Reading from
            </p>
            <ul className="flex flex-wrap items-baseline gap-x-7 gap-y-3 text-muted/70">
              {SOURCES.map((s, i) => (
                <li key={s} className="flex items-baseline gap-7">
                  <span className="font-display text-[clamp(22px,2.6vw,40px)] tracking-[-0.02em] hover:text-foreground transition-colors">
                    {s}
                  </span>
                  {i < SOURCES.length - 1 && (
                    <span aria-hidden className="font-mono text-xs text-muted/40">✦</span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
}

/* -----------------------------------------------------------------
 * How it works
 * ---------------------------------------------------------------- */

const STEPS = [
  {
    n: "01",
    title: "Type, don't filter.",
    body: "Forget dropdowns and checkboxes. Write a sentence the way you'd text a friend who knows clothes.",
  },
  {
    n: "02",
    title: "AI fans out.",
    body: "We translate your prompt into structured filters and query dozens of stores in parallel — sizes, stock, price, the works.",
  },
  {
    n: "03",
    title: "Only the matches.",
    body: "A second pass re-ranks results against your intent. What lands on screen is what you'd actually buy.",
  },
];

function HowItWorks() {
  return (
    <section className="relative px-6 py-32 lg:px-12 lg:py-44">
      <div className="mx-auto max-w-[1600px]">
        <p className="text-center font-mono text-[10px] uppercase tracking-[0.22em] text-muted">
          — How it works
        </p>
        <h2
          className="mt-6 text-center font-display-tight leading-[0.9] tracking-[-0.045em] text-foreground"
          style={{ fontSize: "clamp(56px, 8.5vw, 152px)" }}
        >
          From sentence to shortlist.
        </h2>

        <ul className="mt-24 grid grid-cols-1 lg:grid-cols-3 gap-px bg-line/[0.08] hairline">
          {STEPS.map((s) => (
            <li key={s.n} className="bg-background p-10 lg:p-12 flex flex-col gap-12">
              <span className="font-mono text-[11px] tracking-[0.22em] text-muted">{s.n}</span>
              <h3 className="font-display text-[clamp(26px,2.8vw,36px)] tracking-[-0.02em] leading-tight">
                {s.title}
              </h3>
              <p className="text-[15px] leading-relaxed text-muted">{s.body}</p>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

/* -----------------------------------------------------------------
 * Results preview
 * ---------------------------------------------------------------- */

const PREVIEW_CARDS = [
  {
    match: "99%",
    quote: "black cargo pants under $100",
    brand: "Uniqlo",
    category: "Pants",
    price: "$89",
    bg: "linear-gradient(140deg, #1a1a1a 0%, #2c2c2c 60%, #383838 100%)",
  },
  {
    match: "98%",
    quote: "waterproof shell, packable",
    brand: "Arc'teryx",
    category: "Jackets",
    price: "$240",
    bg: "linear-gradient(140deg, #11362b 0%, #1f5240 55%, #2a6c54 100%)",
  },
  {
    match: "97%",
    quote: "minimalist white sneakers",
    brand: "COS",
    category: "Footwear",
    price: "$120",
    bg: "linear-gradient(140deg, #f0ece2 0%, #e6e0d2 100%)",
    onLight: true,
  },
  {
    match: "96%",
    quote: "oversized merino crewneck",
    brand: "Norse Projects",
    category: "Knitwear",
    price: "$185",
    bg: "linear-gradient(140deg, #6a3614 0%, #9a4c1e 55%, #b35a23 100%)",
  },
];

function Preview() {
  return (
    <section className="relative px-6 py-32 lg:px-12 lg:py-44 hairline-t">
      <div className="mx-auto max-w-[1600px]">
        <p className="text-center font-mono text-[10px] uppercase tracking-[0.22em] text-muted">
          — A quick preview
        </p>
        <h2
          className="mt-6 text-center font-display-tight leading-[0.9] tracking-[-0.045em]"
          style={{ fontSize: "clamp(56px, 8vw, 144px)" }}
        >
          Results, not noise.
        </h2>
        <p className="mt-6 text-center text-[15px] text-muted">
          Sample answers Clothist returned in &lt; 3s for real prompts.
        </p>

        <ul className="mt-20 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-px bg-line/[0.08] hairline">
          {PREVIEW_CARDS.map((c) => (
            <li
              key={c.match}
              className="bg-background flex flex-col"
            >
              <div
                className="relative aspect-[4/5]"
                style={{ background: c.bg }}
              >
                <span
                  className={[
                    "absolute top-4 left-4 px-2.5 py-1.5",
                    "font-mono text-[9px] uppercase tracking-[0.22em]",
                    c.onLight ? "bg-foreground text-background" : "bg-background/90 text-foreground",
                  ].join(" ")}
                >
                  Match · {c.match}
                </span>
                <p
                  className={[
                    "absolute bottom-4 left-4 right-4 font-mono text-[12px] leading-snug",
                    c.onLight ? "text-foreground" : "text-foreground",
                  ].join(" ")}
                >
                  &ldquo;{c.quote}&rdquo;
                </p>
              </div>
              <div className="flex items-baseline justify-between gap-4 px-5 py-5 hairline-t">
                <div className="min-w-0">
                  <p className="font-mono text-[9px] uppercase tracking-[0.22em] text-muted">
                    {c.brand}
                  </p>
                  <p className="mt-1.5 text-[15px] truncate">{c.category}</p>
                </div>
                <p className="font-mono text-[13px] shrink-0">{c.price}</p>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

/* -----------------------------------------------------------------
 * What you get
 * ---------------------------------------------------------------- */

const GETS = [
  {
    title: "No ads.",
    body: "Rankings are based on your prompt — never paid placement.",
  },
  {
    title: "Real stock.",
    body: "We check availability and size at query time, not from a stale index.",
  },
  {
    title: "One tab.",
    body: "Twelve stores, one rail. Click out only when you're ready to buy.",
  },
];

function WhatYouGet() {
  return (
    <section className="relative px-6 py-32 lg:px-12 lg:py-44 hairline-t">
      <div className="mx-auto max-w-[1600px]">
        <p className="text-center font-mono text-[10px] uppercase tracking-[0.22em] text-muted">
          — What you get
        </p>
        <h2
          className="mt-6 text-center font-display-tight leading-[0.9] tracking-[-0.045em]"
          style={{ fontSize: "clamp(56px, 8vw, 144px)" }}
        >
          What you get.
        </h2>

        <ul className="mt-24 grid grid-cols-1 lg:grid-cols-3 gap-x-16 gap-y-14">
          {GETS.map((g) => (
            <li key={g.title}>
              <div className="hairline-t pt-8 space-y-5">
                <h3 className="font-display text-[clamp(28px,2.8vw,36px)] tracking-[-0.02em]">
                  {g.title}
                </h3>
                <p className="text-[15px] leading-relaxed text-muted">{g.body}</p>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

/* -----------------------------------------------------------------
 * Final CTA — inverted to LIGHT to break the visual rhythm
 * ---------------------------------------------------------------- */

function FinalCTA() {
  return (
    // data-theme="light" flips every token used inside; bg/fg/muted/line
    // all invert without us touching individual classes.
    <section
      data-theme="light"
      className="relative bg-background text-foreground py-32 lg:py-48 px-6 lg:px-12"
    >
      <div className="mx-auto max-w-[1280px] text-center">
        <SparkleIcon />
        <h2
          className="mt-10 font-display-tight leading-[0.86] tracking-[-0.045em] text-foreground"
          style={{ fontSize: "clamp(72px, 11vw, 200px)" }}
        >
          Try a sentence.
        </h2>
        <p className="mt-8 text-[17px] text-muted max-w-xl mx-auto leading-relaxed">
          The catalog is open. Bring a prompt — Clothist brings the rest.
        </p>

        <div className="mt-12 flex flex-wrap items-center justify-center gap-3">
          <Link
            href="/search"
            className="
              inline-flex items-center gap-3
              bg-foreground text-background
              px-7 py-4 font-mono text-[11px] uppercase tracking-[0.22em]
              hover:bg-foreground/90 transition-colors
            "
          >
            <SearchIcon className="h-4 w-4" />
            Open the search
          </Link>
          <Link
            href="/products"
            className="
              inline-flex items-center gap-3
              border border-foreground px-7 py-4
              font-mono text-[11px] uppercase tracking-[0.22em]
              hover:bg-foreground hover:text-background transition-colors
            "
          >
            Browse all pieces
          </Link>
        </div>
      </div>
    </section>
  );
}

/* -----------------------------------------------------------------
 * Footer
 * ---------------------------------------------------------------- */

function Footer() {
  return (
    <footer className="px-6 lg:px-12 py-10 hairline-t">
      <div className="mx-auto max-w-[1600px] flex flex-wrap items-center justify-between gap-6">
        <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-muted">
          © 2026 Clothist — All rights reserved.
        </p>
        <ul className="flex items-center gap-8 font-mono text-[10px] uppercase tracking-[0.22em] text-muted">
          <li><Link href="#" className="hover:text-foreground">About</Link></li>
          <li><Link href="#" className="hover:text-foreground">Sources</Link></li>
          <li><Link href="#" className="hover:text-foreground">Privacy</Link></li>
        </ul>
      </div>
    </footer>
  );
}

/* -----------------------------------------------------------------
 * Icons
 * ---------------------------------------------------------------- */

function ArrowOutIcon() {
  return (
    <svg
      viewBox="0 0 14 14"
      className="h-3.5 w-3.5"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d="M3 11L11 3" />
      <path d="M5 3h6v6" />
    </svg>
  );
}

function SearchIcon({ className = "" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 16 16"
      className={className}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <circle cx="7" cy="7" r="4.5" />
      <path d="M10.5 10.5L13 13" />
    </svg>
  );
}

function SparkleIcon() {
  // Small four-point sparkle, gently glowing. Kept inline so the CTA
  // doesn't depend on an SVG asset.
  return (
    <svg
      viewBox="0 0 32 32"
      className="mx-auto h-7 w-7 text-foreground"
      aria-hidden
    >
      <path
        d="M16 3 L18 14 L29 16 L18 18 L16 29 L14 18 L3 16 L14 14 Z"
        fill="currentColor"
      />
      <path
        d="M25 6 L25.7 8.3 L28 9 L25.7 9.7 L25 12 L24.3 9.7 L22 9 L24.3 8.3 Z"
        fill="currentColor"
        opacity="0.6"
      />
    </svg>
  );
}
