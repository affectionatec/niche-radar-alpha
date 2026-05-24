'use client';
import { color, font, SCORING_DIMENSIONS } from '@/lib/tokens';
import { A4Scores } from '@/lib/types';

function barColor(score: number): string {
  if (score >= 8) return color.success;
  if (score >= 5) return color.warning;
  return color.error;
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
        fontFamily: font.body, fontSize: '11px', color: color.fgMuted,
        textTransform: 'uppercase' as const, letterSpacing: '1px', marginBottom: '14px',
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
                  fontFamily: font.mono, fontSize: '10px',
                  color: color.fgMuted, textTransform: 'uppercase' as const,
                  letterSpacing: '0.5px', whiteSpace: 'nowrap',
                }}
                title={entry?.rationale || dim.description}
              >
                {dim.label}
              </div>
              <div style={{
                height: '6px', background: color.surfaceHover,
                position: 'relative', overflow: 'hidden',
              }}>
                <div style={{
                  position: 'absolute', top: 0, left: 0, height: '100%',
                  width: `${(value / 10) * 100}%`, background: barColor(value),
                  transition: 'width 0.4s ease',
                }} />
              </div>
              <div style={{
                fontFamily: font.mono, fontSize: '12px',
                color: barColor(value), textAlign: 'right' as const,
              }}>
                {value}
              </div>
            </div>
          );
        })}
      </div>
      {lowest.score <= 4 && (
        <div style={{
          marginTop: '12px', fontFamily: font.mono, fontSize: '10px',
          color: color.errorMuted, letterSpacing: '0.5px',
        }}>
          ⚠ {lowest.label.toUpperCase()} IS DRAGGING THE SCORE ({lowest.score}/10)
        </div>
      )}
    </div>
  );
}
