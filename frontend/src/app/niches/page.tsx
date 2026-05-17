'use client';
import { useState } from 'react';
import Link from 'next/link';
import useSWR from 'swr';
import { endpoints, fetcher } from '@/lib/api';
import { NicheScore } from '@/lib/types';

type SortKey = 'llm_score' | 'keyword' | 'occurrence_count' | 'last_seen';

const COLUMNS: { key: SortKey; label: string; width: string }[] = [
  { key: 'keyword', label: 'KEYWORD', width: '1fr' },
  { key: 'llm_score', label: 'SCORE', width: '80px' },
  { key: 'occurrence_count', label: 'MENTIONS', width: '90px' },
  { key: 'last_seen', label: 'LAST SEEN', width: '180px' },
];

const TIER_LABELS: Record<NicheScore['tier'], string> = {
  high_priority: 'HIGH',
  watchlist: 'WATCH',
  archive: 'ARCH',
};

export default function NichesPage() {
  const [sortKey, setSortKey] = useState<SortKey>('llm_score');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
  const [filter, setFilter] = useState('');

  const { data: niches, error, isLoading } =
    useSWR<NicheScore[]>(endpoints.niches, fetcher, { refreshInterval: 60_000 });

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('desc');
    }
  }

  const filtered = (niches ?? []).filter((n) =>
    filter ? n.keyword.toLowerCase().includes(filter.toLowerCase()) : true,
  );

  const sorted = [...filtered].sort((a, b) => {
    const av = a[sortKey];
    const bv = b[sortKey];
    const cmp =
      typeof av === 'string'
        ? (av as string).localeCompare(bv as string)
        : (av as number) - (bv as number);
    return sortDir === 'asc' ? cmp : -cmp;
  });

  if (error) {
    return (
      <div style={{ padding: '96px 0', textAlign: 'center' }}>
        <p
          style={{
            fontFamily: 'var(--font-geist-mono)',
            fontSize: '12px',
            color: 'rgba(255,255,255,0.3)',
            letterSpacing: '0.8px',
            textTransform: 'uppercase',
          }}
        >
          CANNOT CONNECT TO API
        </p>
      </div>
    );
  }

  return (
    <div>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '32px',
          gap: '24px',
          flexWrap: 'wrap',
        }}
      >
        <h1
          style={{
            fontFamily: 'var(--font-inter)',
            fontSize: '30px',
            fontWeight: 400,
            color: '#ffffff',
          }}
        >
          NICHES
          {niches && (
            <span
              style={{
                fontFamily: 'var(--font-geist-mono)',
                fontSize: '13px',
                color: 'rgba(255,255,255,0.35)',
                marginLeft: '16px',
              }}
            >
              {niches.length}
            </span>
          )}
        </h1>
        <input
          type="text"
          placeholder="FILTER BY KEYWORD"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          style={{
            background: 'rgba(255,255,255,0.06)',
            border: '1px solid rgba(255,255,255,0.15)',
            color: '#ffffff',
            fontFamily: 'var(--font-geist-mono)',
            fontSize: '11px',
            letterSpacing: '0.8px',
            padding: '10px 14px',
            width: '240px',
            outline: 'none',
          }}
        />
      </div>

      {isLoading ? (
        <LoadingSkeleton />
      ) : sorted.length === 0 ? (
        <div
          style={{
            border: '1px solid rgba(255,255,255,0.08)',
            padding: '48px',
            textAlign: 'center',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '20px',
          }}
        >
          <span
            style={{
              fontFamily: 'var(--font-inter)',
              fontSize: '13px',
              color: 'rgba(255,255,255,0.25)',
            }}
          >
            {filter ? `No niches matching "${filter}"` : 'No niches yet.'}
          </span>
          {!filter && (
            <Link
              href="/pipeline"
              style={{
                fontFamily: 'var(--font-geist-mono)',
                fontSize: '11px',
                color: 'rgba(255,255,255,0.7)',
                textDecoration: 'none',
                border: '1px solid rgba(255,255,255,0.2)',
                padding: '8px 16px',
                letterSpacing: '0.8px',
                textTransform: 'uppercase',
              }}
            >
              RUN PIPELINE →
            </Link>
          )}
        </div>
      ) : (
        <div style={{ border: '1px solid rgba(255,255,255,0.1)' }}>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: `${COLUMNS.map((c) => c.width).join(' ')} 70px`,
              padding: '10px 16px',
              borderBottom: '1px solid rgba(255,255,255,0.08)',
            }}
          >
            {COLUMNS.map((col) => (
              <button
                key={col.key}
                onClick={() => toggleSort(col.key)}
                style={{
                  background: 'none',
                  border: 'none',
                  padding: 0,
                  cursor: 'pointer',
                  textAlign: 'left',
                  fontFamily: 'var(--font-inter)',
                  fontSize: '10px',
                  color:
                    sortKey === col.key
                      ? 'rgba(255,255,255,0.7)'
                      : 'rgba(255,255,255,0.35)',
                  letterSpacing: '0.8px',
                  textTransform: 'uppercase',
                  display: 'flex',
                  gap: '6px',
                  alignItems: 'center',
                }}
              >
                {col.label}
                {sortKey === col.key && (
                  <span style={{ fontSize: '9px' }}>{sortDir === 'asc' ? '↑' : '↓'}</span>
                )}
              </button>
            ))}
            <span
              style={{
                fontFamily: 'var(--font-inter)',
                fontSize: '10px',
                color: 'rgba(255,255,255,0.35)',
                letterSpacing: '0.8px',
                textTransform: 'uppercase',
              }}
            >
              TIER
            </span>
          </div>

          {sorted.map((n) => (
            <Link
              key={n.niche_id}
              href={`/niches/${n.niche_id}`}
              style={{
                display: 'grid',
                gridTemplateColumns: `${COLUMNS.map((c) => c.width).join(' ')} 70px`,
                padding: '12px 16px',
                borderBottom: '1px solid rgba(255,255,255,0.05)',
                textDecoration: 'none',
              }}
            >
              <span
                style={{
                  fontFamily: 'var(--font-geist-mono)',
                  fontSize: '13px',
                  color: '#ffffff',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                {n.keyword}
              </span>
              <span
                style={{
                  fontFamily: 'var(--font-geist-mono)',
                  fontSize: '13px',
                  color: '#ffffff',
                }}
              >
                {n.llm_score.toFixed(1)}
              </span>
              <span
                style={{
                  fontFamily: 'var(--font-geist-mono)',
                  fontSize: '13px',
                  color: 'rgba(255,255,255,0.6)',
                }}
              >
                {n.occurrence_count}
              </span>
              <span
                style={{
                  fontFamily: 'var(--font-inter)',
                  fontSize: '12px',
                  color: 'rgba(255,255,255,0.5)',
                }}
              >
                {new Date(n.last_seen).toLocaleDateString()}
              </span>
              <span
                style={{
                  fontFamily: 'var(--font-geist-mono)',
                  fontSize: '10px',
                  color:
                    n.tier === 'high_priority'
                      ? 'rgba(255,255,255,0.85)'
                      : n.tier === 'watchlist'
                        ? 'rgba(255,255,255,0.5)'
                        : 'rgba(255,255,255,0.25)',
                  letterSpacing: '0.5px',
                  textTransform: 'uppercase',
                }}
              >
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
      {[0, 1, 2, 3, 4].map((i) => (
        <div
          key={i}
          style={{
            height: '48px',
            borderBottom: '1px solid rgba(255,255,255,0.05)',
            backgroundColor: 'rgba(255,255,255,0.02)',
          }}
        />
      ))}
    </div>
  );
}
