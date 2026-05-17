'use client';
import useSWR from 'swr';
import Link from 'next/link';
import { endpoints, fetcher } from '@/lib/api';
import { NicheDetail } from '@/lib/types';

export default function NichePage({ params }: { params: { id: string } }) {
  const { id } = params;
  const { data, error, isLoading } = useSWR<NicheDetail>(
    endpoints.niche(id),
    fetcher,
    { refreshInterval: 60_000 }
  );

  if (error) return <StatusMessage text="NICHE NOT FOUND" />;
  if (isLoading || !data) return <StatusMessage text="LOADING..." />;

  const { niche, items } = data;

  return (
    <div>
      {/* Breadcrumb */}
      <div style={{ marginBottom: '48px' }}>
        <Link
          href="/"
          style={{
            fontFamily: 'var(--font-geist-mono)',
            fontSize: '12px',
            color: 'rgba(255,255,255,0.4)',
            textDecoration: 'none',
            textTransform: 'uppercase',
            letterSpacing: '0.8px',
          }}
        >
          ← DASHBOARD
        </Link>
      </div>

      {/* Header */}
      <div
        style={{
          borderBottom: '1px solid rgba(255,255,255,0.1)',
          paddingBottom: '48px',
          marginBottom: '48px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-end',
          flexWrap: 'wrap',
          gap: '24px',
        }}
      >
        <h1
          style={{
            fontFamily: 'var(--font-geist-mono)',
            fontSize: 'clamp(24px, 4vw, 56px)',
            fontWeight: 300,
            color: '#ffffff',
            textTransform: 'uppercase',
            letterSpacing: '2px',
            lineHeight: 1.1,
          }}
        >
          {niche.keyword}
        </h1>
        <div style={{ textAlign: 'right' }}>
          <div
            style={{
              fontFamily: 'var(--font-geist-mono)',
              fontSize: '72px',
              fontWeight: 300,
              color: '#ffffff',
              lineHeight: 1,
            }}
          >
            {niche.llm_score.toFixed(0)}
          </div>
          <div
            style={{
              fontFamily: 'var(--font-inter)',
              fontSize: '11px',
              color: 'rgba(255,255,255,0.35)',
              textTransform: 'uppercase',
              letterSpacing: '1px',
              marginTop: '4px',
            }}
          >
            AI SCORE
          </div>
        </div>
      </div>

      {/* AI analysis + meta */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
          gap: '48px',
          marginBottom: '48px',
        }}
      >
        <div>
          <SectionLabel>AI ANALYSIS</SectionLabel>
          <p
            style={{
              fontFamily: 'var(--font-inter)',
              fontSize: '14px',
              color: 'rgba(255,255,255,0.75)',
              lineHeight: 1.7,
            }}
          >
            {niche.llm_reasoning || 'No analysis available yet.'}
          </p>
        </div>
        <div>
          <SectionLabel>METADATA</SectionLabel>
          <MetaRow label="TIER" value={niche.tier.replace('_', ' ').toUpperCase()} />
          <MetaRow label="OCCURRENCES" value={String(niche.occurrence_count)} />
          <MetaRow
            label="FIRST SEEN"
            value={new Date(niche.first_seen).toLocaleDateString()}
          />
          <MetaRow
            label="LAST SEEN"
            value={new Date(niche.last_seen).toLocaleDateString()}
          />
        </div>
      </div>

      {/* Aliases */}
      {niche.aliases.length > 0 && (
        <div style={{ marginBottom: '48px' }}>
          <SectionLabel>RELATED TERMS</SectionLabel>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
            {niche.aliases.map((alias) => (
              <span
                key={alias}
                style={{
                  fontFamily: 'var(--font-geist-mono)',
                  fontSize: '11px',
                  color: '#ffffff',
                  border: '1px solid rgba(255,255,255,0.2)',
                  padding: '4px 12px',
                  textTransform: 'uppercase',
                  letterSpacing: '0.5px',
                }}
              >
                {alias}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Source items */}
      <div>
        <SectionLabel>SOURCE ITEMS ({items.length})</SectionLabel>
        {items.length === 0 ? (
          <div
            style={{
              border: '1px solid rgba(255,255,255,0.1)',
              padding: '32px',
              textAlign: 'center',
              fontFamily: 'var(--font-inter)',
              fontSize: '13px',
              color: 'rgba(255,255,255,0.3)',
            }}
          >
            No linked source items.
          </div>
        ) : (
          <div
            style={{
              border: '1px solid rgba(255,255,255,0.1)',
              display: 'flex',
              flexDirection: 'column',
            }}
          >
            {items.map((item, i) => (
              <div
                key={item.id}
                style={{
                  display: 'grid',
                  gridTemplateColumns: '80px 1fr 60px',
                  gap: '16px',
                  alignItems: 'center',
                  padding: '14px 20px',
                  borderBottom:
                    i < items.length - 1
                      ? '1px solid rgba(255,255,255,0.06)'
                      : 'none',
                  backgroundColor: 'rgba(255,255,255,0.02)',
                }}
              >
                <span
                  style={{
                    fontFamily: 'var(--font-geist-mono)',
                    fontSize: '10px',
                    color: 'rgba(255,255,255,0.35)',
                    textTransform: 'uppercase',
                    letterSpacing: '0.5px',
                  }}
                >
                  {item.source}
                </span>
                <div>
                  {item.url ? (
                    <a
                      href={item.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{
                        fontFamily: 'var(--font-inter)',
                        fontSize: '13px',
                        color: '#ffffff',
                        textDecoration: 'none',
                        display: 'block',
                        marginBottom: '3px',
                      }}
                    >
                      {item.title ?? item.source_id}
                    </a>
                  ) : (
                    <span
                      style={{
                        fontFamily: 'var(--font-inter)',
                        fontSize: '13px',
                        color: '#ffffff',
                        display: 'block',
                        marginBottom: '3px',
                      }}
                    >
                      {item.title ?? item.source_id}
                    </span>
                  )}
                </div>
                <span
                  style={{
                    fontFamily: 'var(--font-geist-mono)',
                    fontSize: '13px',
                    color: 'rgba(255,255,255,0.45)',
                    textAlign: 'right',
                  }}
                >
                  {item.score ?? 0}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        fontFamily: 'var(--font-inter)',
        fontSize: '11px',
        color: 'rgba(255,255,255,0.4)',
        textTransform: 'uppercase',
        letterSpacing: '1px',
        marginBottom: '16px',
        fontWeight: 400,
      }}
    >
      {children}
    </div>
  );
}

function MetaRow({ label, value }: { label: string; value: string }) {
  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        padding: '10px 0',
        borderBottom: '1px solid rgba(255,255,255,0.07)',
      }}
    >
      <span
        style={{
          fontFamily: 'var(--font-inter)',
          fontSize: '11px',
          color: 'rgba(255,255,255,0.35)',
          textTransform: 'uppercase',
          letterSpacing: '0.5px',
        }}
      >
        {label}
      </span>
      <span
        style={{
          fontFamily: 'var(--font-geist-mono)',
          fontSize: '12px',
          color: '#ffffff',
        }}
      >
        {value}
      </span>
    </div>
  );
}

function StatusMessage({ text }: { text: string }) {
  return (
    <div
      style={{
        padding: '96px 0',
        textAlign: 'center',
        fontFamily: 'var(--font-geist-mono)',
        fontSize: '13px',
        color: 'rgba(255,255,255,0.3)',
        textTransform: 'uppercase',
        letterSpacing: '1px',
      }}
    >
      {text}
    </div>
  );
}
