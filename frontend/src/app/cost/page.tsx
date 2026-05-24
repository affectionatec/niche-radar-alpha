'use client';
import useSWR from 'swr';
import { endpoints, fetcher } from '@/lib/api';
import { color, font, fontSize, spacing } from '@/lib/tokens';

interface AgentUsage {
  agent: string;
  prompt_total: number;
  completion_total: number;
  token_total: number;
  call_count: number;
}

interface RunUsage {
  pipeline_run: string;
  token_total: number;
  call_count: number;
  started_at: string;
}

interface DailyUsage {
  day: string;
  token_total: number;
  call_count: number;
}

interface CostSummary {
  period_days: number;
  totals: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
    call_count: number;
  };
  by_agent: AgentUsage[];
  by_run: RunUsage[];
  daily: DailyUsage[];
}

const AGENT_LABELS: Record<string, string> = {
  a1: 'Signal Filter',
  a2: 'Pain Extractor',
  a3: 'Market Researcher',
  a4: 'Opportunity Scorer',
  a5: 'Feasibility Analyst',
  a6: 'Go/No-Go Judge',
  a7: 'PRD Writer',
  a8: 'Brief Creator',
  clustering: 'Clustering',
  unknown: 'Other',
};

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toString();
}

function timeAgo(dateStr: string): string {
  if (!dateStr) return '—';
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export default function CostPage() {
  const { data, error } = useSWR<CostSummary>(endpoints.costSummary(30), fetcher, {
    refreshInterval: 30_000,
  });

  return (
    <div>
      {/* Header */}
      <div style={{ marginBottom: spacing['4xl'] }}>
        <h1 style={{
          fontFamily: font.body, fontSize: fontSize['5xl'], fontWeight: 400,
          color: color.fg, margin: 0,
        }}>
          COST INSIGHTS
        </h1>
        <p style={{
          fontFamily: font.body, fontSize: fontSize.lg,
          color: color.fgDisabled, marginTop: spacing.xs,
        }}>
          LLM token usage across pipeline runs — last 30 days
        </p>
      </div>

      {error && (
        <div style={{
          padding: spacing.lg, border: `1px solid ${color.errorMuted}`,
          fontFamily: font.mono, fontSize: fontSize.base, color: color.error,
          marginBottom: spacing['2xl'],
        }}>
          Failed to load cost data
        </div>
      )}

      {!data && !error && (
        <div style={{
          fontFamily: font.mono, fontSize: fontSize.base,
          color: color.fgGhost, padding: '40px 0', textAlign: 'center',
        }}>
          Loading...
        </div>
      )}

      {data && (
        <>
          {/* Grand totals */}
          <div style={{
            display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1px',
            background: color.surfaceHover, marginBottom: '40px',
          }}>
            <StatCard label="TOTAL TOKENS" value={formatTokens(data.totals.total_tokens)} />
            <StatCard label="PROMPT TOKENS" value={formatTokens(data.totals.prompt_tokens)} />
            <StatCard label="COMPLETION TOKENS" value={formatTokens(data.totals.completion_tokens)} />
            <StatCard label="LLM CALLS" value={data.totals.call_count.toString()} />
          </div>

          {/* Usage by agent */}
          {data.by_agent.length > 0 && (
            <section style={{ marginBottom: '40px' }}>
              <SectionLabel>USAGE BY AGENT</SectionLabel>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1px', background: color.surfaceHover }}>
                {data.by_agent.map((a) => {
                  const pct = data.totals.total_tokens > 0
                    ? (a.token_total / data.totals.total_tokens) * 100
                    : 0;
                  return (
                    <div key={a.agent} style={{
                      background: color.bg, padding: `${spacing.lg} ${spacing.xl}`,
                      display: 'grid', gridTemplateColumns: '120px 1fr 100px 80px',
                      alignItems: 'center', gap: spacing.md,
                    }}>
                      <div>
                        <span style={{
                          fontFamily: font.mono, fontSize: fontSize.sm,
                          color: color.fgMuted, letterSpacing: '0.5px',
                          textTransform: 'uppercase' as const,
                        }}>
                          {a.agent}
                        </span>
                        <div style={{
                          fontFamily: font.body, fontSize: fontSize.sm,
                          color: color.fgGhost, marginTop: '2px',
                        }}>
                          {AGENT_LABELS[a.agent] || a.agent}
                        </div>
                      </div>
                      {/* Bar */}
                      <div style={{ position: 'relative', height: '6px', background: color.surface }}>
                        <div style={{
                          position: 'absolute', left: 0, top: 0, height: '100%',
                          width: `${Math.max(pct, 1)}%`,
                          background: color.fgGhost,
                        }} />
                      </div>
                      <span style={{
                        fontFamily: font.mono, fontSize: fontSize.base,
                        color: color.fg, textAlign: 'right' as const,
                      }}>
                        {formatTokens(a.token_total)}
                      </span>
                      <span style={{
                        fontFamily: font.mono, fontSize: fontSize.sm,
                        color: color.fgGhost, textAlign: 'right' as const,
                      }}>
                        {a.call_count} calls
                      </span>
                    </div>
                  );
                })}
              </div>
            </section>
          )}

          {/* Daily usage */}
          {data.daily.length > 0 && (
            <section style={{ marginBottom: '40px' }}>
              <SectionLabel>DAILY USAGE</SectionLabel>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1px', background: color.surfaceHover }}>
                {data.daily.slice(0, 14).map((d) => {
                  const maxDaily = Math.max(...data.daily.map(dd => dd.token_total));
                  const pct = maxDaily > 0 ? (d.token_total / maxDaily) * 100 : 0;
                  return (
                    <div key={d.day} style={{
                      background: color.bg, padding: `${spacing.md} ${spacing.xl}`,
                      display: 'grid', gridTemplateColumns: '100px 1fr 80px 60px',
                      alignItems: 'center', gap: spacing.md,
                    }}>
                      <span style={{
                        fontFamily: font.mono, fontSize: fontSize.base,
                        color: color.fgMuted,
                      }}>
                        {d.day}
                      </span>
                      <div style={{ position: 'relative', height: '4px', background: color.surface }}>
                        <div style={{
                          position: 'absolute', left: 0, top: 0, height: '100%',
                          width: `${Math.max(pct, 1)}%`,
                          background: color.successMuted,
                        }} />
                      </div>
                      <span style={{
                        fontFamily: font.mono, fontSize: fontSize.base,
                        color: color.fg, textAlign: 'right' as const,
                      }}>
                        {formatTokens(d.token_total)}
                      </span>
                      <span style={{
                        fontFamily: font.mono, fontSize: fontSize.sm,
                        color: color.fgGhost, textAlign: 'right' as const,
                      }}>
                        {d.call_count}
                      </span>
                    </div>
                  );
                })}
              </div>
            </section>
          )}

          {/* Recent pipeline runs */}
          {data.by_run.length > 0 && (
            <section>
              <SectionLabel>RECENT PIPELINE RUNS</SectionLabel>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1px', background: color.surfaceHover }}>
                {data.by_run.slice(0, 10).map((r) => (
                  <div key={r.pipeline_run} style={{
                    background: color.bg, padding: `${spacing.md} ${spacing.xl}`,
                    display: 'grid', gridTemplateColumns: '1fr 80px 80px',
                    alignItems: 'center', gap: spacing.md,
                  }}>
                    <div>
                      <span style={{
                        fontFamily: font.mono, fontSize: fontSize.base,
                        color: color.fgMuted,
                      }}>
                        {r.pipeline_run.slice(0, 8)}
                      </span>
                      <span style={{
                        fontFamily: font.body, fontSize: fontSize.sm,
                        color: color.fgGhost, marginLeft: spacing.sm,
                      }}>
                        {timeAgo(r.started_at)}
                      </span>
                    </div>
                    <span style={{
                      fontFamily: font.mono, fontSize: fontSize.base,
                      color: color.fg, textAlign: 'right' as const,
                    }}>
                      {formatTokens(r.token_total)}
                    </span>
                    <span style={{
                      fontFamily: font.mono, fontSize: fontSize.sm,
                      color: color.fgGhost, textAlign: 'right' as const,
                    }}>
                      {r.call_count} calls
                    </span>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Empty state */}
          {data.totals.call_count === 0 && (
            <div style={{
              textAlign: 'center', padding: `60px ${spacing.xl}`,
              border: `1px solid ${color.surfaceHover}`,
            }}>
              <div style={{
                fontFamily: font.mono, fontSize: fontSize.base,
                color: color.fgGhost, letterSpacing: '0.8px',
                textTransform: 'uppercase' as const,
              }}>
                NO USAGE DATA YET
              </div>
              <p style={{
                fontFamily: font.body, fontSize: fontSize.md,
                color: color.fgGhost, marginTop: spacing.sm,
              }}>
                Run a pipeline analysis to start tracking LLM token usage
              </p>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ background: color.bg, padding: spacing.xl }}>
      <div style={{
        fontFamily: font.mono, fontSize: fontSize.xs, letterSpacing: '1px',
        color: color.fgGhost, textTransform: 'uppercase' as const, marginBottom: spacing.sm,
      }}>
        {label}
      </div>
      <div style={{
        fontFamily: font.mono, fontSize: '24px', fontWeight: 300,
        color: color.fg,
      }}>
        {value}
      </div>
    </div>
  );
}

function SectionLabel({ children }: { children: string }) {
  return (
    <div style={{
      fontFamily: font.mono, fontSize: fontSize.sm, letterSpacing: '1px',
      color: color.fgGhost, textTransform: 'uppercase' as const, marginBottom: spacing.md,
    }}>
      {children}
    </div>
  );
}
