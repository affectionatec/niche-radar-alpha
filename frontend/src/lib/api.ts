export async function fetcher<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`API ${res.status}: ${url}`);
  return res.json() as Promise<T>;
}

export async function postPipeline(
  step: string,
  params?: Record<string, string>,
): Promise<{ job_id: string; status: string }> {
  const url = new URL(`/api/pipeline/${step}`, window.location.origin);
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
  const res = await fetch('/api/settings', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`Settings update failed: ${res.status}`);
}

export async function postSettingsTest(): Promise<{ ok: boolean; message: string }> {
  const res = await fetch('/api/settings/test', { method: 'POST' });
  if (!res.ok) throw new Error(`Test request failed: ${res.status}`);
  return res.json() as Promise<{ ok: boolean; message: string }>;
}

export const endpoints = {
  status: '/api/status',
  niches: '/api/niches',
  niche: (id: string) => `/api/niches/${id}`,
  reports: '/api/reports',
  reportContent: (filename: string) => `/api/reports/${encodeURIComponent(filename)}`,
  jobs: '/api/pipeline/jobs',
  jobLogs: (id: string) => `/api/pipeline/jobs/${id}/logs`,
  settings: '/api/settings',
};
