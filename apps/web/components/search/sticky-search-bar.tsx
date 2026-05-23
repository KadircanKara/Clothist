"use client";

import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

type Props = {
  value: string;
  onChange: (next: string) => void;
  onSubmit: () => void;
  onOpenFilters: () => void;
  /** Sentinel: when this element scrolls out of view, sticky-bar slides in. */
  sentinelTarget: React.RefObject<HTMLDivElement>;
};

export function StickySearchBar({
  value,
  onChange,
  onSubmit,
  onOpenFilters,
  sentinelTarget,
}: Props) {
  const [show, setShow] = useState(false);
  const observerRef = useRef<IntersectionObserver | null>(null);

  useEffect(() => {
    const target = sentinelTarget.current;
    if (!target) return;
    const obs = new IntersectionObserver(
      ([entry]) => {
        setShow(!entry.isIntersecting);
      },
      { root: null, threshold: 0 },
    );
    obs.observe(target);
    observerRef.current = obs;
    return () => {
      obs.disconnect();
      observerRef.current = null;
    };
  }, [sentinelTarget]);

  if (!show) return null;

  return (
    <div className="anim-fade fixed inset-x-0 top-0 z-30 bg-background/95 backdrop-blur md:hidden">
      <form
        role="search"
        onSubmit={(e) => {
          e.preventDefault();
          onSubmit();
        }}
        className="hairline-b px-5 py-3"
      >
        <div className="flex items-center gap-3">
          <span className="font-mono text-sm text-muted">/</span>
          <Input
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder="search"
            enterKeyHint="search"
            className="h-9 border-b-0 p-0 text-sm focus-visible:border-b-0"
          />
          <Button type="submit" size="sm" variant="default">
            ↵
          </Button>
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={onOpenFilters}
          >
            Filters
          </Button>
        </div>
      </form>
    </div>
  );
}
