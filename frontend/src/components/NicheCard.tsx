'use client';
import Link from 'next/link';
import { useState } from 'react';
import { NicheScore } from '@/lib/types';

const COMPLEXITY_LABEL: Record<number, string> = {
  1: 'WEEKEND',
  2: '2-3 DAYS',
  3: '~1 WEEK',
  4: '1-2 WKS',
  5: '2+ WKS',
};

function complexityColor(c: number | null): string {
  if (c === null) return 'rgba(255,255,255,0.3)';
  if (c <= 2) return 'rgba(74,222,128,0.85)';
  if (c === 3) return 'rgba(251,191,36,0.85)';
  return 'rgba(255,140,140,0.85)';
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
          backgroundColor: 'rgba(255, 255, 255, 0.03)',
          border: `1px solid ${hovered ? 'rgba(255,255,255,0.2)' : 'rgba(255,255,255,0.1)'}`,
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
              fontFamily: 'var(--font-geist-mono)',
              fontSize: '11px',
              color: 'rgba(255,255,255,0.45)',
              textTransform: 'uppercase',
              letterSpacing: '1px',
              lineHeight: 1.3,
            }}
          >
            {niche.keyword}
          </span>
          <span
            style={{
              fontFamily: 'var(--font-geist-mono)',
              fontSize: '28px',
              fontWeight: 300,
              color: '#ffffff',
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
            fontFamily: 'var(--font-inter)',
            fontSize: '15px',
            color: '#ffffff',
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
              fontFamily: 'var(--font-geist-mono)',
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
                fontFamily: 'var(--font-geist-mono)',
                fontSize: '10px',
                color: 'rgba(255,255,255,0.55)',
                border: '1px solid rgba(255,255,255,0.15)',
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
              fontFamily: 'var(--font-inter)',
              fontSize: '12px',
              color: 'rgba(255,255,255,0.5)',
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
            fontFamily: 'var(--font-inter)',
            fontSize: '11px',
            color: 'rgba(255, 255, 255, 0.35)',
            letterSpacing: '0.3px',
            marginTop: 'auto',
            paddingTop: '8px',
            borderTop: '1px solid rgba(255,255,255,0.06)',
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
