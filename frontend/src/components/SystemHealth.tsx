'use client';

import Link from 'next/link';
import { SourceHealth, Job, JobStatus } from '@/lib/types';
import { color, font, fontSize, sourceIcon, sourceLabel, sourceReliability } from '@/lib/tokens';

interface SystemHealthProps {
  sources: SourceHealth[];
  recentJobs?: Job[];
}

function statusDot(status: string): { color: string; label: string } {
  switch (status) {
    case 'OK':
      return { color: color.success, label: 'OK' };
    case 'FAILED':
    case 'PARTIAL':
      return { color: color.error, label: status };
    case 'RUNNING':
      return { color: color.warning, label: 'RUNNING' };
    case 'MISSING':
    default:
      return { color: color.fgGhost, label: 'NOT RUN' };
  }
}

function jobStatusColor(status: JobStatus): string {
  if (status === 'done') return color.successMuted;
  if (status === 'failed') return color.errorMuted;
  if (status === 'running') return color.warning;
  return color.fgDisabled;
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

export default function SystemHealth({ sources, recentJobs }: SystemHealthProps) {
  const okCount = sources.filter(s => s.status === 'OK').length;
  const totalCount = sources.length;
  const failedSources = sources.filter(s => s.status === 'FAILED' || s.status === 'PARTIAL');

  const overallStatus = failedSources.length > 0
    ? { color: color.error, label: `${failedSources.length} FAILED` }
    : okCount === 0
      ? { color: color.fgGhost, label: 'NO RUNS' }
      : okCount === totalCount
        ? { color: color.success, label: 'ALL OK' }
        : { color: color.warning, label: `${okCount}/${totalCount} OK` };

  const latestJobs = (recentJobs ?? []).slice(0, 3);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      {/* Source cards — balanced 4-column grid (4×3 for 12 sources) */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(4, 1fr)',
        gap: '1px',
        background: color.surfaceHover,
      }}>
        {sources.map((s) => {
          const dot = statusDot(s.status);
          const icon = sourceIcon[s.source] ?? '·';
          const reliability = sourceReliability[s.source];

          return (
            <Link
              key={s.source}
              href={`/settings/sources/${s.source}`}
              style={{ textDecoration: 'none', display: 'block' }}
            >
              <div style={{
                background: color.bg,
                padding: '16px 18px',
                display: 'flex',
                flexDirection: 'column',
                gap: '10px',
                cursor: 'pointer',
                transition: 'background 0.15s',
                minHeight: '120px',
              }}
                onMouseEnter={(e) => { e.currentTarget.style.background = color.surface; }}
                onMouseLeave={(e) => { e.currentTarget.style.background = color.bg; }}
              >
                {/* Source header */}
                <div style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0 }}>
                    <span style={{ fontFamily: font.mono, fontSize: fontSize.md, color: color.fgDisabled }}>
                      {icon}
                    </span>
                    <span style={{
                      fontFamily: font.mono, fontSize: fontSize.base,
                      letterSpacing: '0.8px', textTransform: 'uppercase' as const,
                      color: color.fg,
                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const,
                    }}>
                      {sourceLabel[s.source] || s.source.replace(/_/g, ' ')}
                    </span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexShrink: 0 }}>
                    <div style={{
                      width: '6px', height: '6px', borderRadius: '50%',
                      background: dot.color,
                    }} />
                    <span style={{
                      fontFamily: font.mono, fontSize: fontSize.xs,
                      letterSpacing: '0.5px', color: dot.color,
                      textTransform: 'uppercase' as const,
                    }}>
                      {dot.label}
                    </span>
                  </div>
                </div>

                {/* Stats row */}
                <div style={{
                  display: 'flex', justifyContent: 'space-between',
                  alignItems: 'flex-end', flex: 1,
                }}>
                  <div>
                    <div style={{
                      fontFamily: font.mono, fontSize: '20px', fontWeight: 300,
                      color: color.fg, lineHeight: 1,
                    }}>
                      {s.items > 0 ? s.items.toLocaleString() : '—'}
                    </div>
                    <div style={{
                      fontFamily: font.body, fontSize: fontSize.xs,
                      color: color.fgDisabled, textTransform: 'uppercase' as const,
                      letterSpacing: '0.5px', marginTop: '4px',
                    }}>
                      items collected
                    </div>
                  </div>
                  <span style={{ fontFamily: font.body, fontSize: fontSize.sm, color: color.fgDisabled }}>
                    {timeAgo(s.last_run)}
                  </span>
                </div>

                {/* Reliability badge */}
                {reliability && (
                  <div style={{
                    display: 'flex', alignItems: 'center', gap: '6px',
                    borderTop: `1px solid rgba(255,255,255,0.04)`,
                    paddingTop: '8px',
                    minWidth: 0,
                  }}>
                    <span style={{ fontSize: fontSize.sm, flexShrink: 0 }}>{reliability.icon}</span>
                    <span style={{
                      fontFamily: font.mono, fontSize: fontSize.xs,
                      letterSpacing: '0.5px', color: reliability.color,
                      textTransform: 'uppercase' as const,
                      whiteSpace: 'nowrap' as const, flexShrink: 0,
                    }}>
                      {reliability.label}
                    </span>
                    <span style={{
                      fontFamily: font.body, fontSize: fontSize.xs,
                      color: color.fgGhost, marginLeft: 'auto',
                      overflow: 'hidden', textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap' as const, minWidth: 0,
                    }}>
                      {reliability.note}
                    </span>
                  </div>
                )}
              </div>
            </Link>
          );
        })}
      </div>

      {/* Recent pipeline runs */}
      {latestJobs.length > 0 && (
        <div style={{ border: `1px solid ${color.surfaceHover}` }}>
          <div style={{
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            padding: '10px 20px',
            borderBottom: `1px solid rgba(255,255,255,0.04)`,
          }}>
            <span style={{
              fontFamily: font.mono, fontSize: fontSize.sm,
              letterSpacing: '1px', color: color.fgDisabled,
              textTransform: 'uppercase' as const,
            }}>
              Recent Pipeline Runs
            </span>
            <Link
              href="/pipeline"
              style={{
                fontFamily: font.mono, fontSize: fontSize.sm,
                letterSpacing: '0.5px', color: color.fgDisabled,
                textDecoration: 'none', textTransform: 'uppercase' as const,
              }}
            >
              VIEW ALL →
            </Link>
          </div>
          {latestJobs.map((job, i) => (
            <Link key={job.id} href="/pipeline" style={{ textDecoration: 'none', display: 'block' }}>
              <div style={{
                display: 'grid', gridTemplateColumns: '80px 1fr 80px',
                padding: '8px 20px', alignItems: 'center',
                borderBottom: i < latestJobs.length - 1 ? '1px solid rgba(255,255,255,0.03)' : 'none',
                cursor: 'pointer',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <div style={{
                    width: '5px', height: '5px', borderRadius: '50%',
                    background: jobStatusColor(job.status),
                  }} />
                  <span style={{
                    fontFamily: font.mono, fontSize: fontSize.base,
                    textTransform: 'uppercase' as const, letterSpacing: '0.5px',
                    color: color.fgMuted,
                  }}>
                    {job.step}
                  </span>
                </div>
                <span style={{ fontFamily: font.body, fontSize: fontSize.base, color: color.fgDisabled }}>
                  {timeAgo(job.created_at)}
                </span>
                <span style={{
                  fontFamily: font.mono, fontSize: fontSize.sm,
                  letterSpacing: '0.5px', color: jobStatusColor(job.status),
                  textTransform: 'uppercase' as const, textAlign: 'right' as const,
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
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        padding: '0 4px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{
            width: '6px', height: '6px', borderRadius: '50%',
            background: overallStatus.color,
          }} />
          <span style={{
            fontFamily: font.mono, fontSize: fontSize.sm,
            letterSpacing: '0.8px', color: overallStatus.color,
            textTransform: 'uppercase' as const,
          }}>
            {overallStatus.label}
          </span>
        </div>
        <Link
          href="/settings/sources"
          style={{
            fontFamily: font.mono, fontSize: fontSize.sm,
            letterSpacing: '0.5px', color: color.fgDisabled,
            textDecoration: 'none', textTransform: 'uppercase' as const,
          }}
        >
          CONFIGURE SOURCES →
        </Link>
      </div>
    </div>
  );
}
