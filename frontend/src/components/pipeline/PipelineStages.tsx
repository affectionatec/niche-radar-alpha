'use client';

import { PhaseId, PhaseState, PhaseStatus, RunAllStep, StepId } from '@/lib/usePipelineState';
import { color, font, fontSize } from '@/lib/tokens';

// ---------------------------------------------------------------------------
// Icons
// ---------------------------------------------------------------------------

function CheckIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
      <path d="M3 7l3 3 5-5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function SpinnerIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" style={{ animation: 'spin 1s linear infinite' }} aria-hidden="true">
      <circle cx="7" cy="7" r="5.5" stroke="rgba(255,255,255,0.15)" strokeWidth="1.5" />
      <path d="M12.5 7a5.5 5.5 0 00-5.5-5.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

function FailIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
      <path d="M4 4l6 6M10 4l-6 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

function SkipIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
      <path d="M4 7h6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Status indicator
// ---------------------------------------------------------------------------

const STATUS_COLORS: Record<PhaseStatus, { bg: string; border: string; text: string }> = {
  pending: { bg: 'transparent', border: color.fgGhost, text: color.fgGhost },
  running: { bg: color.surfaceActive, border: color.borderFocus, text: color.fg },
  done: { bg: color.surfaceSelected, border: color.fgMuted, text: color.fg },
  failed: { bg: 'rgba(255,80,80,0.12)', border: color.errorMuted, text: color.error },
  skipped: { bg: 'transparent', border: color.border, text: color.fgGhost },
};

const STATUS_LABEL: Record<PhaseStatus, string> = {
  pending: 'Pending',
  running: 'Running',
  done: 'Complete',
  failed: 'Failed',
  skipped: 'Skipped',
};

function StatusNode({ status }: { status: PhaseStatus }) {
  const c = STATUS_COLORS[status];
  const icon = status === 'done' ? <CheckIcon /> :
    status === 'running' ? <SpinnerIcon /> :
    status === 'failed' ? <FailIcon /> :
    status === 'skipped' ? <SkipIcon /> : null;

  return (
    <div
      role="status"
      aria-label={STATUS_LABEL[status]}
      style={{
        width: '32px',
        height: '32px',
        borderRadius: '50%',
        border: `1.5px solid ${c.border}`,
        background: c.bg,
        color: c.text,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0,
        animation: status === 'running' ? 'pulse-border 2s ease-in-out infinite' : 'none',
      }}
    >
      {icon}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Connector line between stages
// ---------------------------------------------------------------------------

function Connector({ active }: { active: boolean }) {
  return (
    <div
      aria-hidden="true"
      style={{
        width: '24px',
        height: '1.5px',
        background: active ? 'rgba(255,255,255,0.3)' : 'rgba(255,255,255,0.08)',
        // 12px card padding + 16px (half of 32px status circle) = 28px
        marginTop: '28px',
        flexShrink: 0,
        transition: 'background 0.3s',
      }}
    />
  );
}

// ---------------------------------------------------------------------------
// Progress bar
// ---------------------------------------------------------------------------

function ProgressBar({ current, total }: { current: number; total: number }) {
  const pct = total > 0 ? Math.round((current / total) * 100) : 0;
  return (
    <div
      role="progressbar"
      aria-valuenow={current}
      aria-valuemin={0}
      aria-valuemax={total}
      aria-label={`${current} of ${total} complete`}
      style={{
        width: '100%',
        height: '3px',
        background: 'rgba(255,255,255,0.06)',
        overflow: 'hidden',
        marginTop: '8px',
      }}
    >
      <div style={{
        width: `${pct}%`,
        height: '100%',
        background: pct === 100 ? color.success : 'rgba(255,255,255,0.4)',
        transition: 'width 0.3s ease',
      }} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Phase card (analysis phases A-D)
// ---------------------------------------------------------------------------

const STAT_LABELS: Record<string, string> = {
  passed: 'Passed',
  rejected: 'Rejected',
  extractions: 'Extracted',
  clusters: 'Clusters',
  totalClusters: 'Total',
};

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
      width: '140px',
      padding: '12px 8px',
      background: isActive ? 'rgba(255,255,255,0.03)' : 'transparent',
      border: isActive ? '1px solid rgba(255,255,255,0.1)' : '1px solid transparent',
      transition: 'background 0.3s, border-color 0.3s',
    }}>
      <StatusNode status={phase.status} />

      <span style={{
        fontFamily: font.mono,
        fontSize: fontSize.base,
        letterSpacing: '1px',
        textTransform: 'uppercase',
        color: isActive ? color.fg : isDone ? color.fgSecondary : isFailed ? color.error : color.fgGhost,
        textAlign: 'center',
        transition: 'color 0.3s',
        fontWeight: isActive ? 600 : 400,
      }}>
        {phase.id}: {phase.name}
      </span>

      <span style={{
        fontFamily: font.body,
        fontSize: fontSize.sm,
        color: color.fgGhost,
        textAlign: 'center',
        lineHeight: 1.3,
      }}>
        {phase.description}
      </span>

      {phase.progress && (
        <>
          <ProgressBar current={phase.progress.current} total={phase.progress.total} />
          <span style={{
            fontFamily: font.mono,
            fontSize: fontSize.sm,
            color: color.fgDisabled,
          }}>
            {phase.progress.current}/{phase.progress.total}
          </span>
        </>
      )}

      {statEntries.length > 0 && (
        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', justifyContent: 'center', marginTop: '2px' }}>
          {statEntries.map(([k, v]) => (
            <span key={k} style={{
              fontFamily: font.mono,
              fontSize: fontSize.xs,
              color: k === 'passed' ? color.successMuted : k === 'rejected' ? color.errorMuted : color.fgDisabled,
              background: 'rgba(255,255,255,0.04)',
              padding: '1px 6px',
              letterSpacing: '0.3px',
            }}>
              {STAT_LABELS[k] || k}: {String(v)}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Run-all step card (COLLECT → ANALYZE → REPORT)
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

  const descriptions: Record<StepId, string> = {
    collect: 'Gather data from sources',
    analyze: 'LLM pipeline analysis',
    report: 'Generate markdown report',
  };

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      gap: '6px',
      width: '140px',
      padding: '12px 8px',
      background: isActive ? 'rgba(255,255,255,0.03)' : 'transparent',
      border: isActive ? '1px solid rgba(255,255,255,0.1)' : '1px solid transparent',
      transition: 'background 0.3s, border-color 0.3s',
    }}>
      <StatusNode status={step.status} />
      <span style={{
        fontFamily: font.mono,
        fontSize: fontSize.md,
        letterSpacing: '1px',
        textTransform: 'uppercase',
        color: isActive ? color.fg : isDone ? color.fgSecondary : isFailed ? color.error : color.fgGhost,
        transition: 'color 0.3s',
        fontWeight: isActive ? 600 : 400,
      }}>
        {labels[step.step]}
      </span>
      <span style={{
        fontFamily: font.body,
        fontSize: fontSize.sm,
        color: color.fgGhost,
        textAlign: 'center',
      }}>
        {descriptions[step.step]}
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
    <div
      role="region"
      aria-label="Pipeline progress"
      style={{
        background: color.surface,
        border: `1px solid ${color.border}`,
        padding: '28px 24px',
      }}
    >
      {/* Run-all steps row */}
      {isRunAll && (
        <div style={{ marginBottom: showPhases ? '28px' : '0' }}>
          <div style={{
            fontFamily: font.mono,
            fontSize: fontSize.sm,
            letterSpacing: '1px',
            color: color.fgGhost,
            marginBottom: '16px',
            textTransform: 'uppercase',
          }}>
            Pipeline Steps
          </div>
          <div style={{
            display: 'flex',
            alignItems: 'flex-start',
            justifyContent: 'center',
            flexWrap: 'wrap',
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
          {isRunAll && (
            <div style={{
              height: '1px',
              background: color.border,
              margin: '0 0 24px 0',
            }} />
          )}
          <div style={{
            fontFamily: font.mono,
            fontSize: fontSize.sm,
            letterSpacing: '1px',
            color: color.fgGhost,
            marginBottom: '16px',
            textTransform: 'uppercase',
          }}>
            {isRunAll ? 'Analysis Phases' : 'Pipeline Phases'}
          </div>
          <div style={{
            display: 'flex',
            alignItems: 'flex-start',
            justifyContent: 'center',
            flexWrap: 'wrap',
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
