'use client';

import { SourceFreshness, FreshnessSummary } from '@/lib/types';
import { ALL_SOURCES, sourceIcon, sourceFreshnessRule, sourceLabel } from '@/lib/tokens';
import { color as c, font, fontSize, spacing } from '@/lib/tokens';

interface DataFreshnessProps {
  freshness: FreshnessSummary;
}

function freshnessColor(ageHours: number | null, ruleHours: number): string {
  if (ageHours === null) return c.fgGhost;
  const ratio = ageHours / ruleHours;
  if (ratio <= 0.5) return c.success;
  if (ratio <= 1.0) return c.successMuted;
  if (ratio <= 2.0) return c.warning;
  return c.error;
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
    ? c.error
    : staleCount > 0
      ? c.warning
      : noDataCount === totalSources
        ? c.fgGhost
        : c.success;

  const overallLabel = expiredCount > 0
    ? `${expiredCount} EXPIRED`
    : staleCount > 0
      ? `${staleCount} STALE`
      : noDataCount === totalSources
        ? 'NO DATA'
        : 'ALL FRESH';

  return (
    <div style={{
      border: `1px solid ${c.surfaceActive}`,
    }}>
      {/* Header */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: `${spacing.lg} ${spacing['2xl']}`,
        borderBottom: `1px solid ${c.surfaceHover}`,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: spacing.md }}>
          <span style={{
            fontFamily: font.mono,
            fontSize: fontSize.sm,
            letterSpacing: '1px',
            color: c.fgDisabled,
            textTransform: 'uppercase' as const,
          }}>
            Analysis Window · {freshness.analysis_window_days} Days
          </span>
        </div>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: spacing.sm,
        }}>
          <div style={{
            width: '6px',
            height: '6px',
            borderRadius: '50%',
            background: overallColor,
          }} />
          <span style={{
            fontFamily: font.mono,
            fontSize: fontSize.sm,
            letterSpacing: '0.8px',
            color: overallColor,
            textTransform: 'uppercase' as const,
          }}>
            {overallLabel}
          </span>
        </div>
      </div>

      {/* Source rows */}
      <div style={{ padding: `${spacing.sm} 0` }}>
        {allSources.map((src) => {
          const ruleKey = sourceFreshnessRule[src];
          const ruleHours = rules[ruleKey] ?? 72;
          const data = sourceMap[src];
          const age = data?.newest_age_hours ?? null;
          const items = data?.items ?? 0;
          const fColor = freshnessColor(age, ruleHours);
          const label = freshnessLabel(age);
          const pct = barPercent(age, ruleHours);
          const icon = sourceIcon[src] ?? '·';

          return (
            <div key={src} style={{
              display: 'grid',
              gridTemplateColumns: '140px 1fr 90px 80px 60px',
              alignItems: 'center',
              padding: `${spacing.md} ${spacing['2xl']}`,
              gap: spacing.lg,
              borderBottom: `1px solid ${c.surface}`,
            }}>
              {/* Source name */}
              <div style={{ display: 'flex', alignItems: 'center', gap: spacing.sm }}>
                <span style={{
                  fontFamily: font.mono,
                  fontSize: fontSize.md,
                  color: c.fgGhost,
                  width: '14px',
                  textAlign: 'center' as const,
                }}>
                  {icon}
                </span>
                <span style={{
                  fontFamily: font.mono,
                  fontSize: fontSize.base,
                  letterSpacing: '0.8px',
                  textTransform: 'uppercase' as const,
                  color: c.fgSecondary,
                }}>
                  {sourceLabel[src] || src.replace(/_/g, ' ')}
                </span>
              </div>

              {/* Freshness bar */}
              <div style={{
                height: '4px',
                background: c.surface,
                borderRadius: '2px',
                overflow: 'hidden',
              }}>
                <div style={{
                  width: `${pct}%`,
                  height: '100%',
                  background: fColor,
                  borderRadius: '2px',
                  transition: 'width 0.5s ease, background 0.5s ease',
                }} />
              </div>

              {/* Age label */}
              <span style={{
                fontFamily: font.mono,
                fontSize: fontSize.base,
                color: fColor,
                textAlign: 'right' as const,
              }}>
                {label}
              </span>

              {/* Rule threshold */}
              <span style={{
                fontFamily: font.mono,
                fontSize: fontSize.xs,
                letterSpacing: '0.8px',
                color: fColor,
                textAlign: 'center' as const,
                textTransform: 'uppercase' as const,
              }}>
                ≤{ruleHours}h
              </span>

              {/* Item count */}
              <span style={{
                fontFamily: font.mono,
                fontSize: fontSize.base,
                color: c.fgGhost,
                textAlign: 'right' as const,
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
        gap: spacing.xl,
        padding: `${spacing.md} ${spacing['2xl']}`,
        borderTop: `1px solid ${c.surface}`,
      }}>
        {[
          { label: 'FRESH', lc: c.success },
          { label: 'STALE', lc: c.warning },
          { label: 'EXPIRED', lc: c.error },
        ].map(({ label: l, lc }) => (
          <div key={l} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <div style={{ width: '8px', height: '3px', background: lc, borderRadius: '1px' }} />
            <span style={{
              fontFamily: font.mono,
              fontSize: fontSize.xs,
              letterSpacing: '0.8px',
              color: c.fgGhost,
              textTransform: 'uppercase' as const,
            }}>
              {l}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
