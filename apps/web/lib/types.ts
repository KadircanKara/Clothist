export type Product = {
  id: string;
  retailer: string;
  retailer_product_id: string;
  url: string;
  title: string;
  brand: string | null;
  category: string | null;
  description: string | null;
  price: string | null;
  currency: string | null;
  original_price: string | null;
  image_url: string | null;
  colors: string[] | null;
  sizes: string[] | null;
  attributes: Record<string, unknown> | null;
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
  price: { min: string | null; max: string | null };
};

export type SearchParams = {
  q?: string;
  category?: string;
  brand?: string;
  color?: string;
  min_price?: number;
  max_price?: number;
  in_stock_only?: boolean;
  limit?: number;
  offset?: number;
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
};

export type IntentResponse = {
  raw_query: string;
  parsed: ParsedIntent;
  model: string;
  duration_ms: number;
};
