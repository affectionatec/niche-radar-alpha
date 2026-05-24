'use client';
import { useState, useEffect, useRef } from 'react';
import useSWR from 'swr';
import { endpoints, fetcher, postPipeline } from '@/lib/api';
import { Job, JobDetail, JobStatus } from '@/lib/types';
import { usePipelineState } from '@/lib/usePipelineState';
import { color, font, fontSize, spacing, button as btnStyle, ALL_SOURCES, sourceLabel } from '@/lib/tokens';
import PipelineStages from '@/components/pipeline/PipelineStages';
import AgentActivity from '@/components/pipeline/AgentActivity';
import ActivityLog from '@/components/pipeline/ActivityLog';
import PipelineSummaryPanel from '@/components/pipeline/PipelineSummaryPanel';

const STEP_BUTTONS: { label: string; step: string; desc: string; primary?: boolean }[] = [
  { label: 'COLLECT', step: 'collect', desc: 'Gather from sources' },
  { label: 'ANALYZE', step: 'analyze', desc: 'LLM analysis' },
  { label: 'REPORT', step: 'report', desc: 'Generate report' },
  { label: 'RUN ALL', step: 'run-all', desc: 'Full pipeline', primary: true },
];

function statusColor(status: JobStatus): string {
  if (status === 'done') return 'rgba(255,255,255,0.9)';
  if (status === 'failed') return color.error;
  if (status === 'running') return color.fgSecondary;
  return color.fgGhost;
}

function statusDot(status: JobStatus): string {
  if (status === 'done') return color.success;
  if (status === 'failed') return color.error;
  if (status === 'running') return color.fgSecondary;
  return color.fgDisabled;
}

function ElapsedTime({ startTime }: { startTime: string }) {
  const [elapsed, setElapsed] = useState('');

  useEffect(() => {
    const start = new Date(startTime).getTime();
    function tick() {
      const diff = Math.floor((Date.now() - start) / 1000);
      const m = Math.floor(diff / 60);
      const s = diff % 60;
      setElapsed(m > 0 ? `${m}m ${s}s` : `${s}s`);
    }
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [startTime]);

  return (
    <span style={{ fontFamily: font.mono, fontSize: fontSize.sm, color: color.fgDisabled, letterSpacing: '0.5px' }}>
      {elapsed}
    </span>
  );
}

export default function PipelinePage() {
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [source, setSource] = useState('');
  const [launching, setLaunching] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const { data: jobs, mutate: mutateJobs } = useSWR<Job[]>(
    endpoints.jobs,
    fetcher,
    { refreshInterval: 5_000 },
  );

  const { data: activeJob, error: activeJobError } = useSWR<JobDetail>(
    activeJobId ? endpoints.jobLogs(activeJobId) : null,
    fetcher,
    {
      refreshInterval: (data?: JobDetail) =>
        data?.status === 'done' || data?.status === 'failed' ? 0 : 2_000,
      shouldRetryOnError: false,
      onSuccess: (data: JobDetail) => {
        if (data.status === 'done' || data.status === 'failed') {
          mutateJobs();
        }
      },
    },
  );

  const jobLost = Boolean(activeJobId && activeJobError);
  const pipelineState = usePipelineState(activeJob?.logs, activeJob?.step);
  const showVisualization = activeJobId && activeJob && (activeJob.step === 'analyze' || activeJob.step === 'run-all');

  async function launch(step: string) {
    setError(null);
    setLaunching(step);
    try {
      const params: Record<string, string> = {};
      if (step === 'collect' && source) params.source = source;
      const { job_id } = await postPipeline(step, Object.keys(params).length ? params : undefined);
      setActiveJobId(job_id);
      mutateJobs();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to launch job');
    } finally {
      setLaunching(null);
    }
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '48px', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h1 style={{ fontFamily: font.body, fontSize: fontSize['5xl'], fontWeight: 400, color: color.fg, marginBottom: '8px' }}>
            PIPELINE
          </h1>
          <p style={{ fontFamily: font.body, fontSize: fontSize.lg, color: color.fgDisabled }}>
            Collect data, run LLM analysis, and generate reports.
          </p>
        </div>
        {activeJob?.status === 'running' && activeJob.created_at && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: color.success, animation: 'pulse-border 1.5s ease-in-out infinite' }} />
            <span style={{ fontFamily: font.mono, fontSize: fontSize.base, color: color.fgMuted, letterSpacing: '0.5px', textTransform: 'uppercase' }}>
              Running
            </span>
            <ElapsedTime startTime={activeJob.created_at} />
          </div>
        )}
      </div>

      {/* Action bar */}
      <section style={{ marginBottom: '32px' }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px', alignItems: 'center' }}>
          <select
            value={source}
            onChange={(e) => setSource(e.target.value)}
            aria-label="Source filter"
            style={{
              background: color.surfaceHover,
              border: `1px solid ${color.border}`,
              color: color.fgSecondary,
              fontFamily: font.mono,
              fontSize: fontSize.base,
              letterSpacing: '0.8px',
              padding: '10px 14px',
              cursor: 'pointer',
              height: '40px',
            }}
          >
            <option value="" style={{ background: color.bg }}>ALL SOURCES</option>
            {ALL_SOURCES.map((s) => (
              <option key={s} value={s} style={{ background: color.bg }}>
                {sourceLabel[s] || s.toUpperCase()}
              </option>
            ))}
          </select>

          {STEP_BUTTONS.map(({ label, step, desc, primary }) => (
            <button
              key={step}
              disabled={launching !== null}
              onClick={() => launch(step)}
              aria-busy={launching === step}
              title={desc}
              style={{
                ...(primary ? btnStyle.primary : btnStyle.secondary),
                opacity: launching !== null ? 0.5 : 1,
                cursor: launching !== null ? 'not-allowed' : 'pointer',
              }}
            >
              {launching === step ? '...' : label}
            </button>
          ))}
        </div>

        {error && (
          <p role="alert" style={{ marginTop: '12px', fontFamily: font.mono, fontSize: fontSize.md, color: color.error }}>
            {error}
          </p>
        )}
      </section>

      {/* Lost-job notice */}
      {jobLost && (
        <section style={{ marginBottom: '24px' }}>
          <div
            role="alert"
            style={{
              background: 'rgba(251,191,36,0.08)',
              border: '1px solid rgba(251,191,36,0.3)',
              padding: '14px 18px',
              fontFamily: font.mono,
              fontSize: fontSize.md,
              color: color.warning,
              letterSpacing: '0.3px',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              gap: '16px',
            }}
          >
            <span>
              Job {activeJobId?.slice(0, 8)} is no longer tracked by the backend. Trigger a fresh run.
            </span>
            <button
              onClick={() => setActiveJobId(null)}
              style={{
                ...btnStyle.ghost,
                borderColor: 'rgba(251,191,36,0.5)',
                color: color.warning,
              }}
            >
              DISMISS
            </button>
          </div>
        </section>
      )}

      {/* Pipeline visualization */}
      {activeJobId && activeJob && (
        <section style={{ marginBottom: '48px' }}>
          {/* Job header */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
              <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: statusDot(activeJob.status) }} />
              <span style={{ fontFamily: font.mono, fontSize: fontSize.md, letterSpacing: '0.8px', textTransform: 'uppercase', color: color.fg }}>
                {activeJob.step}
              </span>
              <span style={{ fontFamily: font.mono, fontSize: fontSize.base, letterSpacing: '0.6px', textTransform: 'uppercase', color: statusColor(activeJob.status) }}>
                {activeJob.status}
              </span>
              {activeJob.status === 'running' && (
                <span style={{ fontFamily: font.mono, fontSize: fontSize.xs, letterSpacing: '1px', color: color.fgGhost, textTransform: 'uppercase' }}>
                  {activeJob.logs.length} log lines
                </span>
              )}
            </div>
            <button
              onClick={() => setActiveJobId(null)}
              aria-label="Dismiss job view"
              style={{ background: 'none', border: 'none', color: color.fgGhost, cursor: 'pointer', fontFamily: font.mono, fontSize: fontSize.base, letterSpacing: '0.5px' }}
            >
              DISMISS
            </button>
          </div>

          {/* Visual workflow stages */}
          {showVisualization && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <PipelineStages
                phases={pipelineState.phases}
                runAllSteps={pipelineState.runAllSteps}
                isRunAll={pipelineState.isRunAll}
                currentRunAllStep={pipelineState.currentRunAllStep}
              />

              {pipelineState.isComplete && pipelineState.summary && (
                <PipelineSummaryPanel
                  summary={pipelineState.summary}
                  clusterResults={pipelineState.clusterResults}
                />
              )}

              {pipelineState.agents.length > 0 && (
                <AgentActivity agents={pipelineState.agents} />
              )}

              <ActivityLog
                logs={activeJob.logs}
                isRunning={activeJob.status === 'running'}
              />
            </div>
          )}

          {/* Plain log viewer for collect/report steps */}
          {!showVisualization && (
            <div
              role="log"
              aria-label="Job output"
              style={{
                backgroundColor: color.surface,
                border: `1px solid ${color.border}`,
                padding: '16px 20px',
                maxHeight: '420px',
                overflowY: 'auto',
                fontFamily: font.mono,
                fontSize: fontSize.md,
                color: color.fgSecondary,
                lineHeight: 1.75,
              }}
            >
              {activeJob.logs.length === 0 ? (
                <span style={{ color: color.fgGhost }}>
                  {activeJob.status === 'pending' ? 'Starting...' : 'Waiting for output...'}
                </span>
              ) : (
                activeJob.logs.map((line: string, i: number) => (
                  <div key={i}>{line || ' '}</div>
                ))
              )}
            </div>
          )}
        </section>
      )}

      {/* Job history */}
      <section>
        <h2 style={{ fontFamily: font.body, fontSize: fontSize['3xl'], fontWeight: 400, color: color.fg, marginBottom: '20px' }}>
          HISTORY
        </h2>

        {!jobs || jobs.length === 0 ? (
          <p style={{ fontFamily: font.body, fontSize: fontSize.lg, color: color.fgGhost }}>
            No jobs yet. Use the buttons above to run a pipeline step.
          </p>
        ) : (
          <div style={{ border: `1px solid ${color.border}` }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 100px 180px 100px', padding: '10px 16px', borderBottom: `1px solid ${color.border}` }}>
              {['JOB', 'STEP', 'STARTED', 'STATUS'].map((h) => (
                <span key={h} style={{ ...({ fontFamily: font.body, fontSize: fontSize.sm, color: color.fgDisabled, letterSpacing: '0.8px', textTransform: 'uppercase' } as const) }}>
                  {h}
                </span>
              ))}
            </div>
            {jobs.map((job) => (
              <button
                key={job.id}
                onClick={() => setActiveJobId(job.id)}
                aria-label={`View job ${job.id.slice(0, 8)}, step ${job.step}, status ${job.status}`}
                style={{
                  display: 'grid',
                  gridTemplateColumns: '1fr 100px 180px 100px',
                  padding: '10px 16px',
                  borderBottom: '1px solid rgba(255,255,255,0.05)',
                  cursor: 'pointer',
                  backgroundColor: job.id === activeJobId ? color.surfaceActive : 'transparent',
                  width: '100%',
                  border: 'none',
                  textAlign: 'left',
                }}
              >
                <span style={{ fontFamily: font.mono, fontSize: fontSize.base, color: color.fgDisabled, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {job.id.slice(0, 8)}
                </span>
                <span style={{ fontFamily: font.mono, fontSize: fontSize.base, color: color.fg, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                  {job.step}
                </span>
                <span style={{ fontFamily: font.body, fontSize: fontSize.md, color: color.fgMuted }}>
                  {new Date(job.created_at).toLocaleString()}
                </span>
                <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: statusDot(job.status), flexShrink: 0 }} />
                  <span style={{ fontFamily: font.mono, fontSize: fontSize.base, textTransform: 'uppercase', letterSpacing: '0.5px', color: statusColor(job.status) }}>
                    {job.status}
                  </span>
                </span>
              </button>
            ))}
          </div>
        )}
      </section>

      {/* Pipeline Runs — A/B Comparison */}
      <PipelineRunsSection />
    </div>
  );
}

interface PipelineRun {
  id: string;
  prompt_hash: string;
  model: string;
  item_count: number;
  cluster_count: number;
  niche_count: number;
  budget_used: number;
  label: string | null;
  started_at: string;
  completed_at: string | null;
}

function PipelineRunsSection() {
  const { data: runs } = useSWR<PipelineRun[]>(endpoints.pipelineRuns, fetcher, { refreshInterval: 30_000 });

  if (!runs || runs.length === 0) return null;

  const hashes = Array.from(new Set(runs.map(r => r.prompt_hash)));
  const hashColor = (h: string) => {
    const idx = hashes.indexOf(h);
    const colors = [color.successMuted, color.info, color.warningMuted, color.errorMuted];
    return colors[idx % colors.length];
  };

  const GRID_COLS = '80px 100px 80px 60px 60px 60px 1fr';

  return (
    <section style={{ marginTop: spacing['4xl'] }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: spacing.lg }}>
        <h2 style={{ fontFamily: font.mono, fontSize: fontSize.sm, letterSpacing: '1px', color: color.fgDisabled, textTransform: 'uppercase' as const, margin: 0 }}>
          PIPELINE RUNS (A/B)
        </h2>
        <span style={{ fontFamily: font.mono, fontSize: fontSize.xs, color: color.fgGhost }}>
          {hashes.length} prompt version{hashes.length !== 1 ? 's' : ''}
        </span>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1px', background: color.surfaceHover }}>
        {/* Header */}
        <div style={{
          display: 'grid', gridTemplateColumns: GRID_COLS,
          padding: `${spacing.sm} ${spacing.lg}`, background: color.bg, gap: spacing.sm,
        }}>
          {['RUN', 'PROMPTS', 'MODEL', 'ITEMS', 'CLUST', 'NICHES', 'LABEL'].map(h => (
            <span key={h} style={{ fontFamily: font.mono, fontSize: fontSize.xs, color: color.fgGhost, letterSpacing: '0.5px' }}>{h}</span>
          ))}
        </div>
        {runs.slice(0, 15).map((run) => (
          <div key={run.id} style={{
            display: 'grid', gridTemplateColumns: GRID_COLS,
            padding: `${spacing.md} ${spacing.lg}`, background: color.bg, gap: spacing.sm, alignItems: 'center',
          }}>
            <span style={{ fontFamily: font.mono, fontSize: fontSize.base, color: color.fgMuted }}>{run.id.slice(0, 8)}</span>
            <span style={{ fontFamily: font.mono, fontSize: fontSize.sm, color: hashColor(run.prompt_hash) }}>{run.prompt_hash}</span>
            <span style={{ fontFamily: font.mono, fontSize: fontSize.xs, color: color.fgDisabled, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const }}>{run.model}</span>
            <span style={{ fontFamily: font.mono, fontSize: fontSize.base, color: color.fg }}>{run.item_count}</span>
            <span style={{ fontFamily: font.mono, fontSize: fontSize.base, color: color.fg }}>{run.cluster_count}</span>
            <span style={{ fontFamily: font.mono, fontSize: fontSize.base, color: color.fg }}>{run.niche_count}</span>
            <span style={{ fontFamily: font.mono, fontSize: fontSize.sm, color: run.label ? color.fg : color.fgGhost }}>
              {run.label || '—'}
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}
