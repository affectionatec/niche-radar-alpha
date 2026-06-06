'use client';
import { useState } from 'react';
import Link from 'next/link';
import useSWR from 'swr';
import { endpoints, fetcher } from '@/lib/api';
import { EntityListResponse } from '@/lib/types';
import { color, font } from '@/lib/tokens';

const TYPE_COLORS: Record<string, string> = {
  company: 'rgba(125,211,252,0.9)',
  product: 'rgba(74,222,128,0.85)',
  technology: 'rgba(251,191,36,0.85)',
  person: 'rgba(192,132,252,0.85)',
  category: 'rgba(255,255,255,0.5)',
};

const ENTITY_TYPES = ['', 'company', 'product', 'technology', 'person', 'category'];

type SortKey = 'last_seen' | 'mention_count' | 'velocity_score' | 'canonical_name';

export default function EntitiesPage() {
  const [typeFilter, setTypeFilter] = useState('');
  const [sort, setSort] = useState<SortKey>('last_seen');
  const [search, setSearch] = useState('');

  const url = `${endpoints.entities}?sort=${sort}&limit=100${typeFilter ? `&type=${typeFilter}` : ''}`;
  const { data, error, isLoading } = useSWR<EntityListResponse>(url, fetcher, { refreshInterval: 60_000 });

  const entities = (data?.items ?? []).filter(e => {
    if (!search) return true;
    const s = search.toLowerCase();
    return e.canonical_name.toLowerCase().includes(s) ||
      (e.aliases || []).some(a => a.toLowerCase().includes(s));
  });

  if (error) return (
    <div style={{ padding: '96px 0', textAlign: 'center' }}>
      <p style={{ fontFamily: font.mono, fontSize: '12px', color: color.fgGhost, letterSpacing: '0.8px', textTransform: 'uppercase' }}>
        CANNOT CONNECT TO API
      </p>
    </div>
  );

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '24px', gap: '24px', flexWrap: 'wrap' }}>
        <h1 style={{ fontFamily: font.body, fontSize: '30px', fontWeight: 400, color: color.fg }}>
          ENTITIES
          {data && <span style={{ fontFamily: font.mono, fontSize: '13px', color: color.fgDisabled, marginLeft: '16px' }}>{data.total}</span>}
        </h1>
        <Link href="/entities/trending" style={{
          fontFamily: font.mono, fontSize: '10px', letterSpacing: '0.8px',
          color: color.fgMuted, textDecoration: 'none',
          border: `1px solid ${color.borderStrong}`, padding: '8px 14px', textTransform: 'uppercase',
        }}>
          TRENDING
        </Link>
      </div>

      <div style={{ display: 'flex', gap: '12px', marginBottom: '24px', flexWrap: 'wrap', alignItems: 'center' }}>
        <input
          type="text"
          placeholder="SEARCH ENTITY"
          value={search}
          onChange={e => setSearch(e.target.value)}
          style={{
            background: color.surfaceHover, border: `1px solid ${color.borderStrong}`,
            color: color.fg, fontFamily: font.mono, fontSize: '11px',
            letterSpacing: '0.8px', padding: '8px 14px', width: '240px', outline: 'none',
          }}
        />
        <div style={{ display: 'flex', gap: '4px' }}>
          {ENTITY_TYPES.map(t => (
            <button key={t || 'all'} onClick={() => setTypeFilter(t)} style={{
              background: typeFilter === t ? color.surfaceSelected : 'transparent',
              border: `1px solid ${color.borderStrong}`,
              color: typeFilter === t ? color.fg : color.fgMuted,
              fontFamily: font.mono, fontSize: '10px', letterSpacing: '0.5px',
              padding: '7px 12px', cursor: 'pointer', textTransform: 'uppercase',
            }}>
              {t || 'ALL'}
            </button>
          ))}
        </div>
        <div style={{ display: 'flex', gap: '4px' }}>
          {([['last_seen', 'RECENT'], ['mention_count', 'MENTIONS'], ['velocity_score', 'VELOCITY']] as const).map(([key, label]) => (
            <button key={key} onClick={() => setSort(key)} style={{
              background: sort === key ? color.surfaceSelected : 'transparent',
              border: `1px solid ${color.borderStrong}`,
              color: sort === key ? color.fg : color.fgMuted,
              fontFamily: font.mono, fontSize: '10px', letterSpacing: '0.5px',
              padding: '7px 12px', cursor: 'pointer', textTransform: 'uppercase',
            }}>
              {label}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <div style={{ border: `1px solid ${color.border}` }}>
          {[0, 1, 2, 3, 4].map(i => (
            <div key={i} style={{ height: '48px', borderBottom: `1px solid ${color.surfaceHover}`, backgroundColor: color.surface }} />
          ))}
        </div>
      ) : entities.length === 0 ? (
        <div style={{ border: `1px solid ${color.surfaceActive}`, padding: '48px', textAlign: 'center' }}>
          <span style={{ fontFamily: font.body, fontSize: '13px', color: color.fgGhost }}>
            {search || typeFilter ? 'No entities match the current filters.' : 'No entities yet. Run the pipeline to extract entities from collected data.'}
          </span>
        </div>
      ) : (
        <div style={{ border: `1px solid ${color.border}` }}>
          <div style={{ display: 'grid', gridTemplateColumns: '2fr 80px 90px 90px 80px 130px', gap: '12px', padding: '10px 16px', borderBottom: `1px solid ${color.surfaceActive}` }}>
            {['NAME', 'TYPE', 'MENTIONS', 'VELOCITY', 'SOURCES', 'LAST SEEN'].map(h => (
              <span key={h} style={{ fontFamily: font.body, fontSize: '10px', color: color.fgDisabled, letterSpacing: '0.8px', textTransform: 'uppercase' }}>{h}</span>
            ))}
          </div>
          {entities.map(e => (
            <Link
              key={e.id}
              href={`/entities/${e.id}`}
              style={{ display: 'grid', gridTemplateColumns: '2fr 80px 90px 90px 80px 130px', gap: '12px', padding: '14px 16px', borderBottom: `1px solid ${color.surfaceHover}`, textDecoration: 'none', alignItems: 'center' }}
            >
              <div style={{ overflow: 'hidden' }}>
                <div style={{ fontFamily: font.body, fontSize: '13px', color: color.fg, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {e.canonical_name}
                </div>
                {e.aliases && e.aliases.length > 0 && (
                  <div style={{ fontFamily: font.mono, fontSize: '10px', color: color.fgDisabled, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {e.aliases.slice(0, 3).join(', ')}
                  </div>
                )}
              </div>
              <span style={{
                fontFamily: font.mono, fontSize: '9px', letterSpacing: '0.5px',
                color: TYPE_COLORS[e.type] || color.fgDisabled,
                border: `1px solid ${TYPE_COLORS[e.type] || color.borderStrong}`,
                padding: '2px 6px', textTransform: 'uppercase', textAlign: 'center',
              }}>
                {e.type}
              </span>
              <span style={{ fontFamily: font.mono, fontSize: '13px', color: color.fgSecondary }}>{e.mention_count}</span>
              <span style={{ fontFamily: font.mono, fontSize: '13px', color: e.velocity_score > 0 ? color.success : color.fgDisabled }}>
                {e.velocity_score > 0 ? e.velocity_score.toFixed(1) : '—'}
              </span>
              <span style={{ fontFamily: font.mono, fontSize: '13px', color: color.fgSecondary }}>{e.source_diversity}</span>
              <span style={{ fontFamily: font.body, fontSize: '12px', color: color.fgMuted }}>
                {new Date(e.last_seen).toLocaleDateString()}
              </span>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
