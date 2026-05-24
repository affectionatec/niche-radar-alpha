'use client';
import Link from 'next/link';
import { useState } from 'react';
import { NicheScore } from '@/lib/types';
import { color, font } from '@/lib/tokens';

const COMPLEXITY_LABEL: Record<number, string> = {
  1: 'WEEKEND',
  2: '2-3 DAYS',
  3: '~1 WEEK',
  4: '1-2 WKS',
  5: '2+ WKS',
};

function complexityColor(c: number | null): string {
  if (c === null) return color.fgGhost;
  if (c <= 2) return color.success;
  if (c === 3) return color.warning;
  return color.error;
}

export default function NicheCard({ niche }: { niche: NicheScore }) {
  const [hovered, setHovered] = useState(false);
  const concept = niche.tool_concept || niche.keyword;
  const complexityLabel = niche.build_complexity ? COMPLEXITY_LABEL[niche.build_complexity] : 'UNKNOWN';

  return (
    <Link href={`/niches/${niche.niche_id}`} style={{ textDecoration: 'none', display: 'block' }}>
      <div
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        style={{
          backgroundColor: color.surface,
          border: `1px solid ${hovered ? color.borderStrong : color.border}`,
          padding: '24px',
          cursor: 'pointer',
          transition: 'border-color 0.15s ease',
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        {/* Header: keyword slug + score */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
            marginBottom: '12px',
            gap: '16px',
          }}
        >
          <span
            style={{
              fontFamily: font.mono,
              fontSize: '11px',
              color: color.fgMuted,
              textTransform: 'uppercase' as const,
              letterSpacing: '1px',
              lineHeight: 1.3,
            }}
          >
            {niche.keyword}
          </span>
          <span
            style={{
              fontFamily: font.mono,
              fontSize: '28px',
              fontWeight: 300,
              color: color.fg,
              lineHeight: 1,
              flexShrink: 0,
            }}
          >
            {niche.llm_score.toFixed(0)}
          </span>
        </div>

        {/* Tool concept (the headline) */}
        <p
          style={{
            fontFamily: font.body,
            fontSize: '15px',
            color: color.fg,
            lineHeight: 1.4,
            marginBottom: '14px',
            display: '-webkit-box',
            WebkitLineClamp: 2,
            WebkitBoxOrient: 'vertical',
            overflow: 'hidden',
          }}
        >
          {concept}
        </p>

        {/* Badges row: complexity + audience */}
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '12px' }}>
          <span
            style={{
              fontFamily: font.mono,
              fontSize: '10px',
              color: complexityColor(niche.build_complexity),
              border: `1px solid ${complexityColor(niche.build_complexity)}`,
              padding: '3px 8px',
              letterSpacing: '0.5px',
            }}
          >
            ⏱ {complexityLabel}
          </span>
          {niche.target_audience && (
            <span
              style={{
                fontFamily: font.mono,
                fontSize: '10px',
                color: color.fgMuted,
                border: `1px solid ${color.borderStrong}`,
                padding: '3px 8px',
                letterSpacing: '0.4px',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
                maxWidth: '160px',
              }}
            >
              👥 {niche.target_audience}
            </span>
          )}
        </div>

        {/* Reasoning (demand evidence) — flex-grow so footer pins to bottom */}
        {niche.llm_reasoning && (
          <p
            style={{
              fontFamily: font.body,
              fontSize: '12px',
              color: color.fgMuted,
              lineHeight: 1.55,
              marginBottom: '14px',
              display: '-webkit-box',
              WebkitLineClamp: 2,
              WebkitBoxOrient: 'vertical',
              overflow: 'hidden',
              flexGrow: 1,
            }}
          >
            {niche.llm_reasoning}
          </p>
        )}

        {/* Footer: monetization + mentions */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            gap: '12px',
            fontFamily: font.body,
            fontSize: '11px',
            color: color.fgDisabled,
            letterSpacing: '0.3px',
            marginTop: 'auto',
            paddingTop: '8px',
            borderTop: `1px solid ${color.surfaceHover}`,
          }}
        >
          <span
            style={{
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
              flex: 1,
            }}
            title={niche.monetization}
          >
            💰 {niche.monetization || 'no angle specified'}
          </span>
          <span style={{ flexShrink: 0 }}>×{niche.occurrence_count}</span>
        </div>
      </div>
    </Link>
  );
}
