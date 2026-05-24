'use client';
import { useState } from 'react';
import { A6Detail } from '@/lib/types';
import { color, font } from '@/lib/tokens';

const VERDICT_COLOR: Record<string, string> = {
  GO: color.success,
  'NO-GO': color.error,
  PIVOT: color.warning,
};

interface Props {
  a6: A6Detail;
  feasibilityScore: number | null;
  opportunityScore: number | null;
  confidence: number | null;
}

export default function VerdictChain({ a6, feasibilityScore, opportunityScore, confidence }: Props) {
  const [expanded, setExpanded] = useState(false);
  const verdictColor = VERDICT_COLOR[a6.verdict || ''] || color.fgMuted;

  return (
    <div style={{ border: `1px solid ${verdictColor}33`, background: color.surface }}>
      {/* Header — always visible */}
      <button
        onClick={() => setExpanded(!expanded)}
        style={{
          width: '100%', display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          padding: '16px 20px', background: 'transparent', border: 'none', cursor: 'pointer',
          color: verdictColor,
        }}
      >
        <span style={{ fontFamily: font.mono, fontSize: '10px', letterSpacing: '0.8px', textTransform: 'uppercase' as const }}>
          {expanded ? '▾' : '▸'} WHY THIS VERDICT?
        </span>
        <span style={{ fontFamily: font.mono, fontSize: '10px', letterSpacing: '0.5px' }}>
          {a6.verdict} · {((confidence ?? a6.confidence ?? 0) * 100).toFixed(0)}% confidence
        </span>
      </button>

      {/* Expanded chain */}
      {expanded && (
        <div style={{ padding: '0 20px 20px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {/* A4 Score summary */}
          <ChainStep
            agent="A4"
            label="Opportunity Scorer"
            color={color.fgMuted}
            content={`${opportunityScore ?? '?'}/70 raw score → ${a6.one_line_rationale ? '' : 'Score feeds into verdict decision'}`}
          />

          {/* A5 Feasibility */}
          <ChainStep
            agent="A5"
            label="Feasibility Analyst"
            color={color.fgMuted}
            content={`Feasibility: ${feasibilityScore ?? '?'}/10`}
          />

          {/* A6 Verdict */}
          <ChainStep
            agent="A6"
            label="Go/No-Go Judge"
            color={verdictColor}
            content={a6.one_line_rationale || a6.full_rationale || 'No rationale available'}
          />

          {/* Killer risk */}
          {a6.killer_risk && (
            <div style={{
              marginLeft: '32px', padding: '10px 14px',
              borderLeft: `2px solid ${color.errorMuted}`,
              fontFamily: font.body, fontSize: '12px',
              color: color.error, lineHeight: 1.5,
            }}>
              <strong style={{ fontFamily: font.mono, fontSize: '10px', letterSpacing: '0.5px' }}>KILLER RISK: </strong>
              {a6.killer_risk}
            </div>
          )}

          {/* Pivot suggestion */}
          {a6.pivot_suggestion && (
            <div style={{
              marginLeft: '32px', padding: '10px 14px',
              borderLeft: `2px solid ${color.warningMuted}`,
              fontFamily: font.body, fontSize: '12px',
              color: color.warning, lineHeight: 1.5,
            }}>
              <strong style={{ fontFamily: font.mono, fontSize: '10px', letterSpacing: '0.5px' }}>PIVOT: </strong>
              {a6.pivot_suggestion}
            </div>
          )}

          {/* Conditions to reconsider */}
          {a6.conditions_to_reconsider && (
            <div style={{
              marginLeft: '32px', padding: '10px 14px',
              borderLeft: `2px solid ${color.borderStrong}`,
              fontFamily: font.body, fontSize: '12px',
              color: color.fgMuted, lineHeight: 1.5,
            }}>
              <strong style={{ fontFamily: font.mono, fontSize: '10px', letterSpacing: '0.5px' }}>WOULD RECONSIDER IF: </strong>
              {a6.conditions_to_reconsider}
            </div>
          )}

          {/* Recommended next step */}
          {a6.recommended_next_step && (
            <div style={{
              marginLeft: '32px', padding: '10px 14px',
              borderLeft: `2px solid ${color.successMuted}`,
              fontFamily: font.body, fontSize: '12px',
              color: color.successMuted, lineHeight: 1.5,
            }}>
              <strong style={{ fontFamily: font.mono, fontSize: '10px', letterSpacing: '0.5px' }}>NEXT STEP: </strong>
              {a6.recommended_next_step}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ChainStep({ agent, label, color: tone, content }: {
  agent: string; label: string; color: string; content: string;
}) {
  return (
    <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-start' }}>
      <div style={{
        fontFamily: font.mono, fontSize: '10px', color: tone,
        minWidth: '20px', letterSpacing: '0.5px', paddingTop: '2px',
      }}>
        {agent}
      </div>
      <div>
        <div style={{
          fontFamily: font.mono, fontSize: '10px',
          color: color.fgDisabled, letterSpacing: '0.5px', marginBottom: '2px',
        }}>
          {label}
        </div>
        <div style={{
          fontFamily: font.body, fontSize: '12.5px',
          color: color.fgSecondary, lineHeight: 1.5,
        }}>
          {content}
        </div>
      </div>
    </div>
  );
}
