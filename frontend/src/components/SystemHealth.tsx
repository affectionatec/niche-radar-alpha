'use client';

import Link from 'next/link';
import { SourceHealth, Job, JobStatus } from '@/lib/types';

interface SystemHealthProps {
  sources: SourceHealth[];
  recentJobs?: Job[];
}

function statusDot(status: string): { color: string; label: string } {
  switch (status) {
    case 'OK':
      return { color: 'rgba(74,222,128,0.8)', label: 'OK' };
    case 'FAILED':
    case 'PARTIAL':
      return { color: 'rgba(255,80,80,0.8)', label: status };
    case 'RUNNING':
      return { color: 'rgba(251,191,36,0.8)', label: 'RUNNING' };
    case 'MISSING':
    default:
      return { color: 'rgba(255,255,255,0.2)', label: 'NOT RUN' };
  }
}

function jobStatusColor(status: JobStatus): string {
  if (status === 'done') return 'rgba(74,222,128,0.7)';
  if (status === 'failed') return 'rgba(255,80,80,0.7)';
  if (status === 'running') return 'rgba(251,191,36,0.8)';
  return 'rgba(255,255,255,0.3)';
}

function timeAgo(dateStr: string): string {
  if (!dateStr || dateStr === '-') return 'never';
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

const SOURCE_ICONS: Record<string, string> = {
  reddit: '◆',
  hn: '▲',
  github: '◎',
  google_trends: '◇',
  youtube: '▶',
};

export default function SystemHealth({ sources, recentJobs }: SystemHealthProps) {
  const okCount = sources.filter(s => s.status === 'OK').length;
  const totalCount = sources.length;
  const failedSources = sources.filter(s => s.status === 'FAILED' || s.status === 'PARTIAL');

  const overallStatus = failedSources.length > 0
    ? { color: 'rgba(255,80,80,0.8)', label: `${failedSources.length} FAILED` }
    : okCount === 0
      ? { color: 'rgba(255,255,255,0.25)', label: 'NO RUNS' }
      : okCount === totalCount
        ? { color: 'rgba(74,222,128,0.8)', label: 'ALL OK' }
        : { color: 'rgba(251,191,36,0.8)', label: `${okCount}/${totalCount} OK` };

  // Most recent jobs (limit 3)
  const latestJobs = (recentJobs ?? []).slice(0, 3);

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      gap: '16px',
    }}>
      {/* Source cards grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
        gap: '1px',
        background: 'rgba(255,255,255,0.06)',
      }}>
        {sources.map((s) => {
          const dot = statusDot(s.status);
          const icon = SOURCE_ICONS[s.source] ?? '·';

          return (
            <Link
              key={s.source}
              href={`/settings/sources/${s.source}`}
              style={{ textDecoration: 'none', display: 'block' }}
            >
              <div style={{
                background: '#1f2228',
                padding: '18px 20px',
                display: 'flex',
                flexDirection: 'column',
                gap: '12px',
                cursor: 'pointer',
                transition: 'background 0.2s',
              }}
                onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(255,255,255,0.03)'; }}
                onMouseLeave={(e) => { e.currentTarget.style.background = '#1f2228'; }}
              >
                {/* Source header */}
                <div style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{
                      fontFamily: 'var(--font-geist-mono)',
                      fontSize: '12px',
                      color: 'rgba(255,255,255,0.3)',
                    }}>
                      {icon}
                    </span>
                    <span style={{
                      fontFamily: 'var(--font-geist-mono)',
                      fontSize: '11px',
                      letterSpacing: '0.8px',
                      textTransform: 'uppercase',
                      color: '#ffffff',
                    }}>
                      {s.source.replace('_', ' ')}
                    </span>
                  </div>
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                  }}>
                    <div style={{
                      width: '6px',
                      height: '6px',
                      borderRadius: '50%',
                      background: dot.color,
                    }} />
                    <span style={{
                      fontFamily: 'var(--font-geist-mono)',
                      fontSize: '9px',
                      letterSpacing: '0.5px',
                      color: dot.color,
                      textTransform: 'uppercase',
                    }}>
                      {dot.label}
                    </span>
                  </div>
                </div>

                {/* Stats row */}
                <div style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'flex-end',
                }}>
                  <div>
                    <div style={{
                      fontFamily: 'var(--font-geist-mono)',
                      fontSize: '20px',
                      fontWeight: 300,
                      color: '#ffffff',
                      lineHeight: 1,
                    }}>
                      {s.items > 0 ? s.items.toLocaleString() : '—'}
                    </div>
                    <div style={{
                      fontFamily: 'var(--font-inter)',
                      fontSize: '9px',
                      color: 'rgba(255,255,255,0.3)',
                      textTransform: 'uppercase',
                      letterSpacing: '0.5px',
                      marginTop: '4px',
                    }}>
                      items collected
                    </div>
                  </div>
                  <span style={{
                    fontFamily: 'var(--font-inter)',
                    fontSize: '10px',
                    color: 'rgba(255,255,255,0.35)',
                  }}>
                    {timeAgo(s.last_run)}
                  </span>
                </div>
              </div>
            </Link>
          );
        })}
      </div>

      {/* Recent pipeline runs */}
      {latestJobs.length > 0 && (
        <div style={{
          border: '1px solid rgba(255,255,255,0.06)',
        }}>
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: '10px 20px',
            borderBottom: '1px solid rgba(255,255,255,0.04)',
          }}>
            <span style={{
              fontFamily: 'var(--font-geist-mono)',
              fontSize: '10px',
              letterSpacing: '1px',
              color: 'rgba(255,255,255,0.3)',
              textTransform: 'uppercase',
            }}>
              Recent Pipeline Runs
            </span>
            <Link
              href="/pipeline"
              style={{
                fontFamily: 'var(--font-geist-mono)',
                fontSize: '10px',
                letterSpacing: '0.5px',
                color: 'rgba(255,255,255,0.35)',
                textDecoration: 'none',
                textTransform: 'uppercase',
              }}
            >
              VIEW ALL →
            </Link>
          </div>
          {latestJobs.map((job, i) => (
            <Link
              key={job.id}
              href="/pipeline"
              style={{ textDecoration: 'none', display: 'block' }}
            >
              <div style={{
                display: 'grid',
                gridTemplateColumns: '80px 1fr 80px',
                padding: '8px 20px',
                alignItems: 'center',
                borderBottom: i < latestJobs.length - 1 ? '1px solid rgba(255,255,255,0.03)' : 'none',
                cursor: 'pointer',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <div style={{
                    width: '5px',
                    height: '5px',
                    borderRadius: '50%',
                    background: jobStatusColor(job.status),
                  }} />
                  <span style={{
                    fontFamily: 'var(--font-geist-mono)',
                    fontSize: '11px',
                    textTransform: 'uppercase',
                    letterSpacing: '0.5px',
                    color: 'rgba(255,255,255,0.6)',
                  }}>
                    {job.step}
                  </span>
                </div>
                <span style={{
                  fontFamily: 'var(--font-inter)',
                  fontSize: '11px',
                  color: 'rgba(255,255,255,0.3)',
                }}>
                  {timeAgo(job.created_at)}
                </span>
                <span style={{
                  fontFamily: 'var(--font-geist-mono)',
                  fontSize: '10px',
                  letterSpacing: '0.5px',
                  color: jobStatusColor(job.status),
                  textTransform: 'uppercase',
                  textAlign: 'right',
                }}>
                  {job.status}
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}

      {/* Overall status footer */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: '0 4px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{
            width: '6px',
            height: '6px',
            borderRadius: '50%',
            background: overallStatus.color,
          }} />
          <span style={{
            fontFamily: 'var(--font-geist-mono)',
            fontSize: '10px',
            letterSpacing: '0.8px',
            color: overallStatus.color,
            textTransform: 'uppercase',
          }}>
            {overallStatus.label}
          </span>
        </div>
        <Link
          href="/settings/sources"
          style={{
            fontFamily: 'var(--font-geist-mono)',
            fontSize: '10px',
            letterSpacing: '0.5px',
            color: 'rgba(255,255,255,0.3)',
            textDecoration: 'none',
            textTransform: 'uppercase',
          }}
        >
          CONFIGURE SOURCES →
        </Link>
      </div>
    </div>
  );
}
