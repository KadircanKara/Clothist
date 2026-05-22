"use client";

import { useEffect, useState } from "react";
import { DEFAULT_THEME, THEME_STORAGE_KEY, type Theme } from "@/lib/theme";
import { cn } from "@/lib/utils";

function readTheme(): Theme {
  if (typeof document === "undefined") return DEFAULT_THEME;
  const attr = document.documentElement.getAttribute("data-theme");
  return attr === "light" ? "light" : "dark";
}

export function ThemeToggle({ className }: { className?: string }) {
  const [theme, setTheme] = useState<Theme>(DEFAULT_THEME);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setTheme(readTheme());
    setMounted(true);
  }, []);

  const apply = (next: Theme) => {
    setTheme(next);
    document.documentElement.setAttribute("data-theme", next);
    try {
      localStorage.setItem(THEME_STORAGE_KEY, next);
    } catch {
      /* private mode etc. */
    }
  };

  return (
    <div
      role="group"
      aria-label="Theme"
      className={cn(
        "inline-flex items-center gap-0 rounded-full hairline overflow-hidden",
        "bg-background/40 backdrop-blur-sm",
        className,
      )}
    >
      <button
        type="button"
        aria-pressed={theme === "light"}
        onClick={() => apply("light")}
        className={cn(
          "px-3 py-1.5 text-[10px] font-mono uppercase tracking-widest transition-colors",
          mounted && theme === "light"
            ? "bg-foreground text-background"
            : "text-muted hover:text-foreground",
        )}
      >
        Light
      </button>
      <button
        type="button"
        aria-pressed={theme === "dark"}
        onClick={() => apply("dark")}
        className={cn(
          "px-3 py-1.5 text-[10px] font-mono uppercase tracking-widest transition-colors",
          mounted && theme === "dark"
            ? "bg-foreground text-background"
            : "text-muted hover:text-foreground",
        )}
      >
        Dark
      </button>
    </div>
  );
}
