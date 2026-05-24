'use client';
import { useState } from 'react';
import Link from 'next/link';
import useSWR from 'swr';
import { endpoints, fetcher } from '@/lib/api';
import { NicheScore } from '@/lib/types';
import { color, font } from '@/lib/tokens';

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
  GO: color.success,
  'NO-GO': color.error,
  PIVOT: color.warning,
};

function complexityColor(c: number | null): string {
  if (c === null) return color.fgDisabled;
  if (c <= 2) return color.success;
  if (c === 3) return color.warning;
  return color.error;
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
    <div style={{ padding: '96px 0', textAlign: 'center' as const }}>
      <p style={{ fontFamily: font.mono, fontSize: '12px', color: color.fgGhost, letterSpacing: '0.8px', textTransform: 'uppercase' as const }}>
        CANNOT CONNECT TO API
      </p>
    </div>
  );

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '24px', gap: '24px', flexWrap: 'wrap' }}>
        <h1 style={{ fontFamily: font.body, fontSize: '30px', fontWeight: 400, color: color.fg }}>
          OPPORTUNITIES
          {niches && <span style={{ fontFamily: font.mono, fontSize: '13px', color: color.fgDisabled, marginLeft: '16px' }}>{filtered.length}</span>}
        </h1>
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          <a href={csvUrl} download="niches.csv" style={{
            fontFamily: font.mono, fontSize: '10px', letterSpacing: '0.8px',
            color: color.fgMuted, textDecoration: 'none',
            border: `1px solid ${color.borderStrong}`, padding: '8px 14px', textTransform: 'uppercase' as const,
          }}>
            ↓ CSV
          </a>
          <Link href="/shortlist" style={{
            fontFamily: font.mono, fontSize: '10px', letterSpacing: '0.8px',
            color: color.fgMuted, textDecoration: 'none',
            border: `1px solid ${color.borderStrong}`, padding: '8px 14px', textTransform: 'uppercase' as const,
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
            background: color.surfaceHover, border: `1px solid ${color.borderStrong}`,
            color: color.fg, fontFamily: font.mono, fontSize: '11px',
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
            background: color.surfaceHover, border: `1px solid ${color.borderStrong}`,
            color: color.fg, fontFamily: font.mono, fontSize: '11px',
            letterSpacing: '0.8px', padding: '8px 14px', width: '110px', outline: 'none',
          }}
        />
        {/* Trend filter */}
        <div style={{ display: 'flex', gap: '4px' }}>
          {['any', 'growing', 'stable', 'declining'].map(t => (
            <button key={t} onClick={() => setTrendFilter(t)} style={{
              background: trendFilter === t ? color.surfaceSelected : 'transparent',
              border: `1px solid ${color.borderStrong}`,
              color: trendFilter === t ? color.fg : color.fgMuted,
              fontFamily: font.mono, fontSize: '10px', letterSpacing: '0.5px',
              padding: '7px 12px', cursor: 'pointer', textTransform: 'uppercase' as const,
            }}>
              {t === 'any' ? 'ALL' : `${TREND_EMOJI[t]} ${t}`}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? <LoadingSkeleton /> : sorted.length === 0 ? (
        <div style={{ border: `1px solid ${color.surfaceActive}`, padding: '48px', textAlign: 'center' as const, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '20px' }}>
          <span style={{ fontFamily: font.body, fontSize: '13px', color: color.fgGhost }}>
            {filter || trendFilter !== 'any' || minScore ? 'No opportunities match the current filters.' : 'No opportunities yet.'}
          </span>
          {!filter && trendFilter === 'any' && !minScore && (
            <Link href="/pipeline" style={{ fontFamily: font.mono, fontSize: '11px', color: color.fgSecondary, textDecoration: 'none', border: `1px solid ${color.borderStrong}`, padding: '8px 16px', letterSpacing: '0.8px', textTransform: 'uppercase' as const }}>
              RUN PIPELINE →
            </Link>
          )}
        </div>
      ) : (
        <div style={{ border: `1px solid ${color.border}` }}>
          {/* Header row */}
          <div style={{ display: 'grid', gridTemplateColumns: `${COLUMNS.map(c => c.width).join(' ')} 90px 70px`, gap: '12px', padding: '10px 16px', borderBottom: `1px solid ${color.surfaceActive}` }}>
            {COLUMNS.map(col => (
              <button key={col.key} onClick={() => toggleSort(col.key)} style={{
                background: 'none', border: 'none', padding: 0, cursor: 'pointer', textAlign: 'left',
                fontFamily: font.body, fontSize: '10px',
                color: sortKey === col.key ? color.fgSecondary : color.fgDisabled,
                letterSpacing: '0.8px', textTransform: 'uppercase' as const, display: 'flex', gap: '6px', alignItems: 'center',
              }}>
                {col.label}
                {sortKey === col.key && <span style={{ fontSize: '9px' }}>{sortDir === 'asc' ? '↑' : '↓'}</span>}
              </button>
            ))}
            <span style={{ fontFamily: font.body, fontSize: '10px', color: color.fgDisabled, letterSpacing: '0.8px', textTransform: 'uppercase' as const }}>TREND</span>
            <span style={{ fontFamily: font.body, fontSize: '10px', color: color.fgDisabled, letterSpacing: '0.8px', textTransform: 'uppercase' as const }}>TIER</span>
          </div>

          {sorted.map(n => (
            <Link
              key={n.niche_id || n.id}
              href={`/niches/${n.id || n.niche_id}`}
              style={{ display: 'grid', gridTemplateColumns: `${COLUMNS.map(c => c.width).join(' ')} 90px 70px`, gap: '12px', padding: '14px 16px', borderBottom: `1px solid ${color.surfaceHover}`, textDecoration: 'none', alignItems: 'center' }}
            >
              <div style={{ overflow: 'hidden' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '2px' }}>
                  <div style={{ fontFamily: font.body, fontSize: '13px', color: color.fg, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {n.tool_concept || n.keyword}
                  </div>
                  {n.verdict && n.verdict !== 'null' && (
                    <span style={{ fontFamily: font.mono, fontSize: '9px', color: VERDICT_COLOR[n.verdict] || color.fgDisabled, border: `1px solid ${VERDICT_COLOR[n.verdict] || color.borderStrong}`, padding: '1px 5px', flexShrink: 0 }}>
                      {n.verdict}
                    </span>
                  )}
                </div>
                <div style={{ fontFamily: font.mono, fontSize: '10px', color: color.fgDisabled, textTransform: 'uppercase' as const, letterSpacing: '0.5px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {n.keyword}{n.target_audience ? ` · ${n.target_audience}` : ''}
                </div>
              </div>
              <span style={{ fontFamily: font.mono, fontSize: '14px', color: color.fg }}>
                {n.llm_score.toFixed(0)}
              </span>
              <span style={{ fontFamily: font.mono, fontSize: '11px', color: complexityColor(n.build_complexity), letterSpacing: '0.3px' }}>
                {n.build_complexity ? `${COMPLEXITY_SHORT[n.build_complexity]} (${n.build_complexity}/5)` : '—'}
              </span>
              <span style={{ fontFamily: font.mono, fontSize: '13px', color: color.fgSecondary }}>
                {n.occurrence_count}
              </span>
              <span style={{ fontFamily: font.body, fontSize: '12px', color: color.fgMuted }}>
                {new Date(n.last_seen).toLocaleDateString()}
              </span>
              {/* Trend */}
              <span style={{ fontFamily: font.mono, fontSize: '11px', color: n.momentum_label === 'growing' ? color.success : n.momentum_label === 'declining' ? color.error : color.fgDisabled }}>
                {n.momentum_label ? `${TREND_EMOJI[n.momentum_label]} ${n.momentum_label}` : '—'}
              </span>
              {/* Tier */}
              <span style={{ fontFamily: font.mono, fontSize: '10px', color: n.tier === 'high_priority' ? color.fg : n.tier === 'watchlist' ? color.fgMuted : color.fgGhost, letterSpacing: '0.5px', textTransform: 'uppercase' as const }}>
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
    <div style={{ border: `1px solid ${color.border}` }}>
      {[0, 1, 2, 3, 4].map(i => (
        <div key={i} style={{ height: '48px', borderBottom: `1px solid ${color.surfaceHover}`, backgroundColor: color.surface }} />
      ))}
    </div>
  );
}
