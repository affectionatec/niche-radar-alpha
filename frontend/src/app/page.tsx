'use client';
import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import useSWR from 'swr';
import { endpoints, fetcher } from '@/lib/api';
import { Job, LLMSettings, NicheScore, SystemStatus } from '@/lib/types';
import { color, font, fontSize, spacing } from '@/lib/tokens';
import NicheCard from '@/components/NicheCard';
import DataFreshness from '@/components/DataFreshness';
import SystemHealth from '@/components/SystemHealth';

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

  const { data: jobs } =
    useSWR<Job[]>(endpoints.jobs, fetcher, { refreshInterval: 15_000 });

  const highPriority = niches?.filter((n) => n.tier === 'high_priority') ?? [];
  const watchlist = niches?.filter((n) => n.tier === 'watchlist') ?? [];

  if (nichesError) {
    return (
      <div style={{ padding: '96px 0', textAlign: 'center' }}>
        <p
          style={{
            fontFamily: font.mono,
            fontSize: fontSize.lg,
            color: color.fgDisabled,
            letterSpacing: '1px',
            textTransform: 'uppercase' as const,
            marginBottom: spacing['2xl'],
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
          paddingBottom: spacing['4xl'],
          marginBottom: spacing['4xl'],
          borderBottom: `1px solid ${color.border}`,
          flexWrap: 'wrap' as const,
          gap: spacing['3xl'],
        }}
      >
        <div style={{ display: 'flex', flexWrap: 'wrap' as const, gap: spacing['4xl'] }}>
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
            fontFamily: font.mono,
            fontSize: fontSize.base,
            fontWeight: 600,
            color: color.bg,
            backgroundColor: color.fg,
            textDecoration: 'none',
            letterSpacing: '1px',
            textTransform: 'uppercase' as const,
            padding: `0 ${spacing.xl}`,
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
      <section style={{ marginBottom: spacing['5xl'] }}>
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
      <section style={{ marginBottom: spacing['5xl'] }}>
        <SectionHeading label="WATCHLIST" count={watchlist.length} note="SCORE 65–79 · MONITOR" />
        {nichesLoading ? (
          <LoadingGrid />
        ) : watchlist.length === 0 ? (
          <EmptySection href="/pipeline" cta="RUN PIPELINE" />
        ) : (
          <NicheGrid niches={watchlist} />
        )}
      </section>

      {/* Data freshness */}
      {status?.freshness && (
        <section style={{ marginBottom: spacing['5xl'] }}>
          <SectionHeading
            label="DATA FRESHNESS"
            count={null}
            note={null}
          />
          <DataFreshness freshness={status.freshness} />
        </section>
      )}

      {/* System health */}
      {status && (
        <section>
          <SectionHeading label="SYSTEM HEALTH" count={null} note={null} />
          <SystemHealth sources={status.sources} recentJobs={jobs} />
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
          fontFamily: font.body,
          fontSize: fontSize.base,
          color: color.fgMuted,
          marginBottom: spacing.sm,
          textTransform: 'uppercase' as const,
          letterSpacing: '0.6px',
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontFamily: font.mono,
          fontSize: fontSize['4xl'],
          fontWeight: 300,
          color: color.fg,
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
        gap: spacing.lg,
        marginBottom: spacing['2xl'],
      }}
    >
      <h2
        style={{
          fontFamily: font.body,
          fontSize: fontSize['5xl'],
          fontWeight: 400,
          color: color.fg,
          lineHeight: 1.2,
        }}
      >
        {label}
      </h2>
      {count !== null && (
        <span
          style={{
            fontFamily: font.mono,
            fontSize: fontSize.lg,
            color: color.fgDisabled,
          }}
        >
          {count}
        </span>
      )}
      {note && (
        <span
          style={{
            fontFamily: font.mono,
            fontSize: fontSize.base,
            color: color.fgGhost,
            textTransform: 'uppercase' as const,
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
        backgroundColor: color.surfaceActive,
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
        border: `1px solid ${color.surfaceActive}`,
        padding: spacing['4xl'],
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: spacing['2xl'],
      }}
    >
      <span
        style={{
          fontFamily: font.body,
          fontSize: fontSize.lg,
          color: color.fgGhost,
        }}
      >
        No data yet.
      </span>
      <Link
        href={href}
        style={{
          fontFamily: font.mono,
          fontSize: fontSize.base,
          color: color.fgSecondary,
          textDecoration: 'none',
          border: `1px solid ${color.borderStrong}`,
          padding: `${spacing.sm} ${spacing.lg}`,
          letterSpacing: '0.8px',
          textTransform: 'uppercase' as const,
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
        backgroundColor: color.surfaceActive,
      }}
    >
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          style={{
            backgroundColor: color.surface,
            height: '200px',
          }}
        />
      ))}
    </div>
  );
}
