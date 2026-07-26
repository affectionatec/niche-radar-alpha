/**
 * Shared HTTP client for all Niche Radar API calls.
 * All domain modules (niches, entities, settings…) import from here.
 */

/** Base URL for the backend API (auto-detected via Next.js proxy). */
const BASE_URL = '';

export const AUTH_REQUIRED_EVENT = 'niche-radar:auth-required';

export interface SessionUser {
  username: string;
}

function signalAuthenticationRequired(response: Response): void {
  if (response.status === 401 && typeof window !== 'undefined') {
    window.dispatchEvent(new Event(AUTH_REQUIRED_EVENT));
  }
}

/** Generic typed GET fetch. Throws on non-2xx. */
export async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${url}`, { credentials: 'same-origin' });
  signalAuthenticationRequired(res);
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
    credentials: 'same-origin',
    headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  signalAuthenticationRequired(res);
  if (!res.ok) throw new Error(`API ${method} ${res.status}: ${url}`);
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

/** SWR-compatible fetcher (single-arg, returns typed data). */
export async function fetcher<T>(url: string): Promise<T> {
  return fetchJson<T>(url);
}

export function getSession(): Promise<SessionUser> {
  return fetchJson<SessionUser>('/api/auth/me');
}

export function login(username: string, password: string): Promise<SessionUser> {
  return mutateJson<SessionUser>('/api/auth/login', 'POST', { username, password });
}

export async function logout(): Promise<void> {
  try {
    await mutateJson<void>('/api/auth/logout', 'POST');
  } finally {
    if (typeof window !== 'undefined') window.location.assign('/login');
  }
}
