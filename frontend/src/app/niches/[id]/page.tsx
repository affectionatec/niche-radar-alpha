'use client';
import { useState } from 'react';
import useSWR from 'swr';
import Link from 'next/link';
import { endpoints, fetcher, toggleShortlist, validateNiche } from '@/lib/api';
import { NicheDetail } from '@/lib/types';

const COMPLEXITY_LABEL: Record<number, string> = {
  1: 'WEEKEND BUILD', 2: '2-3 DAY BUILD', 3: '~1 WEEK BUILD', 4: '1-2 WEEK BUILD', 5: '2+ WEEK BUILD',
};

const VERDICT_COLOR: Record<string, string> = {
  GO: 'rgba(74,222,128,0.85)',
  'NO-GO': 'rgba(255,80,80,0.85)',
  PIVOT: 'rgba(251,191,36,0.85)',
};
const VERDICT_BADGE: Record<string, string> = { GO: '🟢 GO', 'NO-GO': '🔴 NO-GO', PIVOT: '🟡 PIVOT' };
const TREND_EMOJI: Record<string, string> = { growing: '📈', stable: '➡️', declining: '📉' };
const WEB_VAL_COLOR: Record<string, string> = {
  validated_gap: 'rgba(74,222,128,0.85)', crowded_market: 'rgba(255,140,140,0.85)',
  expensive_incumbents: 'rgba(251,191,36,0.85)', unclear: 'rgba(255,255,255,0.3)',
};

function complexityColor(c: number | null): string {
  if (c === null) return 'rgba(255,255,255,0.3)';
  if (c <= 2) return 'rgba(74,222,128,0.85)';
  if (c === 3) return 'rgba(251,191,36,0.85)';
  return 'rgba(255,140,140,0.85)';
}

export default function NichePage({ params }: { params: { id: string } }) {
  const { id } = params;
  const { data, error, isLoading, mutate } = useSWR<NicheDetail>(endpoints.niche(id), fetcher, { refreshInterval: 60_000 });

  const [starring, setStarring] = useState(false);
  const [validating, setValidating] = useState(false);
  const [validateResult, setValidateResult] = useState<{ verdict: string; evidence: unknown[] } | null>(null);

  if (error) return <StatusMessage text="OPPORTUNITY NOT FOUND" />;
  if (isLoading || !data) return <StatusMessage text="LOADING..." />;

  const { niche, items } = data;
  const concept = niche.tool_concept || niche.keyword;
  const complexityLabel = niche.build_complexity ? COMPLEXITY_LABEL[niche.build_complexity] : 'UNKNOWN COMPLEXITY';
  const isStarred = niche.is_shortlisted;
  const analysis = niche.analysis;

  async function handleStar() {
    setStarring(true);
    try {
      await toggleShortlist(id, isStarred);
      mutate();
    } finally {
      setStarring(false);
    }
  }

  async function handleValidate() {
    setValidating(true);
    setValidateResult(null);
    try {
      const r = await validateNiche(id);
      setValidateResult(r);
      mutate();
    } catch (e) {
      setValidateResult({ verdict: 'error', evidence: [] });
    } finally {
      setValidating(false);
    }
  }

  return (
    <div>
      {/* Breadcrumb */}
      <div style={{ marginBottom: '32px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <Link href="/niches" style={{ fontFamily: 'var(--font-geist-mono)', fontSize: '12px', color: 'rgba(255,255,255,0.4)', textDecoration: 'none', textTransform: 'uppercase', letterSpacing: '0.8px' }}>
          ← OPPORTUNITIES
        </Link>
        {/* Shortlist star */}
        <button onClick={handleStar} disabled={starring} style={{
          background: 'transparent', border: '1px solid rgba(255,255,255,0.2)',
          color: isStarred ? 'rgba(251,191,36,0.9)' : 'rgba(255,255,255,0.4)',
          fontFamily: 'var(--font-geist-mono)', fontSize: '11px', letterSpacing: '0.8px',
          padding: '8px 16px', cursor: starring ? 'not-allowed' : 'pointer', textTransform: 'uppercase',
        }}>
          {isStarred ? '★ SHORTLISTED' : '☆ ADD TO SHORTLIST'}
        </button>
      </div>

      {/* Slug + verdict */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '14px', flexWrap: 'wrap' }}>
        <div style={{ fontFamily: 'var(--font-geist-mono)', fontSize: '11px', color: 'rgba(255,255,255,0.4)', textTransform: 'uppercase', letterSpacing: '1.5px' }}>
          {niche.keyword}
        </div>
        {niche.verdict && niche.verdict !== 'null' && (
          <span style={{ fontFamily: 'var(--font-geist-mono)', fontSize: '11px', color: VERDICT_COLOR[niche.verdict] || 'rgba(255,255,255,0.4)', border: `1px solid ${VERDICT_COLOR[niche.verdict] || 'rgba(255,255,255,0.2)'}`, padding: '2px 10px', letterSpacing: '0.5px' }}>
            {VERDICT_BADGE[niche.verdict] || niche.verdict}
          </span>
        )}
        {niche.momentum_label && (
          <span style={{ fontFamily: 'var(--font-geist-mono)', fontSize: '11px', color: niche.momentum_label === 'growing' ? 'rgba(74,222,128,0.7)' : niche.momentum_label === 'declining' ? 'rgba(255,140,140,0.7)' : 'rgba(255,255,255,0.3)', letterSpacing: '0.5px' }}>
            {TREND_EMOJI[niche.momentum_label]} {niche.momentum_label}
            {niche.momentum_ratio !== null && niche.momentum_ratio !== undefined && ` (${niche.momentum_ratio.toFixed(1)}×)`}
          </span>
        )}
      </div>

      {/* Header */}
      <div style={{ borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: '40px', marginBottom: '40px', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '32px' }}>
        <h1 style={{ fontFamily: 'var(--font-inter)', fontSize: 'clamp(24px, 3.5vw, 40px)', fontWeight: 400, color: '#ffffff', lineHeight: 1.2, flex: '1 1 400px', letterSpacing: '-0.3px' }}>
          {concept}
        </h1>
        <div style={{ textAlign: 'right', flexShrink: 0 }}>
          <div style={{ fontFamily: 'var(--font-geist-mono)', fontSize: '64px', fontWeight: 300, color: '#ffffff', lineHeight: 1 }}>
            {niche.llm_score.toFixed(0)}
          </div>
          <div style={{ fontFamily: 'var(--font-inter)', fontSize: '11px', color: 'rgba(255,255,255,0.35)', textTransform: 'uppercase', letterSpacing: '1px', marginTop: '4px' }}>
            OPPORTUNITY SCORE
          </div>
          {analysis?.opportunity_score !== null && analysis?.opportunity_score !== undefined && (
            <div style={{ fontFamily: 'var(--font-geist-mono)', fontSize: '12px', color: 'rgba(255,255,255,0.35)', marginTop: '4px' }}>
              {analysis.opportunity_score}/70 raw · {analysis.feasibility_score}/10 feasibility
            </div>
          )}
        </div>
      </div>

      {/* Quick-glance badges */}
      <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', marginBottom: '40px' }}>
        <Badge label={`⏱ ${complexityLabel}`} color={complexityColor(niche.build_complexity)} bordered />
        {niche.target_audience && <Badge label={`👥 ${niche.target_audience.toUpperCase()}`} />}
        <Badge label={`📊 ${niche.occurrence_count} MENTIONS`} />
      </div>

      {/* Analysis block — verdict rationale, PRD, web validation */}
      {analysis && (
        <div style={{ marginBottom: '48px' }}>
          <SectionLabel>ANALYSIS</SectionLabel>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '16px' }}>
            {/* Go/No-Go rationale */}
            {analysis.go_no_go_rationale && (
              <div style={{ padding: '16px 20px', border: `1px solid ${VERDICT_COLOR[analysis.verdict || ''] || 'rgba(255,255,255,0.1)'}33`, background: 'rgba(255,255,255,0.02)' }}>
                <div style={{ fontFamily: 'var(--font-geist-mono)', fontSize: '10px', color: VERDICT_COLOR[analysis.verdict || ''] || 'rgba(255,255,255,0.35)', letterSpacing: '0.8px', marginBottom: '8px' }}>
                  {VERDICT_BADGE[analysis.verdict || ''] || 'VERDICT'}
                </div>
                <p style={{ fontFamily: 'var(--font-inter)', fontSize: '13px', color: 'rgba(255,255,255,0.75)', lineHeight: 1.6, margin: 0 }}>
                  {analysis.go_no_go_rationale}
                </p>
              </div>
            )}

            {/* Web validation */}
            {(analysis.web_validation || validateResult) && (() => {
              const wv = validateResult ? { verdict: validateResult.verdict } : analysis.web_validation;
              if (!wv) return null;
              const color = WEB_VAL_COLOR[wv.verdict] || 'rgba(255,255,255,0.35)';
              return (
                <div style={{ padding: '16px 20px', border: `1px solid ${color}33`, background: 'rgba(255,255,255,0.02)' }}>
                  <div style={{ fontFamily: 'var(--font-geist-mono)', fontSize: '10px', color, letterSpacing: '0.8px', marginBottom: '8px' }}>
                    MARKET CHECK · {(wv.verdict || '').toUpperCase().replace('_', ' ')}
                  </div>
                  <p style={{ fontFamily: 'var(--font-inter)', fontSize: '13px', color: 'rgba(255,255,255,0.6)', lineHeight: 1.6, margin: 0 }}>
                    {wv.verdict === 'validated_gap' && 'Few or no competing products found on major platforms.'}
                    {wv.verdict === 'crowded_market' && 'Multiple products already exist in this space.'}
                    {wv.verdict === 'expensive_incumbents' && 'Incumbents found but pricing is high — pricing gap opportunity.'}
                    {wv.verdict === 'unclear' && 'Insufficient data from web search to determine market status.'}
                  </p>
                </div>
              );
            })()}

            {/* PRD preview */}
            {analysis.prd && (
              <div style={{ padding: '16px 20px', border: '1px solid rgba(255,255,255,0.1)', background: 'rgba(255,255,255,0.02)' }}>
                <div style={{ fontFamily: 'var(--font-geist-mono)', fontSize: '10px', color: 'rgba(74,222,128,0.7)', letterSpacing: '0.8px', marginBottom: '8px' }}>
                  PRD GENERATED
                </div>
                <div style={{ fontFamily: 'var(--font-inter)', fontSize: '13px', color: '#ffffff', marginBottom: '4px' }}>
                  {(analysis.prd as Record<string, string>).product_name || ''}
                </div>
                <p style={{ fontFamily: 'var(--font-inter)', fontSize: '12px', color: 'rgba(255,255,255,0.55)', lineHeight: 1.5, margin: 0 }}>
                  {(analysis.prd as Record<string, string>).one_liner || ''}
                </p>
                {(analysis.prd as Record<string, Record<string, string>>).monetization && (
                  <div style={{ fontFamily: 'var(--font-geist-mono)', fontSize: '11px', color: 'rgba(255,255,255,0.4)', marginTop: '8px' }}>
                    {(analysis.prd as Record<string, Record<string, string>>).monetization.paid_tier_price || ''} · {(analysis.prd as Record<string, Record<string, string>>).monetization.model || ''}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Validate button */}
          <div style={{ marginTop: '16px' }}>
            <button onClick={handleValidate} disabled={validating} style={{
              background: 'transparent', border: '1px solid rgba(255,255,255,0.2)',
              color: 'rgba(255,255,255,0.6)', fontFamily: 'var(--font-geist-mono)',
              fontSize: '11px', letterSpacing: '0.8px', textTransform: 'uppercase',
              padding: '8px 20px', cursor: validating ? 'not-allowed' : 'pointer', opacity: validating ? 0.6 : 1,
            }}>
              {validating ? 'SEARCHING...' : '🔍 RE-CHECK MARKET'}
            </button>
            {validateResult && (
              <span style={{ marginLeft: '16px', fontFamily: 'var(--font-geist-mono)', fontSize: '11px', color: WEB_VAL_COLOR[validateResult.verdict] || 'rgba(255,255,255,0.35)' }}>
                {(validateResult.verdict || '').toUpperCase().replace('_', ' ')}
              </span>
            )}
          </div>
        </div>
      )}

      {/* If no analysis, still show validate button */}
      {!analysis && (
        <div style={{ marginBottom: '48px' }}>
          <button onClick={handleValidate} disabled={validating} style={{
            background: 'transparent', border: '1px solid rgba(255,255,255,0.2)',
            color: 'rgba(255,255,255,0.5)', fontFamily: 'var(--font-geist-mono)',
            fontSize: '11px', letterSpacing: '0.8px', textTransform: 'uppercase',
            padding: '8px 20px', cursor: validating ? 'not-allowed' : 'pointer',
          }}>
            {validating ? 'SEARCHING...' : '🔍 CHECK MARKET (WEB SEARCH)'}
          </button>
          {validateResult && (
            <div style={{ marginTop: '12px', padding: '12px 16px', border: `1px solid ${WEB_VAL_COLOR[validateResult.verdict] || 'rgba(255,255,255,0.15)'}`, fontFamily: 'var(--font-geist-mono)', fontSize: '12px', color: WEB_VAL_COLOR[validateResult.verdict] || 'rgba(255,255,255,0.35)' }}>
              {(validateResult.verdict || '').toUpperCase().replace('_', ' ')}
            </div>
          )}
        </div>
      )}

      {/* Demand evidence + monetization grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '32px', marginBottom: '48px' }}>
        <Block label="WHY IT'S HOT">{niche.llm_reasoning || 'No analysis available yet.'}</Block>
        <Block label="MONETIZATION ANGLE">{niche.monetization || 'No specific angle identified.'}</Block>
      </div>

      {/* Pain points */}
      {niche.pain_points && niche.pain_points.length > 0 && (
        <div style={{ marginBottom: '48px' }}>
          <SectionLabel>PAIN SIGNALS · WHAT USERS ACTUALLY SAID</SectionLabel>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {niche.pain_points.map((p, i) => (
              <div key={i} style={{ border: '1px solid rgba(255,255,255,0.08)', borderLeft: '2px solid rgba(251,191,36,0.5)', padding: '14px 18px', backgroundColor: 'rgba(255,255,255,0.02)' }}>
                <div style={{ fontFamily: 'var(--font-inter)', fontSize: '13px', color: 'rgba(255,255,255,0.85)', marginBottom: p.quote ? '8px' : 0, fontWeight: 500 }}>
                  {p.pain}
                </div>
                {p.quote && (
                  <div style={{ fontFamily: 'var(--font-inter)', fontSize: '12.5px', color: 'rgba(255,255,255,0.55)', fontStyle: 'italic', lineHeight: 1.55 }}>
                    &ldquo;{p.quote}&rdquo;
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Aliases */}
      {niche.aliases.length > 0 && (
        <div style={{ marginBottom: '48px' }}>
          <SectionLabel>RELATED SEARCHES</SectionLabel>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
            {niche.aliases.map(alias => (
              <span key={alias} style={{ fontFamily: 'var(--font-geist-mono)', fontSize: '11px', color: 'rgba(255,255,255,0.75)', border: '1px solid rgba(255,255,255,0.2)', padding: '4px 12px', letterSpacing: '0.5px' }}>
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
          <div style={{ border: '1px solid rgba(255,255,255,0.1)', padding: '32px', textAlign: 'center', fontFamily: 'var(--font-inter)', fontSize: '13px', color: 'rgba(255,255,255,0.3)' }}>
            No linked source items.
          </div>
        ) : (
          <div style={{ border: '1px solid rgba(255,255,255,0.1)', display: 'flex', flexDirection: 'column' }}>
            {items.map((item, i) => (
              <div key={item.id} style={{ display: 'grid', gridTemplateColumns: '80px 1fr 60px', gap: '16px', alignItems: 'center', padding: '14px 20px', borderBottom: i < items.length - 1 ? '1px solid rgba(255,255,255,0.06)' : 'none', backgroundColor: 'rgba(255,255,255,0.02)' }}>
                <span style={{ fontFamily: 'var(--font-geist-mono)', fontSize: '10px', color: 'rgba(255,255,255,0.35)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                  {item.source}
                </span>
                <div>
                  {item.url ? (
                    <a href={item.url} target="_blank" rel="noopener noreferrer" style={{ fontFamily: 'var(--font-inter)', fontSize: '13px', color: '#ffffff', textDecoration: 'none', display: 'block' }}>
                      {item.title ?? item.source_id}
                    </a>
                  ) : (
                    <span style={{ fontFamily: 'var(--font-inter)', fontSize: '13px', color: '#ffffff', display: 'block' }}>
                      {item.title ?? item.source_id}
                    </span>
                  )}
                </div>
                <span style={{ fontFamily: 'var(--font-geist-mono)', fontSize: '13px', color: 'rgba(255,255,255,0.45)', textAlign: 'right' }}>
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

function Badge({ label, color, bordered }: { label: string; color?: string; bordered?: boolean }) {
  const borderColor = bordered && color ? color : 'rgba(255,255,255,0.15)';
  const textColor = color ?? 'rgba(255,255,255,0.7)';
  return (
    <span style={{ fontFamily: 'var(--font-geist-mono)', fontSize: '11px', color: textColor, border: `1px solid ${borderColor}`, padding: '5px 12px', letterSpacing: '0.6px' }}>
      {label}
    </span>
  );
}

function Block({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <SectionLabel>{label}</SectionLabel>
      <p style={{ fontFamily: 'var(--font-inter)', fontSize: '14px', color: 'rgba(255,255,255,0.78)', lineHeight: 1.7, margin: 0 }}>
        {children}
      </p>
    </div>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ fontFamily: 'var(--font-inter)', fontSize: '11px', color: 'rgba(255,255,255,0.4)', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '14px', fontWeight: 400 }}>
      {children}
    </div>
  );
}

function StatusMessage({ text }: { text: string }) {
  return (
    <div style={{ padding: '96px 0', textAlign: 'center', fontFamily: 'var(--font-geist-mono)', fontSize: '13px', color: 'rgba(255,255,255,0.3)', textTransform: 'uppercase', letterSpacing: '1px' }}>
      {text}
    </div>
  );
}
