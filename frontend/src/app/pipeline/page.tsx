'use client';
import { useState, useEffect, useRef } from 'react';
import useSWR from 'swr';
import { endpoints, fetcher, postPipeline } from '@/lib/api';
import { Job, JobDetail, JobStatus } from '@/lib/types';
import { usePipelineState } from '@/lib/usePipelineState';
import PipelineStages from '@/components/pipeline/PipelineStages';
import AgentActivity from '@/components/pipeline/AgentActivity';
import ActivityLog from '@/components/pipeline/ActivityLog';
import PipelineSummaryPanel from '@/components/pipeline/PipelineSummaryPanel';

const SOURCES = ['', 'reddit', 'hn', 'google_trends', 'github', 'youtube'] as const;

const STEP_BUTTONS: { label: string; step: string; primary?: boolean }[] = [
  { label: 'COLLECT', step: 'collect' },
  { label: 'ANALYZE', step: 'analyze' },
  { label: 'REPORT', step: 'report' },
  { label: 'RUN ALL', step: 'run-all', primary: true },
];

function statusColor(status: JobStatus): string {
  if (status === 'done') return 'rgba(255,255,255,0.9)';
  if (status === 'failed') return 'rgba(255,80,80,0.85)';
  if (status === 'running') return 'rgba(255,255,255,0.6)';
  return 'rgba(255,255,255,0.3)';
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

  // Parse logs into structured pipeline state
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
      <h1
        style={{
          fontFamily: 'var(--font-inter)',
          fontSize: '30px',
          fontWeight: 400,
          color: '#ffffff',
          marginBottom: '48px',
        }}
      >
        PIPELINE
      </h1>

      {/* Action bar */}
      <section style={{ marginBottom: '32px' }}>
        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: '12px',
            alignItems: 'center',
          }}
        >
          <select
            value={source}
            onChange={(e) => setSource(e.target.value)}
            style={{
              background: 'rgba(255,255,255,0.06)',
              border: '1px solid rgba(255,255,255,0.15)',
              color: 'rgba(255,255,255,0.7)',
              fontFamily: 'var(--font-geist-mono)',
              fontSize: '11px',
              letterSpacing: '0.8px',
              padding: '10px 14px',
              cursor: 'pointer',
              height: '40px',
            }}
          >
            {SOURCES.map((s) => (
              <option key={s} value={s} style={{ background: '#1f2228' }}>
                {s ? s.toUpperCase() : 'ALL SOURCES'}
              </option>
            ))}
          </select>

          {STEP_BUTTONS.map(({ label, step, primary }) => (
            <button
              key={step}
              disabled={launching !== null}
              onClick={() => launch(step)}
              style={{
                background: primary ? '#ffffff' : 'transparent',
                border: primary ? 'none' : '1px solid rgba(255,255,255,0.25)',
                color: primary ? '#1f2228' : '#ffffff',
                fontFamily: 'var(--font-geist-mono)',
                fontSize: '11px',
                fontWeight: primary ? 600 : 400,
                letterSpacing: '1px',
                textTransform: 'uppercase',
                padding: '0 20px',
                height: '40px',
                cursor: launching !== null ? 'not-allowed' : 'pointer',
                opacity: launching !== null ? 0.5 : 1,
              }}
            >
              {launching === step ? '...' : label}
            </button>
          ))}
        </div>

        {error && (
          <p
            style={{
              marginTop: '12px',
              fontFamily: 'var(--font-geist-mono)',
              fontSize: '12px',
              color: 'rgba(255,80,80,0.85)',
            }}
          >
            {error}
          </p>
        )}
      </section>

      {/* Lost-job notice */}
      {jobLost && (
        <section style={{ marginBottom: '24px' }}>
          <div
            style={{
              background: 'rgba(251,191,36,0.08)',
              border: '1px solid rgba(251,191,36,0.3)',
              padding: '14px 18px',
              fontFamily: 'var(--font-geist-mono)',
              fontSize: '12px',
              color: 'rgba(251,191,36,0.9)',
              letterSpacing: '0.3px',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              gap: '16px',
            }}
          >
            <span>
              Job {activeJobId?.slice(0, 8)} is no longer tracked by the backend
              (likely killed by a restart). Trigger a fresh run.
            </span>
            <button
              onClick={() => setActiveJobId(null)}
              style={{
                background: 'transparent',
                border: '1px solid rgba(251,191,36,0.5)',
                color: 'rgba(251,191,36,0.9)',
                fontFamily: 'var(--font-geist-mono)',
                fontSize: '11px',
                letterSpacing: '0.5px',
                padding: '5px 12px',
                cursor: 'pointer',
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
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: '16px',
            }}
          >
            <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
              <span
                style={{
                  fontFamily: 'var(--font-geist-mono)',
                  fontSize: '12px',
                  letterSpacing: '0.8px',
                  textTransform: 'uppercase',
                  color: '#ffffff',
                }}
              >
                {activeJob.step}
              </span>
              <span
                style={{
                  fontFamily: 'var(--font-geist-mono)',
                  fontSize: '11px',
                  letterSpacing: '0.6px',
                  textTransform: 'uppercase',
                  color: statusColor(activeJob.status),
                }}
              >
                {activeJob.status}
              </span>
              {activeJob.status === 'running' && (
                <span
                  style={{
                    fontFamily: 'var(--font-geist-mono)',
                    fontSize: '9px',
                    letterSpacing: '1px',
                    color: 'rgba(255,255,255,0.3)',
                    textTransform: 'uppercase',
                  }}
                >
                  {activeJob.logs.length} log lines
                </span>
              )}
            </div>
            <button
              onClick={() => setActiveJobId(null)}
              style={{
                background: 'none',
                border: 'none',
                color: 'rgba(255,255,255,0.3)',
                cursor: 'pointer',
                fontFamily: 'var(--font-geist-mono)',
                fontSize: '11px',
                letterSpacing: '0.5px',
              }}
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

              {/* Pipeline summary when complete */}
              {pipelineState.isComplete && pipelineState.summary && (
                <PipelineSummaryPanel
                  summary={pipelineState.summary}
                  clusterResults={pipelineState.clusterResults}
                />
              )}

              {/* Agent activity */}
              {pipelineState.agents.length > 0 && (
                <AgentActivity agents={pipelineState.agents} />
              )}

              {/* Collapsible raw logs */}
              <ActivityLog
                logs={activeJob.logs}
                isRunning={activeJob.status === 'running'}
              />
            </div>
          )}

          {/* Plain log viewer for collect/report steps */}
          {!showVisualization && (
            <div
              style={{
                backgroundColor: 'rgba(255,255,255,0.04)',
                border: '1px solid rgba(255,255,255,0.1)',
                padding: '16px 20px',
                maxHeight: '420px',
                overflowY: 'auto',
                fontFamily: 'var(--font-geist-mono)',
                fontSize: '12px',
                color: 'rgba(255,255,255,0.7)',
                lineHeight: 1.75,
              }}
            >
              {activeJob.logs.length === 0 ? (
                <span style={{ color: 'rgba(255,255,255,0.25)' }}>
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
        <h2
          style={{
            fontFamily: 'var(--font-inter)',
            fontSize: '20px',
            fontWeight: 400,
            color: '#ffffff',
            marginBottom: '20px',
          }}
        >
          HISTORY
        </h2>

        {!jobs || jobs.length === 0 ? (
          <p
            style={{
              fontFamily: 'var(--font-inter)',
              fontSize: '13px',
              color: 'rgba(255,255,255,0.3)',
              fontStyle: 'italic',
            }}
          >
            No jobs yet. Use the buttons above to run a pipeline step.
          </p>
        ) : (
          <div style={{ border: '1px solid rgba(255,255,255,0.1)' }}>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr 100px 180px 100px',
                padding: '10px 16px',
                borderBottom: '1px solid rgba(255,255,255,0.08)',
              }}
            >
              {['JOB', 'STEP', 'STARTED', 'STATUS'].map((h) => (
                <span
                  key={h}
                  style={{
                    fontFamily: 'var(--font-inter)',
                    fontSize: '10px',
                    color: 'rgba(255,255,255,0.35)',
                    letterSpacing: '0.8px',
                    textTransform: 'uppercase',
                  }}
                >
                  {h}
                </span>
              ))}
            </div>
            {jobs.map((job) => (
              <div
                key={job.id}
                onClick={() => setActiveJobId(job.id)}
                style={{
                  display: 'grid',
                  gridTemplateColumns: '1fr 100px 180px 100px',
                  padding: '10px 16px',
                  borderBottom: '1px solid rgba(255,255,255,0.05)',
                  cursor: 'pointer',
                  backgroundColor:
                    job.id === activeJobId ? 'rgba(255,255,255,0.04)' : 'transparent',
                }}
              >
                <span
                  style={{
                    fontFamily: 'var(--font-geist-mono)',
                    fontSize: '11px',
                    color: 'rgba(255,255,255,0.35)',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {job.id.slice(0, 8)}
                </span>
                <span
                  style={{
                    fontFamily: 'var(--font-geist-mono)',
                    fontSize: '11px',
                    color: '#ffffff',
                    textTransform: 'uppercase',
                    letterSpacing: '0.5px',
                  }}
                >
                  {job.step}
                </span>
                <span
                  style={{
                    fontFamily: 'var(--font-inter)',
                    fontSize: '12px',
                    color: 'rgba(255,255,255,0.5)',
                  }}
                >
                  {new Date(job.created_at).toLocaleString()}
                </span>
                <span
                  style={{
                    fontFamily: 'var(--font-geist-mono)',
                    fontSize: '11px',
                    textTransform: 'uppercase',
                    letterSpacing: '0.5px',
                    color: statusColor(job.status),
                  }}
                >
                  {job.status}
                </span>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
