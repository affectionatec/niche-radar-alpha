'use client';

import { PhaseId, PhaseState, PhaseStatus, RunAllStep, StepId } from '@/lib/usePipelineState';

// ---------------------------------------------------------------------------
// Icons
// ---------------------------------------------------------------------------

function CheckIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
      <path d="M3 7l3 3 5-5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function SpinnerIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" style={{ animation: 'spin 1s linear infinite' }}>
      <circle cx="7" cy="7" r="5.5" stroke="rgba(255,255,255,0.15)" strokeWidth="1.5" />
      <path d="M12.5 7a5.5 5.5 0 00-5.5-5.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

function FailIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
      <path d="M4 4l6 6M10 4l-6 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

function SkipIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
      <path d="M4 7h6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Status indicator
// ---------------------------------------------------------------------------

function StatusNode({ status }: { status: PhaseStatus }) {
  const colors: Record<PhaseStatus, { bg: string; border: string; text: string }> = {
    pending: { bg: 'transparent', border: 'rgba(255,255,255,0.15)', text: 'rgba(255,255,255,0.25)' },
    running: { bg: 'rgba(255,255,255,0.08)', border: 'rgba(255,255,255,0.5)', text: '#ffffff' },
    done: { bg: 'rgba(255,255,255,0.12)', border: 'rgba(255,255,255,0.4)', text: '#ffffff' },
    failed: { bg: 'rgba(255,80,80,0.12)', border: 'rgba(255,80,80,0.5)', text: 'rgba(255,80,80,0.9)' },
    skipped: { bg: 'transparent', border: 'rgba(255,255,255,0.1)', text: 'rgba(255,255,255,0.25)' },
  };

  const c = colors[status];
  const icon = status === 'done' ? <CheckIcon /> :
    status === 'running' ? <SpinnerIcon /> :
    status === 'failed' ? <FailIcon /> :
    status === 'skipped' ? <SkipIcon /> : null;

  return (
    <div style={{
      width: '28px',
      height: '28px',
      borderRadius: '50%',
      border: `1.5px solid ${c.border}`,
      background: c.bg,
      color: c.text,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      flexShrink: 0,
    }}>
      {icon}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Connector line between stages
// ---------------------------------------------------------------------------

function Connector({ active }: { active: boolean }) {
  return (
    <div style={{
      flex: 1,
      height: '1.5px',
      background: active ? 'rgba(255,255,255,0.3)' : 'rgba(255,255,255,0.08)',
      minWidth: '24px',
      maxWidth: '80px',
      alignSelf: 'center',
      transition: 'background 0.3s',
    }} />
  );
}

// ---------------------------------------------------------------------------
// Progress bar
// ---------------------------------------------------------------------------

function ProgressBar({ current, total }: { current: number; total: number }) {
  const pct = total > 0 ? Math.round((current / total) * 100) : 0;
  return (
    <div style={{
      width: '100%',
      height: '3px',
      background: 'rgba(255,255,255,0.06)',
      borderRadius: '2px',
      overflow: 'hidden',
      marginTop: '8px',
    }}>
      <div style={{
        width: `${pct}%`,
        height: '100%',
        background: 'rgba(255,255,255,0.35)',
        borderRadius: '2px',
        transition: 'width 0.3s ease',
      }} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Phase card
// ---------------------------------------------------------------------------

function PhaseCard({ phase }: { phase: PhaseState }) {
  const isActive = phase.status === 'running';
  const isDone = phase.status === 'done';
  const isFailed = phase.status === 'failed';

  const statEntries = Object.entries(phase.stats).filter(([k]) =>
    ['passed', 'rejected', 'extractions', 'clusters', 'totalClusters'].includes(k)
  );

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      gap: '6px',
      minWidth: '100px',
      flex: '0 1 140px',
    }}>
      <StatusNode status={phase.status} />
      <span style={{
        fontFamily: 'var(--font-geist-mono)',
        fontSize: '11px',
        letterSpacing: '1px',
        textTransform: 'uppercase',
        color: isActive ? '#ffffff' : isDone ? 'rgba(255,255,255,0.7)' : isFailed ? 'rgba(255,80,80,0.85)' : 'rgba(255,255,255,0.3)',
        textAlign: 'center',
        transition: 'color 0.3s',
      }}>
        {phase.id}: {phase.name}
      </span>
      <span style={{
        fontFamily: 'var(--font-inter)',
        fontSize: '10px',
        color: 'rgba(255,255,255,0.3)',
        textAlign: 'center',
      }}>
        {phase.description}
      </span>

      {phase.progress && (
        <>
          <ProgressBar current={phase.progress.current} total={phase.progress.total} />
          <span style={{
            fontFamily: 'var(--font-geist-mono)',
            fontSize: '10px',
            color: 'rgba(255,255,255,0.4)',
          }}>
            {phase.progress.current}/{phase.progress.total}
          </span>
        </>
      )}

      {statEntries.length > 0 && (
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', justifyContent: 'center' }}>
          {statEntries.map(([k, v]) => (
            <span key={k} style={{
              fontFamily: 'var(--font-geist-mono)',
              fontSize: '9px',
              color: 'rgba(255,255,255,0.35)',
              letterSpacing: '0.3px',
            }}>
              {k}={String(v)}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Run-all step card
// ---------------------------------------------------------------------------

function RunAllStepCard({ step }: { step: RunAllStep }) {
  const isActive = step.status === 'running';
  const isDone = step.status === 'done';
  const isFailed = step.status === 'failed';

  const labels: Record<StepId, string> = {
    collect: 'COLLECT',
    analyze: 'ANALYZE',
    report: 'REPORT',
  };

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      gap: '6px',
      minWidth: '80px',
    }}>
      <StatusNode status={step.status} />
      <span style={{
        fontFamily: 'var(--font-geist-mono)',
        fontSize: '12px',
        letterSpacing: '1px',
        textTransform: 'uppercase',
        color: isActive ? '#ffffff' : isDone ? 'rgba(255,255,255,0.7)' : isFailed ? 'rgba(255,80,80,0.85)' : 'rgba(255,255,255,0.3)',
        transition: 'color 0.3s',
      }}>
        {labels[step.step]}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

interface PipelineStagesProps {
  phases: Record<PhaseId, PhaseState>;
  runAllSteps: RunAllStep[];
  isRunAll: boolean;
  currentRunAllStep: StepId | null;
}

export default function PipelineStages({ phases, runAllSteps, isRunAll, currentRunAllStep }: PipelineStagesProps) {
  const phaseOrder: PhaseId[] = ['A', 'B', 'C', 'D'];
  const showPhases = isRunAll ? currentRunAllStep === 'analyze' || runAllSteps.find(s => s.step === 'analyze')?.status === 'done' : true;

  return (
    <div style={{
      background: 'rgba(255,255,255,0.02)',
      border: '1px solid rgba(255,255,255,0.08)',
      padding: '28px 24px',
    }}>
      {/* Run-all steps row */}
      {isRunAll && (
        <div style={{ marginBottom: showPhases ? '28px' : '0' }}>
          <div style={{
            fontFamily: 'var(--font-geist-mono)',
            fontSize: '10px',
            letterSpacing: '1px',
            color: 'rgba(255,255,255,0.3)',
            marginBottom: '16px',
            textTransform: 'uppercase',
          }}>
            Pipeline Steps
          </div>
          <div style={{
            display: 'flex',
            alignItems: 'flex-start',
            gap: '0',
            justifyContent: 'center',
          }}>
            {runAllSteps.map((step, i) => (
              <div key={step.step} style={{ display: 'flex', alignItems: 'flex-start' }}>
                <RunAllStepCard step={step} />
                {i < runAllSteps.length - 1 && (
                  <Connector active={step.status === 'done' || step.status === 'running'} />
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Analysis phases row */}
      {showPhases && (
        <>
          <div style={{
            fontFamily: 'var(--font-geist-mono)',
            fontSize: '10px',
            letterSpacing: '1px',
            color: 'rgba(255,255,255,0.3)',
            marginBottom: '16px',
            textTransform: 'uppercase',
          }}>
            {isRunAll ? 'Analysis Phases' : 'Pipeline Phases'}
          </div>
          <div style={{
            display: 'flex',
            alignItems: 'flex-start',
            gap: '0',
            justifyContent: 'center',
          }}>
            {phaseOrder.map((id, i) => (
              <div key={id} style={{ display: 'flex', alignItems: 'flex-start' }}>
                <PhaseCard phase={phases[id]} />
                {i < phaseOrder.length - 1 && (
                  <Connector active={phases[id].status === 'done' || phases[id].status === 'running'} />
                )}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
