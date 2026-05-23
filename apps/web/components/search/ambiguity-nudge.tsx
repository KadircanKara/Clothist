"use client";

import { useState } from "react";
import type { AmbiguityHint } from "@/lib/types";

type Props = {
  hint: AmbiguityHint;
  onAccept: (alternative: string) => void;
};

export function AmbiguityNudge({ hint, onAccept }: Props) {
  const [dismissed, setDismissed] = useState(false);
  if (dismissed) return null;

  return (
    <div
      role="alertdialog"
      aria-labelledby="ambiguity-text"
      className="anim-fade mt-3 flex flex-wrap items-center gap-3 bg-bg-alt/40 px-4 py-3 text-sm"
      style={{ borderLeft: "4px solid rgb(var(--warn))" }}
    >
      <span id="ambiguity-text" className="font-mono text-[11px] uppercase tracking-widest text-warn">
        ! We read &ldquo;{hint.token}&rdquo; as {hint.parsed_as} — was it {hint.alternative}?
      </span>
      <button
        type="button"
        onClick={() => onAccept(hint.alternative)}
        className="hairline rounded-full px-3 py-1 font-mono text-[11px] uppercase tracking-widest text-warn hover:bg-warn hover:text-background transition-colors"
      >
        Yes, {hint.alternative}
      </button>
      <button
        type="button"
        onClick={() => setDismissed(true)}
        className="font-mono text-[11px] uppercase tracking-widest text-muted hover:text-foreground transition-colors"
      >
        No, keep {hint.parsed_as}
      </button>
    </div>
  );
}
