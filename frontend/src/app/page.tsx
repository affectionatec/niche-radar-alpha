'use client';
import useSWR from 'swr';
import { endpoints, fetcher } from '@/lib/api';
import { NicheScore, SystemStatus } from '@/lib/types';
import NicheCard from '@/components/NicheCard';
import SourceHealthTable from '@/components/SourceHealthTable';

export default function Dashboard() {
  const { data: niches, error: nichesError, isLoading: nichesLoading } =
    useSWR<NicheScore[]>(endpoints.niches, fetcher, { refreshInterval: 30_000 });

  const { data: status } =
    useSWR<SystemStatus>(endpoints.status, fetcher, { refreshInterval: 30_000 });

  const highPriority = niches?.filter((n) => n.tier === 'high_priority') ?? [];
  const watchlist = niches?.filter((n) => n.tier === 'watchlist') ?? [];

  if (nichesError) {
    return (
      <div style={{ padding: '96px 0', textAlign: 'center' }}>
        <p style={{
          fontFamily: 'var(--font-geist-mono)',
          fontSize: '13px',
          color: 'rgba(255,255,255,0.35)',
          letterSpacing: '1px',
          textTransform: 'uppercase',
        }}>
          CANNOT CONNECT TO API — IS THE BACKEND RUNNING ON PORT 8000?
        </p>
      </div>
    );
  }

  return (
    <div>
      {/* Stats strip */}
      {status && (
        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: '48px',
            paddingBottom: '48px',
            marginBottom: '48px',
            borderBottom: '1px solid rgba(255,255,255,0.1)',
          }}
        >
          <Stat label="ACTIVE NICHES" value={status.active_niches} />
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
        </div>
      )}

      {/* High priority */}
      <section style={{ marginBottom: '64px' }}>
        <SectionHeading label="HIGH PRIORITY" count={highPriority.length} note="SCORE ≥ 80" />
        {nichesLoading ? (
          <LoadingGrid />
        ) : highPriority.length === 0 ? (
          <EmptyState message="No high-priority niches yet. Run: python -m niche_radar collect && extract && score" />
        ) : (
          <NicheGrid niches={highPriority} />
        )}
      </section>

      {/* Watchlist */}
      <section style={{ marginBottom: '64px' }}>
        <SectionHeading label="WATCHLIST" count={watchlist.length} note="SCORE 65–79" />
        {nichesLoading ? (
          <LoadingGrid />
        ) : watchlist.length === 0 ? (
          <EmptyState message="No watchlist niches yet." />
        ) : (
          <NicheGrid niches={watchlist} />
        )}
      </section>

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

function EmptyState({ message }: { message: string }) {
  return (
    <div
      style={{
        border: '1px solid rgba(255,255,255,0.1)',
        padding: '48px',
        textAlign: 'center',
        fontFamily: 'var(--font-inter)',
        fontSize: '13px',
        color: 'rgba(255,255,255,0.35)',
        fontStyle: 'italic',
      }}
    >
      {message}
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
