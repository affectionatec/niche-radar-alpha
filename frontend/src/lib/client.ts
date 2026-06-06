/**
 * Shared HTTP client for all Niche Radar API calls.
 * All domain modules (niches, entities, settings…) import from here.
 */

/** Base URL for the backend API (auto-detected via Next.js proxy). */
const BASE_URL = '';

/** Generic typed GET fetch. Throws on non-2xx. */
export async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${url}`);
  if (!res.ok) throw new Error(`API ${res.status}: ${url}`);
  return res.json() as Promise<T>;
}

/** Generic typed POST/PUT/DELETE. Throws on non-2xx. */
export async function mutateJson<T>(
  url: string,
  method: 'POST' | 'PUT' | 'DELETE' = 'POST',
  body?: unknown,
): Promise<T> {
  const res = await fetch(`${BASE_URL}${url}`, {
    method,
    headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`API ${method} ${res.status}: ${url}`);
  return res.json() as Promise<T>;
}

/** SWR-compatible fetcher (single-arg, returns typed data). */
export async function fetcher<T>(url: string): Promise<T> {
  return fetchJson<T>(url);
}
