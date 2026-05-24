export type ProductVariant = {
  color: string;
  /** Hero image — same as images[0] when `images` is populated. Kept as
   *  a flat field for back-compat with older ingest payloads. */
  image_url: string;
  /** Full image set for this color, hero first. The PDP gallery uses
   *  this to render a thumbnail strip; falls back to [image_url] when
   *  the source didn't yield additional images. */
  images?: string[];
  ai_generated?: boolean;
  /** Per-variant in-stock signal (Shopify variants[].available). Phase 1
   *  ingests populate this; renderers may ignore it for MVP. */
  available?: boolean;
  /** True when the variant's image is a positional/categorical guess
   *  rather than a vendor-confirmed color match. Reserved for Phase 2 UI. */
  image_inferred?: boolean;
};

export type Product = {
  id: string;
  retailer: string;
  retailer_product_id: string;
  url: string;
  title: string;
  brand: string | null;
  category: string | null;
  gender: string | null;
  description: string | null;
  price: string | null;
  currency: string | null;
  original_price: string | null;
  price_usd: string | null;
  display_price: string | null;
  image_url: string | null;
  colors: string[] | null;
  sizes: string[] | null;
  attributes:
    | ({ features?: string[]; variants?: ProductVariant[] } & Record<string, unknown>)
    | null;
  in_stock: boolean;
};

export type SearchResponse = {
  query: string | null;
  total: number;
  limit: number;
  offset: number;
  items: Product[];
};

export type FacetValue = { value: string; count: number };

export type FacetsResponse = {
  categories: FacetValue[];
  brands: FacetValue[];
  colors: FacetValue[];
  price: { min: string | null; max: string | null };
  features: string[];
  fx_date: string | null;
};

export type SortKey =
  | "relevance"
  | "price_asc"
  | "price_desc"
  | "newest"
  | "highest_rated";

export type SearchParams = {
  q?: string;
  // Multi-select: pass `["tshirts", "hoodies"]` and the API matches
  // either. Single-value `"tshirts"` still works.
  category?: string | string[];
  // Multi-select brand: same shape as category.
  brand?: string | string[];
  gender?: "men" | "women" | "unisex";
  color?: string;
  min_price?: number;
  max_price?: number;
  in_stock_only?: boolean;
  features?: string[];
  excluded_features?: string[];
  sort?: SortKey;
  currency?: string;
  limit?: number;
  offset?: number;
};

export type AmbiguityHint = {
  token: string;
  parsed_as: string;
  alternative: string;
};

export type ParsedIntent = {
  category: string | null;
  brand: string | null;
  color: string | null;
  min_price: number | null;
  max_price: number | null;
  in_stock_only: boolean;
  refined_query: string | null;
  explanation: string;
  features: string[];
  excluded_features: string[];
  sort: SortKey;
  detected_currency: string | null;
  detected_amount_native: string | null;
  ambiguity_hint: AmbiguityHint | null;
  locale: string;
};

export type DegradedReason =
  | "llm_rate_limited"
  | "llm_timeout"
  | "llm_5xx"
  | "llm_disabled";

export type IntentResponse = {
  raw_query: string;
  parsed: ParsedIntent;
  model: string;
  duration_ms: number;
  degraded: boolean;
  degraded_reason: DegradedReason | null;
  ui_hints: string[];
};
