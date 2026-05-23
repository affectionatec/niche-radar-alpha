'use client';

import { SourceFreshness, FreshnessSummary } from '@/lib/types';
import { ALL_SOURCES, sourceIcon, sourceFreshnessRule, sourceLabel } from '@/lib/tokens';

interface DataFreshnessProps {
  freshness: FreshnessSummary;
}

function freshnessColor(ageHours: number | null, ruleHours: number): string {
  if (ageHours === null) return 'rgba(255,255,255,0.15)';
  const ratio = ageHours / ruleHours;
  if (ratio <= 0.5) return 'rgba(74,222,128,0.8)';
  if (ratio <= 1.0) return 'rgba(74,222,128,0.5)';
  if (ratio <= 2.0) return 'rgba(251,191,36,0.7)';
  return 'rgba(255,80,80,0.7)';
}

function freshnessLabel(ageHours: number | null): string {
  if (ageHours === null) return 'NO DATA';
  if (ageHours < 1) return `${Math.round(ageHours * 60)}m ago`;
  if (ageHours < 24) return `${ageHours.toFixed(0)}h ago`;
  const days = ageHours / 24;
  if (days < 7) return `${days.toFixed(1)}d ago`;
  return `${Math.round(days)}d ago`;
}

function freshnessStatus(ageHours: number | null, ruleHours: number): string {
  if (ageHours === null) return 'NONE';
  const ratio = ageHours / ruleHours;
  if (ratio <= 0.5) return 'FRESH';
  if (ratio <= 1.0) return 'OK';
  if (ratio <= 2.0) return 'STALE';
  return 'EXPIRED';
}

function barPercent(ageHours: number | null, ruleHours: number): number {
  if (ageHours === null) return 0;
  // Invert: fresh = 100%, stale = low%
  const ratio = ageHours / ruleHours;
  if (ratio <= 0) return 100;
  if (ratio >= 3) return 5;
  return Math.max(5, Math.round(100 - (ratio / 3) * 100));
}

export default function DataFreshness({ freshness }: DataFreshnessProps) {
  const rules = freshness.rules as Record<string, number>;
  const sourceMap: Record<string, SourceFreshness> = {};
  for (const s of freshness.per_source) {
    sourceMap[s.source] = s;
  }

  const allSources = [...ALL_SOURCES];

  // Compute overall health
  const totalSources = allSources.length;
  let freshCount = 0;
  let staleCount = 0;
  let expiredCount = 0;
  let noDataCount = 0;

  for (const src of allSources) {
    const ruleKey = sourceFreshnessRule[src];
    const ruleHours = rules[ruleKey] ?? 72;
    const data = sourceMap[src];
    const age = data?.newest_age_hours ?? null;
    const status = freshnessStatus(age, ruleHours);
    if (status === 'FRESH' || status === 'OK') freshCount++;
    else if (status === 'STALE') staleCount++;
    else if (status === 'EXPIRED') expiredCount++;
    else noDataCount++;
  }

  const overallColor = expiredCount > 0
    ? 'rgba(255,80,80,0.8)'
    : staleCount > 0
      ? 'rgba(251,191,36,0.8)'
      : noDataCount === totalSources
        ? 'rgba(255,255,255,0.3)'
        : 'rgba(74,222,128,0.8)';

  const overallLabel = expiredCount > 0
    ? `${expiredCount} EXPIRED`
    : staleCount > 0
      ? `${staleCount} STALE`
      : noDataCount === totalSources
        ? 'NO DATA'
        : 'ALL FRESH';

  return (
    <div style={{
      border: '1px solid rgba(255,255,255,0.08)',
    }}>
      {/* Header */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: '16px 24px',
        borderBottom: '1px solid rgba(255,255,255,0.06)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span style={{
            fontFamily: 'var(--font-geist-mono)',
            fontSize: '10px',
            letterSpacing: '1px',
            color: 'rgba(255,255,255,0.35)',
            textTransform: 'uppercase',
          }}>
            Analysis Window · {freshness.analysis_window_days} Days
          </span>
        </div>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
        }}>
          <div style={{
            width: '6px',
            height: '6px',
            borderRadius: '50%',
            background: overallColor,
          }} />
          <span style={{
            fontFamily: 'var(--font-geist-mono)',
            fontSize: '10px',
            letterSpacing: '0.8px',
            color: overallColor,
            textTransform: 'uppercase',
          }}>
            {overallLabel}
          </span>
        </div>
      </div>

      {/* Source rows */}
      <div style={{ padding: '8px 0' }}>
        {allSources.map((src) => {
          const ruleKey = sourceFreshnessRule[src];
          const ruleHours = rules[ruleKey] ?? 72;
          const data = sourceMap[src];
          const age = data?.newest_age_hours ?? null;
          const items = data?.items ?? 0;
          const color = freshnessColor(age, ruleHours);
          const label = freshnessLabel(age);
          const status = freshnessStatus(age, ruleHours);
          const pct = barPercent(age, ruleHours);
          const icon = sourceIcon[src] ?? '·';

          return (
            <div key={src} style={{
              display: 'grid',
              gridTemplateColumns: '140px 1fr 90px 80px 60px',
              alignItems: 'center',
              padding: '10px 24px',
              gap: '16px',
              borderBottom: '1px solid rgba(255,255,255,0.03)',
            }}>
              {/* Source name */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{
                  fontFamily: 'var(--font-geist-mono)',
                  fontSize: '12px',
                  color: 'rgba(255,255,255,0.3)',
                  width: '14px',
                  textAlign: 'center',
                }}>
                  {icon}
                </span>
                <span style={{
                  fontFamily: 'var(--font-geist-mono)',
                  fontSize: '11px',
                  letterSpacing: '0.8px',
                  textTransform: 'uppercase',
                  color: 'rgba(255,255,255,0.7)',
                }}>
                  {sourceLabel[src] || src.replace(/_/g, ' ')}
                </span>
              </div>

              {/* Freshness bar */}
              <div style={{
                height: '4px',
                background: 'rgba(255,255,255,0.04)',
                borderRadius: '2px',
                overflow: 'hidden',
              }}>
                <div style={{
                  width: `${pct}%`,
                  height: '100%',
                  background: color,
                  borderRadius: '2px',
                  transition: 'width 0.5s ease, background 0.5s ease',
                }} />
              </div>

              {/* Age label */}
              <span style={{
                fontFamily: 'var(--font-geist-mono)',
                fontSize: '11px',
                color,
                textAlign: 'right',
              }}>
                {label}
              </span>

              {/* Status badge */}
              <span style={{
                fontFamily: 'var(--font-geist-mono)',
                fontSize: '9px',
                letterSpacing: '0.8px',
                color,
                textAlign: 'center',
                textTransform: 'uppercase',
              }}>
                ≤{ruleHours}h
              </span>

              {/* Item count */}
              <span style={{
                fontFamily: 'var(--font-geist-mono)',
                fontSize: '11px',
                color: 'rgba(255,255,255,0.3)',
                textAlign: 'right',
              }}>
                {items > 0 ? items.toLocaleString() : '—'}
              </span>
            </div>
          );
        })}
      </div>

      {/* Footer legend */}
      <div style={{
        display: 'flex',
        gap: '20px',
        padding: '10px 24px',
        borderTop: '1px solid rgba(255,255,255,0.04)',
      }}>
        {[
          { label: 'FRESH', color: 'rgba(74,222,128,0.7)' },
          { label: 'STALE', color: 'rgba(251,191,36,0.7)' },
          { label: 'EXPIRED', color: 'rgba(255,80,80,0.7)' },
        ].map(({ label: l, color: c }) => (
          <div key={l} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <div style={{ width: '8px', height: '3px', background: c, borderRadius: '1px' }} />
            <span style={{
              fontFamily: 'var(--font-geist-mono)',
              fontSize: '9px',
              letterSpacing: '0.8px',
              color: 'rgba(255,255,255,0.25)',
              textTransform: 'uppercase',
            }}>
              {l}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
