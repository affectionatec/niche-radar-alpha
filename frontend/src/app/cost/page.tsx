'use client';
import useSWR from 'swr';
import Link from 'next/link';
import { endpoints, fetcher } from '@/lib/api';

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
    <main style={{ maxWidth: '900px', margin: '0 auto', padding: '64px 24px' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '48px' }}>
        <div>
          <h1 style={{
            fontFamily: 'var(--font-inter)', fontSize: '30px', fontWeight: 400,
            color: '#ffffff', margin: 0,
          }}>
            Cost Insights
          </h1>
          <p style={{
            fontFamily: 'var(--font-inter)', fontSize: '13px',
            color: 'rgba(255,255,255,0.35)', marginTop: '4px',
          }}>
            LLM token usage across pipeline runs — last 30 days
          </p>
        </div>
        <Link
          href="/settings"
          style={{
            fontFamily: 'var(--font-geist-mono)', fontSize: '10px', letterSpacing: '0.8px',
            color: 'rgba(255,255,255,0.4)', textDecoration: 'none', textTransform: 'uppercase',
          }}
        >
          ← SETTINGS
        </Link>
      </div>

      {error && (
        <div style={{
          padding: '16px', border: '1px solid rgba(255,80,80,0.3)',
          fontFamily: 'var(--font-geist-mono)', fontSize: '11px', color: 'rgba(255,80,80,0.85)',
          marginBottom: '24px',
        }}>
          Failed to load cost data
        </div>
      )}

      {!data && !error && (
        <div style={{
          fontFamily: 'var(--font-geist-mono)', fontSize: '11px',
          color: 'rgba(255,255,255,0.3)', padding: '40px 0', textAlign: 'center',
        }}>
          Loading...
        </div>
      )}

      {data && (
        <>
          {/* Grand totals */}
          <div style={{
            display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1px',
            background: 'rgba(255,255,255,0.06)', marginBottom: '40px',
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
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1px', background: 'rgba(255,255,255,0.06)' }}>
                {data.by_agent.map((a) => {
                  const pct = data.totals.total_tokens > 0
                    ? (a.token_total / data.totals.total_tokens) * 100
                    : 0;
                  return (
                    <div key={a.agent} style={{
                      background: '#1f2228', padding: '14px 20px',
                      display: 'grid', gridTemplateColumns: '120px 1fr 100px 80px',
                      alignItems: 'center', gap: '12px',
                    }}>
                      <div>
                        <span style={{
                          fontFamily: 'var(--font-geist-mono)', fontSize: '10px',
                          color: 'rgba(255,255,255,0.5)', letterSpacing: '0.5px',
                          textTransform: 'uppercase',
                        }}>
                          {a.agent}
                        </span>
                        <div style={{
                          fontFamily: 'var(--font-inter)', fontSize: '10px',
                          color: 'rgba(255,255,255,0.25)', marginTop: '2px',
                        }}>
                          {AGENT_LABELS[a.agent] || a.agent}
                        </div>
                      </div>
                      {/* Bar */}
                      <div style={{ position: 'relative', height: '6px', background: 'rgba(255,255,255,0.04)' }}>
                        <div style={{
                          position: 'absolute', left: 0, top: 0, height: '100%',
                          width: `${Math.max(pct, 1)}%`,
                          background: 'rgba(255,255,255,0.25)',
                        }} />
                      </div>
                      <span style={{
                        fontFamily: 'var(--font-geist-mono)', fontSize: '11px',
                        color: '#ffffff', textAlign: 'right',
                      }}>
                        {formatTokens(a.token_total)}
                      </span>
                      <span style={{
                        fontFamily: 'var(--font-geist-mono)', fontSize: '10px',
                        color: 'rgba(255,255,255,0.3)', textAlign: 'right',
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
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1px', background: 'rgba(255,255,255,0.06)' }}>
                {data.daily.slice(0, 14).map((d) => {
                  const maxDaily = Math.max(...data.daily.map(dd => dd.token_total));
                  const pct = maxDaily > 0 ? (d.token_total / maxDaily) * 100 : 0;
                  return (
                    <div key={d.day} style={{
                      background: '#1f2228', padding: '10px 20px',
                      display: 'grid', gridTemplateColumns: '100px 1fr 80px 60px',
                      alignItems: 'center', gap: '12px',
                    }}>
                      <span style={{
                        fontFamily: 'var(--font-geist-mono)', fontSize: '11px',
                        color: 'rgba(255,255,255,0.5)',
                      }}>
                        {d.day}
                      </span>
                      <div style={{ position: 'relative', height: '4px', background: 'rgba(255,255,255,0.04)' }}>
                        <div style={{
                          position: 'absolute', left: 0, top: 0, height: '100%',
                          width: `${Math.max(pct, 1)}%`,
                          background: 'rgba(74,222,128,0.5)',
                        }} />
                      </div>
                      <span style={{
                        fontFamily: 'var(--font-geist-mono)', fontSize: '11px',
                        color: '#ffffff', textAlign: 'right',
                      }}>
                        {formatTokens(d.token_total)}
                      </span>
                      <span style={{
                        fontFamily: 'var(--font-geist-mono)', fontSize: '10px',
                        color: 'rgba(255,255,255,0.3)', textAlign: 'right',
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
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1px', background: 'rgba(255,255,255,0.06)' }}>
                {data.by_run.slice(0, 10).map((r) => (
                  <div key={r.pipeline_run} style={{
                    background: '#1f2228', padding: '12px 20px',
                    display: 'grid', gridTemplateColumns: '1fr 80px 80px',
                    alignItems: 'center', gap: '12px',
                  }}>
                    <div>
                      <span style={{
                        fontFamily: 'var(--font-geist-mono)', fontSize: '11px',
                        color: 'rgba(255,255,255,0.5)',
                      }}>
                        {r.pipeline_run.slice(0, 8)}
                      </span>
                      <span style={{
                        fontFamily: 'var(--font-inter)', fontSize: '10px',
                        color: 'rgba(255,255,255,0.25)', marginLeft: '8px',
                      }}>
                        {timeAgo(r.started_at)}
                      </span>
                    </div>
                    <span style={{
                      fontFamily: 'var(--font-geist-mono)', fontSize: '11px',
                      color: '#ffffff', textAlign: 'right',
                    }}>
                      {formatTokens(r.token_total)}
                    </span>
                    <span style={{
                      fontFamily: 'var(--font-geist-mono)', fontSize: '10px',
                      color: 'rgba(255,255,255,0.3)', textAlign: 'right',
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
              textAlign: 'center', padding: '60px 20px',
              border: '1px solid rgba(255,255,255,0.06)',
            }}>
              <div style={{
                fontFamily: 'var(--font-geist-mono)', fontSize: '11px',
                color: 'rgba(255,255,255,0.3)', letterSpacing: '0.8px',
                textTransform: 'uppercase',
              }}>
                NO USAGE DATA YET
              </div>
              <p style={{
                fontFamily: 'var(--font-inter)', fontSize: '12px',
                color: 'rgba(255,255,255,0.2)', marginTop: '8px',
              }}>
                Run a pipeline analysis to start tracking LLM token usage
              </p>
            </div>
          )}
        </>
      )}
    </main>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ background: '#1f2228', padding: '20px' }}>
      <div style={{
        fontFamily: 'var(--font-geist-mono)', fontSize: '9px', letterSpacing: '1px',
        color: 'rgba(255,255,255,0.3)', textTransform: 'uppercase', marginBottom: '8px',
      }}>
        {label}
      </div>
      <div style={{
        fontFamily: 'var(--font-geist-mono)', fontSize: '24px', fontWeight: 300,
        color: '#ffffff',
      }}>
        {value}
      </div>
    </div>
  );
}

function SectionLabel({ children }: { children: string }) {
  return (
    <div style={{
      fontFamily: 'var(--font-geist-mono)', fontSize: '10px', letterSpacing: '1px',
      color: 'rgba(255,255,255,0.25)', textTransform: 'uppercase', marginBottom: '12px',
    }}>
      {children}
    </div>
  );
}
