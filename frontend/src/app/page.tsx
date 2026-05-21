'use client';
import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import useSWR from 'swr';
import { endpoints, fetcher } from '@/lib/api';
import { LLMSettings, NicheScore, SystemStatus } from '@/lib/types';
import NicheCard from '@/components/NicheCard';
import SourceHealthTable from '@/components/SourceHealthTable';

export default function Dashboard() {
  const router = useRouter();

  const { data: settings } = useSWR<LLMSettings>(endpoints.settings, fetcher);

  useEffect(() => {
    if (settings && !settings.llm_api_key_set) {
      router.replace('/settings?onboarding=1');
    }
  }, [settings, router]);

  const { data: niches, error: nichesError, isLoading: nichesLoading } =
    useSWR<NicheScore[]>(endpoints.niches, fetcher, { refreshInterval: 30_000 });

  const { data: status } =
    useSWR<SystemStatus>(endpoints.status, fetcher, { refreshInterval: 30_000 });

  const highPriority = niches?.filter((n) => n.tier === 'high_priority') ?? [];
  const watchlist = niches?.filter((n) => n.tier === 'watchlist') ?? [];

  if (nichesError) {
    return (
      <div style={{ padding: '96px 0', textAlign: 'center' }}>
        <p
          style={{
            fontFamily: 'var(--font-geist-mono)',
            fontSize: '13px',
            color: 'rgba(255,255,255,0.35)',
            letterSpacing: '1px',
            textTransform: 'uppercase',
            marginBottom: '24px',
          }}
        >
          CANNOT CONNECT TO API — IS THE BACKEND RUNNING ON PORT 8000?
        </p>
      </div>
    );
  }

  return (
    <div>
      {/* Stats strip + pipeline CTA */}
      {/* high_priority = quick-win + high-score (build≤2, score≥80). watchlist = score 65-79. */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          paddingBottom: '48px',
          marginBottom: '48px',
          borderBottom: '1px solid rgba(255,255,255,0.1)',
          flexWrap: 'wrap',
          gap: '32px',
        }}
      >
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '48px' }}>
          {status ? (
            <>
              <Stat label="OPPORTUNITIES" value={status.active_niches} />
              <Stat label="RAW ITEMS" value={status.raw_items.toLocaleString()} />
              <Stat label="CYCLES" value={status.collection_cycle} />
              <Stat
                label="LAST COLLECTION"
                value={
                  status.last_collection
                    ? new Date(status.last_collection).toLocaleString()
                    : 'NEVER'
                }
              />
            </>
          ) : null}
        </div>
        <Link
          href="/pipeline"
          style={{
            fontFamily: 'var(--font-geist-mono)',
            fontSize: '11px',
            fontWeight: 600,
            color: '#1f2228',
            backgroundColor: '#ffffff',
            textDecoration: 'none',
            letterSpacing: '1px',
            textTransform: 'uppercase',
            padding: '0 20px',
            height: '40px',
            display: 'inline-flex',
            alignItems: 'center',
            flexShrink: 0,
          }}
        >
          OPEN PIPELINE →
        </Link>
      </div>

      {/* High priority */}
      <section style={{ marginBottom: '64px' }}>
        <SectionHeading label="HIGH PRIORITY" count={highPriority.length} note="SCORE ≥ 80 · BUILD NOW" />
        {nichesLoading ? (
          <LoadingGrid />
        ) : highPriority.length === 0 ? (
          <EmptySection href="/pipeline" cta="RUN PIPELINE" />
        ) : (
          <NicheGrid niches={highPriority} />
        )}
      </section>

      {/* Watchlist */}
      <section style={{ marginBottom: '64px' }}>
        <SectionHeading label="WATCHLIST" count={watchlist.length} note="SCORE 65–79 · MONITOR" />
        {nichesLoading ? (
          <LoadingGrid />
        ) : watchlist.length === 0 ? (
          <EmptySection href="/pipeline" cta="RUN PIPELINE" />
        ) : (
          <NicheGrid niches={watchlist} />
        )}
      </section>

      {/* Freshness rules */}
      {status?.freshness && (
        <section style={{ marginBottom: '64px' }}>
          <SectionHeading
            label="DATA FRESHNESS"
            count={null}
            note={`ANALYSIS WINDOW · LAST ${status.freshness.analysis_window_days} DAYS`}
          />
          <div
            style={{
              border: '1px solid rgba(255,255,255,0.1)',
              padding: '20px 24px',
              fontFamily: 'var(--font-geist-mono)',
              fontSize: '11px',
              color: 'rgba(255,255,255,0.6)',
              lineHeight: 1.8,
            }}
          >
            <div style={{ marginBottom: '14px', color: 'rgba(255,255,255,0.45)', fontSize: '10px', letterSpacing: '1px', textTransform: 'uppercase' }}>
              COLLECTION RULES — items older than these windows are dropped at collection time
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px', marginBottom: '20px' }}>
              <span>REDDIT &nbsp;<span style={{ color: 'rgba(74,222,128,0.85)' }}>≤ {status.freshness.rules.reddit_hours}h</span></span>
              <span>HN &nbsp;<span style={{ color: 'rgba(74,222,128,0.85)' }}>≤ {status.freshness.rules.hn_hours}h</span></span>
              <span>GITHUB &nbsp;<span style={{ color: 'rgba(74,222,128,0.85)' }}>≤ {status.freshness.rules.github_hours}h</span></span>
              <span>GOOGLE TRENDS &nbsp;<span style={{ color: 'rgba(74,222,128,0.85)' }}>≤ {status.freshness.rules.google_trends_hours}h</span></span>
              <span>YOUTUBE &nbsp;<span style={{ color: 'rgba(74,222,128,0.85)' }}>≤ {status.freshness.rules.youtube_hours}h</span></span>
            </div>
            {status.freshness.per_source.length > 0 && (
              <>
                <div style={{ marginBottom: '8px', color: 'rgba(255,255,255,0.45)', fontSize: '10px', letterSpacing: '1px', textTransform: 'uppercase' }}>
                  CURRENT CORPUS — newest item age per source
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '8px' }}>
                  {status.freshness.per_source.map((s) => (
                    <span key={s.source}>
                      {s.source.toUpperCase()} &nbsp;
                      <span
                        style={{
                          color: (s.newest_age_hours ?? 999) <= 24
                            ? 'rgba(74,222,128,0.85)'
                            : (s.newest_age_hours ?? 999) <= 72
                              ? 'rgba(251,191,36,0.85)'
                              : 'rgba(255,140,140,0.85)',
                        }}
                      >
                        {s.newest_age_hours !== null ? `${s.newest_age_hours.toFixed(0)}h ago` : '—'}
                      </span>
                      <span style={{ color: 'rgba(255,255,255,0.3)' }}> · {s.items} items</span>
                    </span>
                  ))}
                </div>
              </>
            )}
          </div>
        </section>
      )}

      {/* System health */}
      {status && (
        <section>
          <SectionHeading label="SYSTEM HEALTH" count={null} note={null} />
          <SourceHealthTable sources={status.sources} />
        </section>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <div>
      <div
        style={{
          fontFamily: 'var(--font-inter)',
          fontSize: '11px',
          color: 'rgba(255,255,255,0.4)',
          marginBottom: '8px',
          textTransform: 'uppercase',
          letterSpacing: '0.6px',
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontFamily: 'var(--font-geist-mono)',
          fontSize: '28px',
          fontWeight: 300,
          color: '#ffffff',
          lineHeight: 1,
        }}
      >
        {value}
      </div>
    </div>
  );
}

function SectionHeading({
  label,
  count,
  note,
}: {
  label: string;
  count: number | null;
  note: string | null;
}) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'baseline',
        gap: '16px',
        marginBottom: '24px',
      }}
    >
      <h2
        style={{
          fontFamily: 'var(--font-inter)',
          fontSize: '30px',
          fontWeight: 400,
          color: '#ffffff',
          lineHeight: 1.2,
        }}
      >
        {label}
      </h2>
      {count !== null && (
        <span
          style={{
            fontFamily: 'var(--font-geist-mono)',
            fontSize: '13px',
            color: 'rgba(255,255,255,0.35)',
          }}
        >
          {count}
        </span>
      )}
      {note && (
        <span
          style={{
            fontFamily: 'var(--font-geist-mono)',
            fontSize: '11px',
            color: 'rgba(255,255,255,0.25)',
            textTransform: 'uppercase',
            letterSpacing: '0.5px',
          }}
        >
          {note}
        </span>
      )}
    </div>
  );
}

function NicheGrid({ niches }: { niches: NicheScore[] }) {
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))',
        gap: '1px',
        backgroundColor: 'rgba(255,255,255,0.08)',
      }}
    >
      {niches.map((n) => (
        <NicheCard key={n.niche_id} niche={n} />
      ))}
    </div>
  );
}

function EmptySection({ href, cta }: { href: string; cta: string }) {
  return (
    <div
      style={{
        border: '1px solid rgba(255,255,255,0.08)',
        padding: '48px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '24px',
      }}
    >
      <span
        style={{
          fontFamily: 'var(--font-inter)',
          fontSize: '13px',
          color: 'rgba(255,255,255,0.25)',
        }}
      >
        No data yet.
      </span>
      <Link
        href={href}
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
        {cta} →
      </Link>
    </div>
  );
}

function LoadingGrid() {
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))',
        gap: '1px',
        backgroundColor: 'rgba(255,255,255,0.08)',
      }}
    >
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          style={{
            backgroundColor: 'rgba(255,255,255,0.03)',
            height: '200px',
          }}
        />
      ))}
    </div>
  );
}
