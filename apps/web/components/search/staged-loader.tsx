"use client";

import { useEffect, useState } from "react";

/**
 * Staged search loader.
 *
 * Three honest stages tied to what the pipeline actually does:
 *   1. "Reading your prompt"     — LLM intent parse
 *   2. "Searching the catalog"   — Postgres FTS + filters
 *   3. "Building your filter set" — clientside facet derivation
 *
 * `stage` is driven by the parent (0 = idle, 1/2/3 = active), so we can
 * advance in lock-step with real events. We also nudge the stage forward
 * after a minimum dwell so a sub-200ms query still feels like a process.
 */

export type LoaderStage = 0 | 1 | 2 | 3;

const STAGES = [
  { idx: 1, label: "Reading your prompt" },
  { idx: 2, label: "Searching the catalog" },
  { idx: 3, label: "Building your filter set" },
] as const;

export function StagedLoader({ stage }: { stage: LoaderStage }) {
  // The parent drives `stage` strictly upward. We mirror it locally so a
  // very fast query still shows each label for a beat instead of
  // flashing past — the UX value of the loader is the narration.
  const [display, setDisplay] = useState<LoaderStage>(stage);
  useEffect(() => {
    if (stage <= display) return;
    // Catch up gradually if the parent jumped ahead (e.g., when the
    // API returned faster than the minimum dwell).
    const t = setTimeout(() => setDisplay((d) => (d + 1) as LoaderStage), 280);
    return () => clearTimeout(t);
  }, [stage, display]);

  if (display === 0) return null;

  return (
    <div className="mt-12 anim-fade">
      <ul className="space-y-3 max-w-[520px]">
        {STAGES.map((s) => {
          const isDone = display > s.idx;
          const isActive = display === s.idx;
          const isPending = display < s.idx;
          return (
            <li
              key={s.idx}
              className={[
                "flex items-center gap-4 font-mono text-[12px] uppercase tracking-[0.18em] transition-opacity",
                isPending ? "opacity-25" : "opacity-100",
              ].join(" ")}
            >
              <StageIcon isActive={isActive} isDone={isDone} />
              <span className={isActive ? "text-foreground" : "text-muted"}>
                {s.label}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function StageIcon({ isActive, isDone }: { isActive: boolean; isDone: boolean }) {
  if (isDone) {
    return (
      <svg viewBox="0 0 16 16" className="h-3 w-3 text-foreground" aria-hidden>
        <path
          d="M3.5 8.5 L6.5 11.5 L12.5 4.5"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    );
  }
  if (isActive) {
    return (
      <span
        aria-hidden
        className="staged-spin block h-3 w-3 rounded-full border border-foreground border-t-transparent"
      />
    );
  }
  return (
    <span
      aria-hidden
      className="block h-3 w-3 rounded-full border border-line/30"
    />
  );
}
