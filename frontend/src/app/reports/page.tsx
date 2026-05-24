'use client';
import { useState } from 'react';
import useSWR from 'swr';
import Link from 'next/link';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { endpoints, fetcher } from '@/lib/api';
import { ReportFile } from '@/lib/types';
import { color, font } from '@/lib/tokens';

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function downloadMarkdown(filename: string, body: string) {
  const blob = new Blob([body], { type: 'text/markdown;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
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
      <div style={{ padding: '96px 0', textAlign: 'center' as const }}>
        <p
          style={{
            fontFamily: font.mono,
            fontSize: '12px',
            color: color.fgGhost,
            letterSpacing: '0.8px',
            textTransform: 'uppercase' as const,
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
            fontFamily: font.body,
            fontSize: '30px',
            fontWeight: 400,
            color: color.fg,
          }}
        >
          REPORTS
          {reports && (
            <span
              style={{
                fontFamily: font.mono,
                fontSize: '13px',
                color: color.fgDisabled,
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
            fontFamily: font.mono,
            fontSize: '11px',
            color: color.fgMuted,
            textDecoration: 'none',
            border: `1px solid ${color.borderStrong}`,
            padding: '8px 14px',
            letterSpacing: '0.8px',
            textTransform: 'uppercase' as const,
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
            border: `1px solid ${color.surfaceActive}`,
            padding: '48px',
            textAlign: 'center' as const,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '20px',
          }}
        >
          <span
            style={{
              fontFamily: font.body,
              fontSize: '13px',
              color: color.fgGhost,
            }}
          >
            No reports yet.
          </span>
          <Link
            href="/pipeline"
            style={{
              fontFamily: font.mono,
              fontSize: '11px',
              color: color.fgSecondary,
              textDecoration: 'none',
              border: `1px solid ${color.borderStrong}`,
              padding: '8px 16px',
              letterSpacing: '0.8px',
              textTransform: 'uppercase' as const,
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
            backgroundColor: color.surfaceActive,
            alignItems: 'start',
          }}
        >
          <div style={{ backgroundColor: color.bg }}>
            {reports.map((r) => (
              <button
                key={r.filename}
                onClick={() => setSelected(selected === r.filename ? null : r.filename)}
                style={{
                  width: '100%',
                  background:
                    r.filename === selected
                      ? color.surfaceHover
                      : 'transparent',
                  border: 'none',
                  borderBottom: `1px solid ${color.surfaceHover}`,
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
                    fontFamily: font.mono,
                    fontSize: '12px',
                    color: r.filename === selected ? color.fg : color.fgSecondary,
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
                    fontFamily: font.body,
                    fontSize: '11px',
                    color: color.fgGhost,
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
                backgroundColor: color.bg,
                padding: '32px 36px',
                minHeight: '400px',
              }}
            >
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'flex-end',
                  marginBottom: '16px',
                }}
              >
                <button
                  onClick={() => content && downloadMarkdown(selected, content.content)}
                  disabled={!content}
                  style={{
                    background: 'transparent',
                    border: `1px solid ${color.borderStrong}`,
                    color: color.fgSecondary,
                    fontFamily: font.mono,
                    fontSize: '11px',
                    letterSpacing: '0.8px',
                    textTransform: 'uppercase' as const,
                    padding: '6px 14px',
                    cursor: content ? 'pointer' : 'not-allowed',
                    opacity: content ? 1 : 0.4,
                  }}
                >
                  ↓ DOWNLOAD .MD
                </button>
              </div>
              {contentLoading ? (
                <span
                  style={{
                    fontFamily: font.mono,
                    fontSize: '12px',
                    color: color.fgGhost,
                  }}
                >
                  Loading...
                </span>
              ) : content ? (
                <article className="report-markdown">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{content.content}</ReactMarkdown>
                </article>
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
    <div style={{ border: `1px solid ${color.border}` }}>
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          style={{
            height: '60px',
            borderBottom: `1px solid ${color.surfaceHover}`,
            backgroundColor: color.surface,
          }}
        />
      ))}
    </div>
  );
}
