import type {
  FacetsResponse,
  IntentResponse,
  SearchParams,
  SearchResponse,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function buildQuery(params: Record<string, unknown>): string {
  const usp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "") continue;
    usp.set(k, String(v));
  }
  const qs = usp.toString();
  return qs ? `?${qs}` : "";
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly path: string,
    public readonly body: unknown,
  ) {
    super(`API ${path} failed: ${status}`);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    let body: unknown = null;
    try {
      body = await res.json();
    } catch {
      /* non-json body */
    }
    throw new ApiError(res.status, path, body);
  }
  return res.json() as Promise<T>;
}

export function searchProducts(params: SearchParams): Promise<SearchResponse> {
  return request<SearchResponse>(`/search${buildQuery(params as Record<string, unknown>)}`);
}

export function getFacets(): Promise<FacetsResponse> {
  return request<FacetsResponse>("/search/facets");
}

export function parseIntent(q: string): Promise<IntentResponse> {
  return request<IntentResponse>("/search/intent", {
    method: "POST",
    body: JSON.stringify({ q }),
  });
}
