'use client';
import { useState } from 'react';
import Link from 'next/link';
import useSWR from 'swr';
import { endpoints, fetcher } from '@/lib/api';
import { NicheScore } from '@/lib/types';

type SortKey = 'llm_score' | 'keyword' | 'build_complexity' | 'occurrence_count' | 'last_seen';

const COLUMNS: { key: SortKey; label: string; width: string }[] = [
  { key: 'keyword', label: 'TOOL CONCEPT', width: '2fr' },
  { key: 'llm_score', label: 'SCORE', width: '70px' },
  { key: 'build_complexity', label: 'BUILD', width: '90px' },
  { key: 'occurrence_count', label: 'MENTIONS', width: '90px' },
  { key: 'last_seen', label: 'LAST SEEN', width: '140px' },
];

const TIER_LABELS: Record<NicheScore['tier'], string> = {
  high_priority: 'HIGH',
  watchlist: 'WATCH',
  archive: 'ARCH',
};

const COMPLEXITY_SHORT: Record<number, string> = {
  1: 'wknd', 2: '2-3d', 3: '~1w', 4: '1-2w', 5: '2w+',
};

const TREND_EMOJI: Record<string, string> = {
  growing: '📈', stable: '➡️', declining: '📉',
};

const VERDICT_COLOR: Record<string, string> = {
  GO: 'rgba(74,222,128,0.85)',
  'NO-GO': 'rgba(255,80,80,0.85)',
  PIVOT: 'rgba(251,191,36,0.85)',
};

function complexityColor(c: number | null): string {
  if (c === null) return 'rgba(255,255,255,0.35)';
  if (c <= 2) return 'rgba(74,222,128,0.85)';
  if (c === 3) return 'rgba(251,191,36,0.85)';
  return 'rgba(255,140,140,0.85)';
}

export default function NichesPage() {
  const [sortKey, setSortKey] = useState<SortKey>('llm_score');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
  const [filter, setFilter] = useState('');
  const [trendFilter, setTrendFilter] = useState<string>('any');
  const [minScore, setMinScore] = useState<string>('');

  const { data: niches, error, isLoading } =
    useSWR<NicheScore[]>(endpoints.niches, fetcher, { refreshInterval: 60_000 });

  function toggleSort(key: SortKey) {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortKey(key); setSortDir('desc'); }
  }

  const filtered = (niches ?? []).filter(n => {
    if (filter) {
      const f = filter.toLowerCase();
      if (!n.keyword.toLowerCase().includes(f) &&
          !(n.tool_concept || '').toLowerCase().includes(f) &&
          !(n.target_audience || '').toLowerCase().includes(f)) return false;
    }
    if (trendFilter !== 'any' && n.momentum_label !== trendFilter) return false;
    if (minScore && n.llm_score < Number(minScore)) return false;
    return true;
  });

  const sorted = [...filtered].sort((a, b) => {
    const av = a[sortKey], bv = b[sortKey];
    if (av === null && bv === null) return 0;
    if (av === null) return 1;
    if (bv === null) return -1;
    const cmp = typeof av === 'string' ? av.localeCompare(bv as string) : (av as number) - (bv as number);
    return sortDir === 'asc' ? cmp : -cmp;
  });

  const csvUrl = `/api/niches?format=csv${trendFilter !== 'any' ? `&trend=${trendFilter}` : ''}${minScore ? `&min_score=${minScore}` : ''}`;

  if (error) return (
    <div style={{ padding: '96px 0', textAlign: 'center' }}>
      <p style={{ fontFamily: 'var(--font-geist-mono)', fontSize: '12px', color: 'rgba(255,255,255,0.3)', letterSpacing: '0.8px', textTransform: 'uppercase' }}>
        CANNOT CONNECT TO API
      </p>
    </div>
  );

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '24px', gap: '24px', flexWrap: 'wrap' }}>
        <h1 style={{ fontFamily: 'var(--font-inter)', fontSize: '30px', fontWeight: 400, color: '#ffffff' }}>
          OPPORTUNITIES
          {niches && <span style={{ fontFamily: 'var(--font-geist-mono)', fontSize: '13px', color: 'rgba(255,255,255,0.35)', marginLeft: '16px' }}>{filtered.length}</span>}
        </h1>
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          <a href={csvUrl} download="niches.csv" style={{
            fontFamily: 'var(--font-geist-mono)', fontSize: '10px', letterSpacing: '0.8px',
            color: 'rgba(255,255,255,0.4)', textDecoration: 'none',
            border: '1px solid rgba(255,255,255,0.15)', padding: '8px 14px', textTransform: 'uppercase',
          }}>
            ↓ CSV
          </a>
          <Link href="/shortlist" style={{
            fontFamily: 'var(--font-geist-mono)', fontSize: '10px', letterSpacing: '0.8px',
            color: 'rgba(255,255,255,0.4)', textDecoration: 'none',
            border: '1px solid rgba(255,255,255,0.15)', padding: '8px 14px', textTransform: 'uppercase',
          }}>
            ★ SHORTLIST
          </Link>
        </div>
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', gap: '12px', marginBottom: '24px', flexWrap: 'wrap', alignItems: 'center' }}>
        <input
          type="text"
          placeholder="FILTER CONCEPT / KEYWORD"
          value={filter}
          onChange={e => setFilter(e.target.value)}
          aria-label="Filter opportunities by concept or keyword"
          style={{
            background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.15)',
            color: '#ffffff', fontFamily: 'var(--font-geist-mono)', fontSize: '11px',
            letterSpacing: '0.8px', padding: '8px 14px', width: '280px', outline: 'none',
          }}
        />
        <input
          type="number"
          placeholder="MIN SCORE"
          value={minScore}
          onChange={e => setMinScore(e.target.value)}
          aria-label="Minimum score filter"
          style={{
            background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.15)',
            color: '#ffffff', fontFamily: 'var(--font-geist-mono)', fontSize: '11px',
            letterSpacing: '0.8px', padding: '8px 14px', width: '110px', outline: 'none',
          }}
        />
        {/* Trend filter */}
        <div style={{ display: 'flex', gap: '4px' }}>
          {['any', 'growing', 'stable', 'declining'].map(t => (
            <button key={t} onClick={() => setTrendFilter(t)} style={{
              background: trendFilter === t ? 'rgba(255,255,255,0.12)' : 'transparent',
              border: '1px solid rgba(255,255,255,0.15)',
              color: trendFilter === t ? '#ffffff' : 'rgba(255,255,255,0.4)',
              fontFamily: 'var(--font-geist-mono)', fontSize: '10px', letterSpacing: '0.5px',
              padding: '7px 12px', cursor: 'pointer', textTransform: 'uppercase',
            }}>
              {t === 'any' ? 'ALL' : `${TREND_EMOJI[t]} ${t}`}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? <LoadingSkeleton /> : sorted.length === 0 ? (
        <div style={{ border: '1px solid rgba(255,255,255,0.08)', padding: '48px', textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '20px' }}>
          <span style={{ fontFamily: 'var(--font-inter)', fontSize: '13px', color: 'rgba(255,255,255,0.25)' }}>
            {filter || trendFilter !== 'any' || minScore ? 'No opportunities match the current filters.' : 'No opportunities yet.'}
          </span>
          {!filter && trendFilter === 'any' && !minScore && (
            <Link href="/pipeline" style={{ fontFamily: 'var(--font-geist-mono)', fontSize: '11px', color: 'rgba(255,255,255,0.7)', textDecoration: 'none', border: '1px solid rgba(255,255,255,0.2)', padding: '8px 16px', letterSpacing: '0.8px', textTransform: 'uppercase' }}>
              RUN PIPELINE →
            </Link>
          )}
        </div>
      ) : (
        <div style={{ border: '1px solid rgba(255,255,255,0.1)' }}>
          {/* Header row */}
          <div style={{ display: 'grid', gridTemplateColumns: `${COLUMNS.map(c => c.width).join(' ')} 90px 70px`, gap: '12px', padding: '10px 16px', borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
            {COLUMNS.map(col => (
              <button key={col.key} onClick={() => toggleSort(col.key)} style={{
                background: 'none', border: 'none', padding: 0, cursor: 'pointer', textAlign: 'left',
                fontFamily: 'var(--font-inter)', fontSize: '10px',
                color: sortKey === col.key ? 'rgba(255,255,255,0.7)' : 'rgba(255,255,255,0.35)',
                letterSpacing: '0.8px', textTransform: 'uppercase', display: 'flex', gap: '6px', alignItems: 'center',
              }}>
                {col.label}
                {sortKey === col.key && <span style={{ fontSize: '9px' }}>{sortDir === 'asc' ? '↑' : '↓'}</span>}
              </button>
            ))}
            <span style={{ fontFamily: 'var(--font-inter)', fontSize: '10px', color: 'rgba(255,255,255,0.35)', letterSpacing: '0.8px', textTransform: 'uppercase' }}>TREND</span>
            <span style={{ fontFamily: 'var(--font-inter)', fontSize: '10px', color: 'rgba(255,255,255,0.35)', letterSpacing: '0.8px', textTransform: 'uppercase' }}>TIER</span>
          </div>

          {sorted.map(n => (
            <Link
              key={n.niche_id || n.id}
              href={`/niches/${n.id || n.niche_id}`}
              style={{ display: 'grid', gridTemplateColumns: `${COLUMNS.map(c => c.width).join(' ')} 90px 70px`, gap: '12px', padding: '14px 16px', borderBottom: '1px solid rgba(255,255,255,0.05)', textDecoration: 'none', alignItems: 'center' }}
            >
              <div style={{ overflow: 'hidden' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '2px' }}>
                  <div style={{ fontFamily: 'var(--font-inter)', fontSize: '13px', color: '#ffffff', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {n.tool_concept || n.keyword}
                  </div>
                  {n.verdict && n.verdict !== 'null' && (
                    <span style={{ fontFamily: 'var(--font-geist-mono)', fontSize: '9px', color: VERDICT_COLOR[n.verdict] || 'rgba(255,255,255,0.35)', border: `1px solid ${VERDICT_COLOR[n.verdict] || 'rgba(255,255,255,0.2)'}`, padding: '1px 5px', flexShrink: 0 }}>
                      {n.verdict}
                    </span>
                  )}
                </div>
                <div style={{ fontFamily: 'var(--font-geist-mono)', fontSize: '10px', color: 'rgba(255,255,255,0.35)', textTransform: 'uppercase', letterSpacing: '0.5px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {n.keyword}{n.target_audience ? ` · ${n.target_audience}` : ''}
                </div>
              </div>
              <span style={{ fontFamily: 'var(--font-geist-mono)', fontSize: '14px', color: '#ffffff' }}>
                {n.llm_score.toFixed(0)}
              </span>
              <span style={{ fontFamily: 'var(--font-geist-mono)', fontSize: '11px', color: complexityColor(n.build_complexity), letterSpacing: '0.3px' }}>
                {n.build_complexity ? `${COMPLEXITY_SHORT[n.build_complexity]} (${n.build_complexity}/5)` : '—'}
              </span>
              <span style={{ fontFamily: 'var(--font-geist-mono)', fontSize: '13px', color: 'rgba(255,255,255,0.6)' }}>
                {n.occurrence_count}
              </span>
              <span style={{ fontFamily: 'var(--font-inter)', fontSize: '12px', color: 'rgba(255,255,255,0.5)' }}>
                {new Date(n.last_seen).toLocaleDateString()}
              </span>
              {/* Trend */}
              <span style={{ fontFamily: 'var(--font-geist-mono)', fontSize: '11px', color: n.momentum_label === 'growing' ? 'rgba(74,222,128,0.85)' : n.momentum_label === 'declining' ? 'rgba(255,140,140,0.85)' : 'rgba(255,255,255,0.35)' }}>
                {n.momentum_label ? `${TREND_EMOJI[n.momentum_label]} ${n.momentum_label}` : '—'}
              </span>
              {/* Tier */}
              <span style={{ fontFamily: 'var(--font-geist-mono)', fontSize: '10px', color: n.tier === 'high_priority' ? 'rgba(255,255,255,0.85)' : n.tier === 'watchlist' ? 'rgba(255,255,255,0.5)' : 'rgba(255,255,255,0.25)', letterSpacing: '0.5px', textTransform: 'uppercase' }}>
                {TIER_LABELS[n.tier]}
              </span>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div style={{ border: '1px solid rgba(255,255,255,0.1)' }}>
      {[0, 1, 2, 3, 4].map(i => (
        <div key={i} style={{ height: '48px', borderBottom: '1px solid rgba(255,255,255,0.05)', backgroundColor: 'rgba(255,255,255,0.02)' }} />
      ))}
    </div>
  );
}
