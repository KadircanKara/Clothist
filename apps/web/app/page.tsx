import { Suspense } from "react";
import { SearchView } from "@/components/search/search-view";

export default function HomePage() {
  return (
    <Suspense fallback={<div className="p-8 text-sm text-muted-foreground">Loading…</div>}>
      <SearchView />
    </Suspense>
  );
}
