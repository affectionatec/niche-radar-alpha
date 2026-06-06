'use client';
import Link from 'next/link';
import useSWR from 'swr';
import { endpoints, fetcher } from '@/lib/api';
import { Entity } from '@/lib/types';
import { color, font } from '@/lib/tokens';

const TYPE_COLORS: Record<string, string> = {
  company: 'rgba(125,211,252,0.9)',
  product: 'rgba(74,222,128,0.85)',
  technology: 'rgba(251,191,36,0.85)',
  person: 'rgba(192,132,252,0.85)',
  category: 'rgba(255,255,255,0.5)',
};

export default function TrendingEntitiesPage() {
  const { data, error, isLoading } = useSWR<Entity[]>(
    `${endpoints.entitiesTrending}?limit=20`,
    fetcher,
    { refreshInterval: 60_000 },
  );

  if (error) return (
    <div style={{ padding: '96px 0', textAlign: 'center' }}>
      <p style={{ fontFamily: font.mono, fontSize: '12px', color: color.fgGhost, letterSpacing: '0.8px', textTransform: 'uppercase' }}>
        CANNOT CONNECT TO API
      </p>
    </div>
  );

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '24px' }}>
        <h1 style={{ fontFamily: font.body, fontSize: '30px', fontWeight: 400, color: color.fg }}>
          TRENDING ENTITIES
        </h1>
        <Link href="/entities" style={{
          fontFamily: font.mono, fontSize: '10px', letterSpacing: '0.8px',
          color: color.fgMuted, textDecoration: 'none',
          border: `1px solid ${color.borderStrong}`, padding: '8px 14px', textTransform: 'uppercase',
        }}>
          ALL ENTITIES
        </Link>
      </div>

      {isLoading ? (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '16px' }}>
          {[0, 1, 2, 3].map(i => (
            <div key={i} style={{ height: '120px', backgroundColor: color.surface, border: `1px solid ${color.border}` }} />
          ))}
        </div>
      ) : !data || data.length === 0 ? (
        <div style={{ border: `1px solid ${color.surfaceActive}`, padding: '48px', textAlign: 'center' }}>
          <span style={{ fontFamily: font.body, fontSize: '13px', color: color.fgGhost }}>
            No trending entities yet. Entity velocity is computed weekly.
          </span>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '16px' }}>
          {data.map((e, idx) => (
            <Link
              key={e.id}
              href={`/entities/${e.id}`}
              style={{
                border: `1px solid ${color.border}`,
                padding: '20px',
                textDecoration: 'none',
                display: 'flex', flexDirection: 'column', gap: '12px',
                backgroundColor: idx < 3 ? color.surfaceHover : 'transparent',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                  <div style={{ fontFamily: font.body, fontSize: '15px', color: color.fg, marginBottom: '4px' }}>
                    {e.canonical_name}
                  </div>
                  <span style={{
                    fontFamily: font.mono, fontSize: '9px', letterSpacing: '0.5px',
                    color: TYPE_COLORS[e.type] || color.fgDisabled,
                    border: `1px solid ${TYPE_COLORS[e.type] || color.borderStrong}`,
                    padding: '2px 6px', textTransform: 'uppercase',
                  }}>
                    {e.type}
                  </span>
                </div>
                <span style={{ fontFamily: font.mono, fontSize: '20px', color: color.success, fontWeight: 600 }}>
                  {e.velocity_score > 0 ? e.velocity_score.toFixed(1) : '—'}
                </span>
              </div>
              <div style={{ display: 'flex', gap: '24px' }}>
                <div>
                  <div style={{ fontFamily: font.body, fontSize: '10px', color: color.fgDisabled, letterSpacing: '0.8px', textTransform: 'uppercase', marginBottom: '2px' }}>MENTIONS</div>
                  <span style={{ fontFamily: font.mono, fontSize: '14px', color: color.fgSecondary }}>{e.mention_count}</span>
                </div>
                <div>
                  <div style={{ fontFamily: font.body, fontSize: '10px', color: color.fgDisabled, letterSpacing: '0.8px', textTransform: 'uppercase', marginBottom: '2px' }}>SOURCES</div>
                  <span style={{ fontFamily: font.mono, fontSize: '14px', color: color.fgSecondary }}>{e.source_diversity}</span>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
