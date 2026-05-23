"use client";

import { useEffect, useState } from "react";
import type { DegradedReason } from "@/lib/types";

const COPY: Record<DegradedReason, string> = {
  llm_rate_limited:
    "The AI parser is over its free-tier quota. We're matching your words against product text instead. Price and currency filters from your query still work.",
  llm_timeout:
    "The AI parser didn't reply in time. We're matching your words against product text instead. Price and currency filters from your query still work.",
  llm_5xx:
    "The AI parser is having a moment. We're matching your words against product text instead. Price and currency filters from your query still work.",
  llm_disabled:
    "The AI parser isn't configured for this build. We're matching your words against product text instead. Price and currency filters from your query still work.",
};

type Props = {
  reason: DegradedReason;
};

export function DegradedBanner({ reason }: Props) {
  const storageKey = `clothist:degraded-dismiss:${reason}`;
  const [dismissed, setDismissed] = useState(true);

  useEffect(() => {
    // Re-read on mount so that hydration mismatch doesn't flash the banner.
    if (typeof window === "undefined") return;
    setDismissed(window.sessionStorage.getItem(storageKey) === "1");
  }, [storageKey]);

  if (dismissed) return null;

  const dismiss = () => {
    if (typeof window !== "undefined") {
      window.sessionStorage.setItem(storageKey, "1");
    }
    setDismissed(true);
  };

  return (
    <div
      role="status"
      aria-live="polite"
      className="anim-fade hairline relative mb-4 flex items-start gap-4 bg-bg-alt/60 px-4 py-3 pl-5"
      style={{ borderLeft: "4px solid rgb(var(--warn))" }}
    >
      <div className="grow">
        <p className="font-mono text-[11px] uppercase tracking-widest text-warn">
          <strong className="font-medium">AI parser offline — keyword search only</strong>
        </p>
        <p className="serif-eyebrow mt-1 text-sm">{COPY[reason]}</p>
      </div>
      <button
        type="button"
        aria-label="Dismiss AI offline notice"
        onClick={dismiss}
        className="shrink-0 font-mono text-xs text-muted hover:text-foreground transition-colors"
      >
        ×
      </button>
    </div>
  );
}
