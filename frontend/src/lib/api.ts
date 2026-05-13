const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

export async function fetcher<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`API ${res.status}: ${url}`);
  return res.json() as Promise<T>;
}

export const endpoints = {
  status: `${API_URL}/api/status`,
  niches: `${API_URL}/api/niches`,
  niche: (id: string) => `${API_URL}/api/niches/${id}`,
  reports: `${API_URL}/api/reports`,
};
