const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

export async function fetcher<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`API ${res.status}: ${url}`);
  return res.json() as Promise<T>;
}

export async function postPipeline(
  step: string,
  params?: Record<string, string>,
): Promise<{ job_id: string; status: string }> {
  const url = new URL(`${API_URL}/api/pipeline/${step}`);
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      url.searchParams.set(k, v);
    }
  }
  const res = await fetch(url.toString(), { method: 'POST' });
  if (!res.ok) throw new Error(`Pipeline ${step} failed: ${res.status}`);
  return res.json() as Promise<{ job_id: string; status: string }>;
}

export async function postSettings(body: Record<string, string>): Promise<void> {
  const res = await fetch(`${API_URL}/api/settings`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`Settings update failed: ${res.status}`);
}

export const endpoints = {
  status: `${API_URL}/api/status`,
  niches: `${API_URL}/api/niches`,
  niche: (id: string) => `${API_URL}/api/niches/${id}`,
  reports: `${API_URL}/api/reports`,
  reportContent: (filename: string) => `${API_URL}/api/reports/${encodeURIComponent(filename)}`,
  jobs: `${API_URL}/api/pipeline/jobs`,
  jobLogs: (id: string) => `${API_URL}/api/pipeline/jobs/${id}/logs`,
  settings: `${API_URL}/api/settings`,
};
