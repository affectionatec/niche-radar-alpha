'use client';
import Link from 'next/link';
import useSWR from 'swr';
import { endpoints, fetcher } from '@/lib/api';
import { SourceStatus } from '@/lib/types';

const SOURCE_LABELS: Record<string, string> = {
  reddit: 'Reddit',
  hn: 'Hacker News',
  google_trends: 'Google Trends',
  github: 'GitHub Trending',
  youtube: 'YouTube',
  product_hunt: 'Product Hunt',
  stack_overflow: 'Stack Overflow',
  twitter: 'Twitter / X',
  g2_reviews: 'G2 Reviews',
  indie_hackers: 'Indie Hackers',
  app_store: 'App Store',
  play_store: 'Play Store',
};

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
};

function StatusChip({ configured, last_success }: { configured: boolean; last_success: string | null }) {
  const color = configured ? 'rgba(74,222,128,0.85)' : 'rgba(251,191,36,0.85)';
  const label = configured ? 'CONFIGURED' : 'NEEDS SETUP';
  return (
    <span style={{
      fontFamily: 'var(--font-geist-mono)', fontSize: '10px', letterSpacing: '0.8px',
      color, border: `1px solid ${color}`, padding: '2px 8px',
    }}>
      {label}
    </span>
  );
}

export default function SourcesPage() {
  const { data: sources, isLoading, error } = useSWR<SourceStatus[]>(
    endpoints.sources, fetcher, { refreshInterval: 30_000 }
  );

  return (
    <div>
      <div style={{ marginBottom: '32px' }}>
        <Link href="/settings" style={{
          fontFamily: 'var(--font-geist-mono)', fontSize: '12px',
          color: 'rgba(255,255,255,0.4)', textDecoration: 'none',
          textTransform: 'uppercase', letterSpacing: '0.8px',
        }}>
          ← SETTINGS
        </Link>
      </div>

      <h1 style={{ fontFamily: 'var(--font-inter)', fontSize: '30px', fontWeight: 400, color: '#ffffff', marginBottom: '8px' }}>
        DATA SOURCES
      </h1>
      <p style={{ fontFamily: 'var(--font-inter)', fontSize: '13px', color: 'rgba(255,255,255,0.35)', marginBottom: '48px' }}>
        Configure credentials and search settings for each data source. Changes take effect immediately — no restart required.
      </p>

      {isLoading && <div style={{ color: 'rgba(255,255,255,0.35)', fontFamily: 'var(--font-geist-mono)', fontSize: '12px' }}>LOADING...</div>}
      {error && <div style={{ color: 'rgba(255,80,80,0.85)', fontFamily: 'var(--font-geist-mono)', fontSize: '12px' }}>Failed to load sources</div>}

      {sources && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
          {sources.map((s) => (
            <Link
              key={s.slug}
              href={`/settings/sources/${s.slug}`}
              style={{ textDecoration: 'none' }}
            >
              <div style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '16px 20px',
                background: 'rgba(255,255,255,0.03)',
                border: '1px solid rgba(255,255,255,0.08)',
                cursor: 'pointer',
              }}
              onMouseEnter={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.06)')}
              onMouseLeave={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.03)')}
              >
                <div>
                  <div style={{ fontFamily: 'var(--font-geist-mono)', fontSize: '13px', color: '#ffffff', marginBottom: '4px' }}>
                    {SOURCE_LABELS[s.slug] || s.slug}
                  </div>
                  <div style={{ fontFamily: 'var(--font-inter)', fontSize: '12px', color: 'rgba(255,255,255,0.35)' }}>
                    {SOURCE_DESCRIPTIONS[s.slug] || ''}
                  </div>
                  {s.last_success && (
                    <div style={{ fontFamily: 'var(--font-geist-mono)', fontSize: '10px', color: 'rgba(255,255,255,0.2)', marginTop: '4px' }}>
                      Last run: {new Date(s.last_success).toLocaleDateString()}
                    </div>
                  )}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                  <StatusChip configured={s.configured} last_success={s.last_success} />
                  <span style={{ color: 'rgba(255,255,255,0.25)', fontSize: '16px' }}>›</span>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
