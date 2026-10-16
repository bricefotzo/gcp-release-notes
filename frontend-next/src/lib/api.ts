// Centralised API client — proxied through Next.js rewrites → FastAPI backend

const BASE = "";  // empty = relative, Next.js rewrites /api/* to backend

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

// ── Types ──────────────────────────────────────────────────────────────────

export type ReleaseNote = {
  description: string;
  release_note_type: string;
  published_at: string;
  product_name: string;
  product_version_name: string;
};

export type FilterOptions = {
  types: string[];
  products: string[];
  min_date: string;
  max_date: string;
};

export type ReleaseNotesResponse = {
  data: ReleaseNote[];
  total: number;
};

// ── API helpers ────────────────────────────────────────────────────────────

export const getHealth = () => apiFetch<{ status: string }>("/api/health");

export const getFilterOptions = () => apiFetch<FilterOptions>("/api/filter-options");

export const getReleaseNotes = (params: {
  types?: string[];
  products?: string[];
  start_date?: string;
  end_date?: string;
  search?: string;
  page?: number;
  page_size?: number;
}) => {
  const qs = new URLSearchParams();
  params.types?.forEach((t) => qs.append("types", t));
  params.products?.forEach((p) => qs.append("products", p));
  if (params.start_date) qs.set("start_date", params.start_date);
  if (params.end_date) qs.set("end_date", params.end_date);
  if (params.search) qs.set("search", params.search);
  if (params.page) qs.set("page", String(params.page));
  if (params.page_size) qs.set("page_size", String(params.page_size));
  return apiFetch<ReleaseNotesResponse>(`/api/release-notes?${qs.toString()}`);
};

export type AIChatResponse = {
  answer: string;
  count: number;
  total: number;
};

export type AIQueryResponse = {
  sql: string;
  rows: Record<string, any>[];
  total: number;
};

export const postAIChat = (params: {
  question: string;
  products?: string[];
  types?: string[];
  start_date?: string;
  end_date?: string;
}) => apiFetch<AIChatResponse>("/api/ai/chat", {
  method: "POST",
  body: JSON.stringify(params),
});

export const postAIQuery = (question: string) => apiFetch<AIQueryResponse>("/api/ai/query", {
  method: "POST",
  body: JSON.stringify({ question }),
});

