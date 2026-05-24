import { Suspense } from "react";

import { SearchView } from "@/components/search/search-view";

export const metadata = { title: "Search — Clothist" };

export default function SearchPage() {
  // Wrapper because SearchView reads useSearchParams() — Suspense lets
  // Next.js stream the rest of the shell while the URL query resolves.
  return (
    <Suspense fallback={<div className="p-8 text-sm text-muted">Loading…</div>}>
      <SearchView />
    </Suspense>
  );
}
