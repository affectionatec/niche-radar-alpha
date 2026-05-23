'use client';

import { PipelineSummary } from '@/lib/usePipelineState';

interface PipelineSummaryPanelProps {
  summary: PipelineSummary;
  clusterResults: { clusterId: string; verdict: string; score: string; tier: string; niche: string }[];
}

function verdictColor(verdict: string): string {
  if (verdict === 'GO') return 'rgba(74,222,128,0.8)';
  if (verdict === 'NO_GO') return 'rgba(255,80,80,0.7)';
  if (verdict === 'MAYBE') return 'rgba(251,191,36,0.8)';
  return 'rgba(255,255,255,0.4)';
}

function tierColor(tier: string): string {
  if (tier === 'high_priority') return 'rgba(74,222,128,0.7)';
  if (tier === 'watchlist') return 'rgba(251,191,36,0.7)';
  return 'rgba(255,255,255,0.3)';
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
    <div style={{
      background: 'rgba(255,255,255,0.02)',
      border: '1px solid rgba(255,255,255,0.08)',
      padding: '20px 24px',
    }}>
      <div style={{
        fontFamily: 'var(--font-geist-mono)',
        fontSize: '10px',
        letterSpacing: '1px',
        color: 'rgba(255,255,255,0.3)',
        textTransform: 'uppercase',
        marginBottom: '16px',
      }}>
        Pipeline Complete
      </div>

      {/* Stats row */}
      <div style={{
        display: 'flex',
        gap: '32px',
        flexWrap: 'wrap',
        marginBottom: clusterResults.length > 0 ? '20px' : '0',
      }}>
        {stats.map(({ label, value }) => (
          <div key={label} style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <span style={{
              fontFamily: 'var(--font-geist-mono)',
              fontSize: '9px',
              letterSpacing: '0.8px',
              color: 'rgba(255,255,255,0.3)',
              textTransform: 'uppercase',
            }}>
              {label}
            </span>
            <span style={{
              fontFamily: 'var(--font-geist-mono)',
              fontSize: '20px',
              fontWeight: 300,
              color: '#ffffff',
            }}>
              {value}
            </span>
          </div>
        ))}
      </div>

      {/* Cluster results */}
      {clusterResults.length > 0 && (
        <>
          <div style={{
            fontFamily: 'var(--font-geist-mono)',
            fontSize: '10px',
            letterSpacing: '1px',
            color: 'rgba(255,255,255,0.3)',
            textTransform: 'uppercase',
            marginBottom: '10px',
          }}>
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
              }}>
                <span style={{
                  fontFamily: 'var(--font-geist-mono)',
                  fontSize: '11px',
                  fontWeight: 500,
                  color: verdictColor(cr.verdict),
                  width: '52px',
                  flexShrink: 0,
                }}>
                  {cr.verdict}
                </span>
                <span style={{
                  fontFamily: 'var(--font-inter)',
                  fontSize: '12px',
                  color: '#ffffff',
                  flex: 1,
                }}>
                  {cr.niche}
                </span>
                <span style={{
                  fontFamily: 'var(--font-geist-mono)',
                  fontSize: '10px',
                  color: 'rgba(255,255,255,0.4)',
                }}>
                  {cr.score}
                </span>
                <span style={{
                  fontFamily: 'var(--font-geist-mono)',
                  fontSize: '9px',
                  letterSpacing: '0.5px',
                  color: tierColor(cr.tier),
                  textTransform: 'uppercase',
                }}>
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
