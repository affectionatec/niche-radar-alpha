'use client';

import { PipelineSummary } from '@/lib/usePipelineState';
import { color, font, fontSize } from '@/lib/tokens';

interface PipelineSummaryPanelProps {
  summary: PipelineSummary;
  clusterResults: { clusterId: string; verdict: string; score: string; tier: string; niche: string }[];
}

function verdictColor(verdict: string): string {
  if (verdict === 'GO') return color.success;
  if (verdict === 'NO_GO') return color.error;
  if (verdict === 'MAYBE') return color.warning;
  return color.fgDisabled;
}

function tierColor(tier: string): string {
  if (tier === 'high_priority') return color.success;
  if (tier === 'watchlist') return color.warning;
  return color.fgGhost;
}

export default function PipelineSummaryPanel({ summary, clusterResults }: PipelineSummaryPanelProps) {
  const stats = [
    { label: 'ITEMS', value: summary.items },
    { label: 'PASSED', value: summary.passed },
    { label: 'CLUSTERS', value: summary.clusters },
    { label: 'PERSISTED', value: summary.persisted },
    { label: 'LLM CALLS', value: summary.budgetUsed },
  ];

  return (
    <div
      role="region"
      aria-label="Pipeline results summary"
      style={{ background: color.surface, border: `1px solid ${color.border}`, padding: '20px 24px' }}
    >
      <div style={{ fontFamily: font.mono, fontSize: fontSize.sm, letterSpacing: '1px', color: color.success, textTransform: 'uppercase', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
          <path d="M3 7l3 3 5-5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        Pipeline Complete
      </div>

      {/* Stats row */}
      <div style={{ display: 'flex', gap: '32px', flexWrap: 'wrap', marginBottom: clusterResults.length > 0 ? '20px' : '0' }}>
        {stats.map(({ label, value }) => (
          <div key={label} style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <span style={{ fontFamily: font.mono, fontSize: fontSize.xs, letterSpacing: '0.8px', color: color.fgGhost, textTransform: 'uppercase' }}>
              {label}
            </span>
            <span style={{ fontFamily: font.mono, fontSize: fontSize['3xl'], fontWeight: 300, color: color.fg }}>
              {value}
            </span>
          </div>
        ))}
      </div>

      {/* Cluster results */}
      {clusterResults.length > 0 && (
        <>
          <div style={{ fontFamily: font.mono, fontSize: fontSize.sm, letterSpacing: '1px', color: color.fgGhost, textTransform: 'uppercase', marginBottom: '10px' }}>
            Discovered Niches
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            {clusterResults.map((cr, i) => (
              <div key={i} style={{
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
                padding: '6px 0',
                borderBottom: i < clusterResults.length - 1 ? '1px solid rgba(255,255,255,0.04)' : 'none',
                flexWrap: 'wrap',
              }}>
                <span style={{ fontFamily: font.mono, fontSize: fontSize.base, fontWeight: 500, color: verdictColor(cr.verdict), width: '52px', flexShrink: 0 }}>
                  {cr.verdict}
                </span>
                <span style={{ fontFamily: font.body, fontSize: fontSize.md, color: color.fg, flex: 1, minWidth: '120px' }}>
                  {cr.niche}
                </span>
                <span style={{ fontFamily: font.mono, fontSize: fontSize.sm, color: color.fgDisabled }}>
                  {cr.score}
                </span>
                <span style={{ fontFamily: font.mono, fontSize: fontSize.xs, letterSpacing: '0.5px', color: tierColor(cr.tier), textTransform: 'uppercase' }}>
                  {cr.tier.replace('_', ' ')}
                </span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
