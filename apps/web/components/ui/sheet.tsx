"use client";

import { useEffect } from "react";
import { createPortal } from "react-dom";

type Props = {
  open: boolean;
  onClose: () => void;
  children: React.ReactNode;
  side?: "bottom";
  ariaLabel?: string;
};

/**
 * Minimal portal sheet primitive — scrim + focus-trap-ish behavior. ESC and
 * scrim click both close. Not a full dialog library; enough for one use site.
 */
export function Sheet({ open, onClose, children, ariaLabel = "Panel" }: Props) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = previousOverflow;
    };
  }, [open, onClose]);

  if (!open || typeof document === "undefined") return null;

  return createPortal(
    <div
      role="dialog"
      aria-modal="true"
      aria-label={ariaLabel}
      className="fixed inset-0 z-50 flex items-end"
    >
      <button
        aria-label="Close sheet"
        onClick={onClose}
        className="absolute inset-0 bg-foreground/30"
        tabIndex={-1}
      />
      <div className="anim-rise relative max-h-[85vh] w-full overflow-y-auto bg-background hairline-t">
        <div className="mx-auto h-1 w-12 rounded-full bg-muted/40 mt-2 mb-3" aria-hidden />
        {children}
      </div>
    </div>,
    document.body,
  );
}
