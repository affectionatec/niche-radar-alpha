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
  nicheMomentum: (id: string) => `/api/niches/${id}/momentum`,
  shortlist: '/api/shortlist',
  reports: '/api/reports',
  reportContent: (filename: string) => `/api/reports/${encodeURIComponent(filename)}`,
  jobs: '/api/pipeline/jobs',
  jobLogs: (id: string) => `/api/pipeline/jobs/${id}/logs`,
  settings: '/api/settings',
  sources: '/api/sources',
  source: (slug: string) => `/api/sources/${slug}`,
  sourceTest: (slug: string) => `/api/sources/${slug}/test`,
};

export async function postSourceCredentials(
  slug: string,
  credentials: Record<string, string | null>,
): Promise<void> {
  const res = await fetch(`/api/sources/${slug}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ credentials }),
  });
  if (!res.ok) throw new Error(`Source update failed: ${res.status}`);
}

export async function postSourceTest(slug: string): Promise<{ ok: boolean; message: string }> {
  const res = await fetch(`/api/sources/${slug}/test`, { method: 'POST' });
  if (!res.ok) throw new Error(`Source test failed: ${res.status}`);
  return res.json() as Promise<{ ok: boolean; message: string }>;
}

export async function toggleShortlist(nicheId: string, starred: boolean): Promise<void> {
  const method = starred ? 'DELETE' : 'POST';
  const res = await fetch(`/api/niches/${nicheId}/shortlist`, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: starred ? undefined : JSON.stringify({ note: '' }),
  });
  if (!res.ok) throw new Error(`Shortlist toggle failed: ${res.status}`);
}

export async function validateNiche(nicheId: string): Promise<{ verdict: string; evidence: unknown[] }> {
  const res = await fetch(`/api/niches/${nicheId}/validate`, { method: 'POST' });
  if (!res.ok) throw new Error(`Validate failed: ${res.status}`);
  return res.json();
}
