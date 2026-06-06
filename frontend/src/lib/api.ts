/**
 * API module — domain helpers and endpoint registry.
 * All network calls go through the shared client in ./client.ts.
 */
export { fetchJson, fetcher } from './client';
import { fetchJson, mutateJson } from './client';

// ── Endpoint registry ────────────────────────────────────────────────────

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
  settingsModels: '/api/settings/models',
  scoringWeights: '/api/settings/scoring-weights',
  sources: '/api/sources',
  source: (slug: string) => `/api/sources/${slug}`,
  sourceTest: (slug: string) => `/api/sources/${slug}/test`,
  costSummary: (days: number = 30) => `/api/cost/summary?days=${days}`,
  pipelineRuns: '/api/pipeline/runs',
  pipelineRun: (id: string) => `/api/pipeline/runs/${id}`,
  promptPacks: '/api/prompt-packs',
  entities: '/api/entities',
  entitiesTrending: '/api/entities/trending',
  entity: (id: string) => `/api/entities/${id}`,
  entityMentions: (id: string, page: number = 0, limit: number = 50) =>
    `/api/entities/${id}/mentions?limit=${limit}&offset=${page * limit}`,
};

// ── Pipeline ─────────────────────────────────────────────────────────────

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
  return mutateJson(url.toString(), 'POST');
}

// ── Settings ─────────────────────────────────────────────────────────────

export async function postSettings(body: Record<string, string>): Promise<void> {
  await mutateJson('/api/settings', 'POST', body);
}

export async function postSettingsTest(): Promise<{ ok: boolean; message: string }> {
  return mutateJson('/api/settings/test', 'POST');
}

export async function fetchProviderModels(): Promise<{ models: string[]; source: string; error?: string }> {
  return fetchJson('/api/settings/models');
}

export async function fetchScoringWeights(): Promise<Record<string, number>> {
  return fetchJson(endpoints.scoringWeights);
}

export async function saveScoringWeights(weights: Record<string, number>): Promise<void> {
  await mutateJson(endpoints.scoringWeights, 'PUT', weights);
}

// ── Sources ──────────────────────────────────────────────────────────────

export async function postSourceCredentials(
  slug: string,
  credentials: Record<string, string | null>,
): Promise<void> {
  await mutateJson(`/api/sources/${slug}`, 'POST', { credentials });
}

export async function postSourceTest(slug: string): Promise<{ ok: boolean; message: string }> {
  return mutateJson(`/api/sources/${slug}/test`, 'POST');
}

// ── Niches ───────────────────────────────────────────────────────────────

export async function toggleShortlist(nicheId: string, starred: boolean): Promise<void> {
  if (starred) {
    await mutateJson(`/api/niches/${nicheId}/shortlist`, 'DELETE');
  } else {
    await mutateJson(`/api/niches/${nicheId}/shortlist`, 'POST', { note: '' });
  }
}

export async function validateNiche(nicheId: string): Promise<{ verdict: string; evidence: unknown[] }> {
  return mutateJson(`/api/niches/${nicheId}/validate`, 'POST');
}
