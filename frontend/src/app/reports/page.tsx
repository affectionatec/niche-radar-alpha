'use client';
import { useState } from 'react';
import useSWR from 'swr';
import Link from 'next/link';
import { endpoints, fetcher } from '@/lib/api';
import { ReportFile } from '@/lib/types';

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export default function ReportsPage() {
  const [selected, setSelected] = useState<string | null>(null);

  const { data: reports, error, isLoading } =
    useSWR<ReportFile[]>(endpoints.reports, fetcher, { refreshInterval: 30_000 });

  const { data: content, isLoading: contentLoading } = useSWR<{ content: string }>(
    selected ? endpoints.reportContent(selected) : null,
    fetcher,
  );

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
          flexWrap: 'wrap',
          gap: '16px',
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
          REPORTS
          {reports && (
            <span
              style={{
                fontFamily: 'var(--font-geist-mono)',
                fontSize: '13px',
                color: 'rgba(255,255,255,0.35)',
                marginLeft: '16px',
              }}
            >
              {reports.length}
            </span>
          )}
        </h1>
        <Link
          href="/pipeline"
          style={{
            fontFamily: 'var(--font-geist-mono)',
            fontSize: '11px',
            color: 'rgba(255,255,255,0.5)',
            textDecoration: 'none',
            border: '1px solid rgba(255,255,255,0.15)',
            padding: '8px 14px',
            letterSpacing: '0.8px',
            textTransform: 'uppercase',
          }}
        >
          GENERATE REPORT →
        </Link>
      </div>

      {isLoading ? (
        <LoadingSkeleton />
      ) : !reports || reports.length === 0 ? (
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
            No reports yet.
          </span>
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
            GENERATE REPORT →
          </Link>
        </div>
      ) : (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: selected ? '280px 1fr' : '1fr',
            gap: '1px',
            backgroundColor: 'rgba(255,255,255,0.08)',
            alignItems: 'start',
          }}
        >
          <div style={{ backgroundColor: '#1f2228' }}>
            {reports.map((r) => (
              <button
                key={r.filename}
                onClick={() => setSelected(selected === r.filename ? null : r.filename)}
                style={{
                  width: '100%',
                  background:
                    r.filename === selected
                      ? 'rgba(255,255,255,0.07)'
                      : 'transparent',
                  border: 'none',
                  borderBottom: '1px solid rgba(255,255,255,0.05)',
                  padding: '14px 16px',
                  textAlign: 'left',
                  cursor: 'pointer',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '4px',
                }}
              >
                <span
                  style={{
                    fontFamily: 'var(--font-geist-mono)',
                    fontSize: '12px',
                    color: r.filename === selected ? '#ffffff' : 'rgba(255,255,255,0.75)',
                    display: 'block',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {r.filename}
                </span>
                <span
                  style={{
                    fontFamily: 'var(--font-inter)',
                    fontSize: '11px',
                    color: 'rgba(255,255,255,0.3)',
                  }}
                >
                  {formatSize(r.size)} ·{' '}
                  {new Date(r.modified * 1000).toLocaleDateString()}
                </span>
              </button>
            ))}
          </div>

          {selected && (
            <div
              style={{
                backgroundColor: '#1f2228',
                padding: '24px',
                minHeight: '400px',
              }}
            >
              {contentLoading ? (
                <span
                  style={{
                    fontFamily: 'var(--font-geist-mono)',
                    fontSize: '12px',
                    color: 'rgba(255,255,255,0.3)',
                  }}
                >
                  Loading...
                </span>
              ) : content ? (
                <pre
                  style={{
                    fontFamily: 'var(--font-geist-mono)',
                    fontSize: '12px',
                    color: 'rgba(255,255,255,0.8)',
                    lineHeight: 1.7,
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                    margin: 0,
                  }}
                >
                  {content.content}
                </pre>
              ) : null}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div style={{ border: '1px solid rgba(255,255,255,0.1)' }}>
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          style={{
            height: '60px',
            borderBottom: '1px solid rgba(255,255,255,0.05)',
            backgroundColor: 'rgba(255,255,255,0.02)',
          }}
        />
      ))}
    </div>
  );
}
