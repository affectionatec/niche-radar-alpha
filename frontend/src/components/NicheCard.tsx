'use client';
import Link from 'next/link';
import { useState } from 'react';
import { NicheScore } from '@/lib/types';

export default function NicheCard({ niche }: { niche: NicheScore }) {
  const [hovered, setHovered] = useState(false);

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
        }}
      >
        {/* Header */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
            marginBottom: '16px',
            gap: '16px',
          }}
        >
          <span
            style={{
              fontFamily: 'var(--font-geist-mono)',
              fontSize: '14px',
              fontWeight: 400,
              color: '#ffffff',
              textTransform: 'uppercase',
              letterSpacing: '0.8px',
              lineHeight: 1.4,
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

        {/* LLM reasoning */}
        {niche.llm_reasoning && (
          <p
            style={{
              fontFamily: 'var(--font-inter)',
              fontSize: '12px',
              color: 'rgba(255,255,255,0.55)',
              lineHeight: 1.6,
              marginBottom: '16px',
              display: '-webkit-box',
              WebkitLineClamp: 3,
              WebkitBoxOrient: 'vertical',
              overflow: 'hidden',
            }}
          >
            {niche.llm_reasoning}
          </p>
        )}

        {/* Aliases */}
        {niche.aliases.length > 0 && (
          <div
            style={{
              display: 'flex',
              flexWrap: 'wrap',
              gap: '6px',
              marginBottom: '16px',
            }}
          >
            {niche.aliases.slice(0, 4).map((alias) => (
              <span
                key={alias}
                style={{
                  fontFamily: 'var(--font-geist-mono)',
                  fontSize: '10px',
                  color: 'rgba(255, 255, 255, 0.6)',
                  border: '1px solid rgba(255, 255, 255, 0.15)',
                  padding: '3px 8px',
                  textTransform: 'uppercase',
                  letterSpacing: '0.4px',
                }}
              >
                {alias}
              </span>
            ))}
          </div>
        )}

        {/* Footer */}
        <div
          style={{
            display: 'flex',
            gap: '16px',
            fontFamily: 'var(--font-inter)',
            fontSize: '11px',
            color: 'rgba(255, 255, 255, 0.3)',
            textTransform: 'uppercase',
            letterSpacing: '0.4px',
          }}
        >
          <span>×{niche.occurrence_count}</span>
          <span>{new Date(niche.first_seen).toLocaleDateString()}</span>
        </div>
      </div>
    </Link>
  );
}
