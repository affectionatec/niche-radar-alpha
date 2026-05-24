'use client';
import { SCORING_DIMENSIONS } from '@/lib/tokens';
import { A4Scores } from '@/lib/types';

function barColor(score: number): string {
  if (score >= 8) return 'rgba(74,222,128,0.85)';
  if (score >= 5) return 'rgba(251,191,36,0.85)';
  return 'rgba(255,80,80,0.85)';
}

export default function ScoreBreakdown({ scores }: { scores: A4Scores }) {
  // Find lowest-scoring dimension for callout
  let lowest = { key: '', score: 11, label: '' };
  SCORING_DIMENSIONS.forEach(dim => {
    const s = (scores[dim.key as keyof A4Scores] as { score: number | null } | null)?.score ?? 0;
    if (s < lowest.score) lowest = { key: dim.key, score: s, label: dim.label };
  });

  return (
    <div>
      <div style={{
        fontFamily: 'var(--font-inter)', fontSize: '11px', color: 'rgba(255,255,255,0.4)',
        textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '14px',
      }}>
        SCORE BREAKDOWN
      </div>
      <div style={{
        display: 'grid', gridTemplateColumns: '140px 1fr 32px',
        gap: '8px 12px', alignItems: 'center',
      }}>
        {SCORING_DIMENSIONS.map(dim => {
          const entry = scores[dim.key as keyof A4Scores] as { score: number | null; rationale: string | null } | null;
          const value = entry?.score ?? 0;
          return (
            <div key={dim.key} style={{ display: 'contents' }}>
              <div
                style={{
                  fontFamily: 'var(--font-geist-mono)', fontSize: '10px',
                  color: 'rgba(255,255,255,0.55)', textTransform: 'uppercase',
                  letterSpacing: '0.5px', whiteSpace: 'nowrap',
                }}
                title={entry?.rationale || dim.description}
              >
                {dim.label}
              </div>
              <div style={{
                height: '6px', background: 'rgba(255,255,255,0.06)',
                position: 'relative', overflow: 'hidden',
              }}>
                <div style={{
                  position: 'absolute', top: 0, left: 0, height: '100%',
                  width: `${(value / 10) * 100}%`, background: barColor(value),
                  transition: 'width 0.4s ease',
                }} />
              </div>
              <div style={{
                fontFamily: 'var(--font-geist-mono)', fontSize: '12px',
                color: barColor(value), textAlign: 'right',
              }}>
                {value}
              </div>
            </div>
          );
        })}
      </div>
      {lowest.score <= 4 && (
        <div style={{
          marginTop: '12px', fontFamily: 'var(--font-geist-mono)', fontSize: '10px',
          color: 'rgba(255,80,80,0.7)', letterSpacing: '0.5px',
        }}>
          ⚠ {lowest.label.toUpperCase()} IS DRAGGING THE SCORE ({lowest.score}/10)
        </div>
      )}
    </div>
  );
}
