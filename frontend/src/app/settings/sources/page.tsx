'use client';
import { useState } from 'react';
import Link from 'next/link';
import useSWR from 'swr';
import { endpoints, fetcher } from '@/lib/api';
import { SourceStatus } from '@/lib/types';
import { color as c, font, fontSize, spacing, sourceLabel, CN_SOURCES } from '@/lib/tokens';

const SOURCE_DESCRIPTIONS: Record<string, string> = {
  reddit: 'Pain-point posts from targeted subreddits via search queries',
  hn: 'Ask HN posts via Algolia search — no credentials needed',
  google_trends: 'Trending search terms — no credentials needed',
  github: 'Trending repos — optional token for higher rate limits',
  youtube: 'Pain-point videos — optional API key for reliability',
  product_hunt: 'Feature-request signals from product comments',
  stack_overflow: 'Unanswered questions on developer pain tags',
  twitter: '⚠️ Free tier = 500 posts/month — configure carefully',
  g2_reviews: '1-2 star reviews from configurable product slugs',
  indie_hackers: 'Revenue-validated product signals',
  app_store: '1-2 star reviews from configured iOS apps',
  play_store: '1-2 star reviews from configured Android apps',
  xiaohongshu: 'Product reviews & lifestyle pain-points via TikHub API',
  bilibili: 'Tech video complaints & tutorials via public API',
  zhihu: 'Q&A pain-points & tool recommendations (cookie-based)',
  weibo: 'Trending complaints & viral pain-points (cookie-based)',
  douyin: 'Short video product pain-points via TikHub API',
};

type FilterTab = 'all' | 'global' | 'chinese';

function StatusChip({ configured, last_success }: { configured: boolean; last_success: string | null }) {
  const color = configured ? c.success : c.warning;
  const label = configured ? 'CONFIGURED' : 'NEEDS SETUP';
  return (
    <span style={{
      fontFamily: font.mono, fontSize: '10px', letterSpacing: '0.8px',
      color, border: `1px solid ${color}`, padding: '2px 8px',
    }}>
      {label}
    </span>
  );
}

export default function SourcesPage() {
  const [filter, setFilter] = useState<FilterTab>('all');
  const { data: sources, isLoading, error } = useSWR<SourceStatus[]>(
    endpoints.sources, fetcher, { refreshInterval: 30_000 }
  );

  const filtered = sources?.filter(s => {
    if (filter === 'global') return !CN_SOURCES.has(s.slug);
    if (filter === 'chinese') return CN_SOURCES.has(s.slug);
    return true;
  });

  const tabs: { key: FilterTab; label: string; count?: number }[] = [
    { key: 'all', label: 'ALL', count: sources?.length },
    { key: 'global', label: 'GLOBAL', count: sources?.filter(s => !CN_SOURCES.has(s.slug)).length },
    { key: 'chinese', label: 'CHINESE', count: sources?.filter(s => CN_SOURCES.has(s.slug)).length },
  ];

  return (
    <div>
      <div style={{ marginBottom: '32px' }}>
        <Link href="/settings" style={{
          fontFamily: font.mono, fontSize: '12px',
          color: c.fgMuted, textDecoration: 'none',
          textTransform: 'uppercase' as const, letterSpacing: '0.8px',
        }}>
          ← SETTINGS
        </Link>
      </div>

      <h1 style={{ fontFamily: font.body, fontSize: '30px', fontWeight: 400, color: c.fg, marginBottom: '8px' }}>
        DATA SOURCES
      </h1>
      <p style={{ fontFamily: font.body, fontSize: '13px', color: c.fgDisabled, marginBottom: spacing['2xl'] }}>
        Configure credentials and search settings for each data source. Changes take effect immediately — no restart required.
      </p>

      {/* Filter tabs */}
      <div style={{
        display: 'flex', gap: '2px', marginBottom: spacing['2xl'],
        borderBottom: `1px solid ${c.border}`, paddingBottom: '0',
      }}>
        {tabs.map(tab => {
          const active = filter === tab.key;
          return (
            <button
              key={tab.key}
              onClick={() => setFilter(tab.key)}
              style={{
                fontFamily: font.mono, fontSize: fontSize.sm, letterSpacing: '1px',
                color: active ? c.fg : c.fgGhost,
                background: active ? c.surfaceActive : 'transparent',
                border: 'none', borderBottom: active ? `2px solid ${c.fg}` : '2px solid transparent',
                padding: `${spacing.sm} ${spacing.lg}`,
                cursor: 'pointer', transition: 'all 0.15s',
              }}
            >
              {tab.label}{tab.count !== undefined ? ` (${tab.count})` : ''}
            </button>
          );
        })}
      </div>

      {isLoading && <div style={{ color: c.fgDisabled, fontFamily: font.mono, fontSize: '12px' }}>LOADING...</div>}
      {error && <div style={{ color: c.error, fontFamily: font.mono, fontSize: '12px' }}>Failed to load sources</div>}

      {filtered && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
          {filtered.map((s) => (
            <Link
              key={s.slug}
              href={`/settings/sources/${s.slug}`}
              style={{ textDecoration: 'none' }}
            >
              <div style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '16px 20px',
                background: c.surface,
                border: `1px solid ${c.surfaceActive}`,
                cursor: 'pointer',
              }}
              onMouseEnter={e => (e.currentTarget.style.background = c.surfaceHover)}
              onMouseLeave={e => (e.currentTarget.style.background = c.surface)}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: spacing.sm }}>
                    <span style={{ fontFamily: font.mono, fontSize: '13px', color: c.fg }}>
                      {sourceLabel[s.slug] || s.slug}
                    </span>
                    {CN_SOURCES.has(s.slug) && (
                      <span style={{
                        fontFamily: font.mono, fontSize: fontSize.xs, color: c.fgGhost,
                        border: `1px solid ${c.border}`, padding: '1px 6px', letterSpacing: '0.5px',
                      }}>
                        CN
                      </span>
                    )}
                  </div>
                  <div style={{ fontFamily: font.body, fontSize: '12px', color: c.fgDisabled, marginTop: '4px' }}>
                    {SOURCE_DESCRIPTIONS[s.slug] || ''}
                  </div>
                  {s.last_success && (
                    <div style={{ fontFamily: font.mono, fontSize: '10px', color: c.fgGhost, marginTop: '4px' }}>
                      Last run: {new Date(s.last_success).toLocaleDateString()}
                    </div>
                  )}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                  <StatusChip configured={s.configured} last_success={s.last_success} />
                  <span style={{ color: c.fgGhost, fontSize: '16px' }}>›</span>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
