"use client";

import { useState } from "react";
import { Sheet } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { FilterSidebar } from "./filter-sidebar";
import type { FacetsResponse, SearchParams } from "@/lib/types";

type Props = {
  open: boolean;
  onClose: () => void;
  facets: FacetsResponse | undefined;
  filters: SearchParams;
  onApply: (next: SearchParams) => void;
};

export function MobileFilterSheet({ open, onClose, facets, filters, onApply }: Props) {
  const [staged, setStaged] = useState<SearchParams>(filters);

  return (
    <Sheet open={open} onClose={onClose} ariaLabel="Filters">
      <div className="px-5 pb-6 pt-1">
        <div className="flex items-center justify-between pb-3 hairline-b">
          <span className="kicker">Filters</span>
          <button
            type="button"
            aria-label="Close filters"
            onClick={onClose}
            className="font-mono text-xs text-muted hover:text-foreground"
          >
            ×
          </button>
        </div>
        <div className="mt-4">
          <FilterSidebar
            facets={facets}
            filters={staged}
            onChange={setStaged}
            compact
          />
        </div>
        <div className="mt-6 flex gap-3">
          <Button
            variant="default"
            size="sm"
            className="flex-1"
            onClick={() => {
              onApply(staged);
              onClose();
            }}
          >
            Apply
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="flex-1"
            onClick={() => {
              const cleared: SearchParams = { q: filters.q, offset: 0 };
              setStaged(cleared);
              onApply(cleared);
              onClose();
            }}
          >
            Clear
          </Button>
        </div>
      </div>
    </Sheet>
  );
}
