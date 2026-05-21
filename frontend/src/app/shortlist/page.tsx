'use client';
import Link from 'next/link';
import useSWR from 'swr';
import { endpoints, fetcher, toggleShortlist } from '@/lib/api';

interface ShortlistItem {
  id: string;
  keyword: string;
  tool_concept: string;
  llm_score: number;
  status: string;
  momentum_label: string | null;
  verdict: string | null;
  added_at: string;
  note: string;
}

const VERDICT_COLOR: Record<string, string> = {
  GO: 'rgba(74,222,128,0.85)', 'NO-GO': 'rgba(255,80,80,0.85)', PIVOT: 'rgba(251,191,36,0.85)',
};
const TREND_EMOJI: Record<string, string> = { growing: '📈', stable: '➡️', declining: '📉' };

export default function ShortlistPage() {
  const { data: items, isLoading, error, mutate } = useSWR<ShortlistItem[]>(
    endpoints.shortlist, fetcher, { refreshInterval: 30_000 }
  );

  async function handleRemove(niche_id: string) {
    await toggleShortlist(niche_id, true); // starred=true → DELETE
    mutate();
  }

  return (
    <div>
      <h1 style={{ fontFamily: 'var(--font-inter)', fontSize: '30px', fontWeight: 400, color: '#ffffff', marginBottom: '8px' }}>
        SHORTLIST
      </h1>
      <p style={{ fontFamily: 'var(--font-inter)', fontSize: '13px', color: 'rgba(255,255,255,0.35)', marginBottom: '48px' }}>
        Opportunities you&apos;ve starred for closer review.
      </p>

      {isLoading && <div style={{ color: 'rgba(255,255,255,0.35)', fontFamily: 'var(--font-geist-mono)', fontSize: '12px' }}>LOADING...</div>}
      {error && <div style={{ color: 'rgba(255,80,80,0.85)', fontFamily: 'var(--font-geist-mono)', fontSize: '12px' }}>Failed to load shortlist</div>}

      {items && items.length === 0 && (
        <div style={{ border: '1px solid rgba(255,255,255,0.08)', padding: '48px', textAlign: 'center' }}>
          <p style={{ fontFamily: 'var(--font-inter)', fontSize: '13px', color: 'rgba(255,255,255,0.25)', marginBottom: '20px' }}>
            No starred opportunities yet.
          </p>
          <Link href="/niches" style={{ fontFamily: 'var(--font-geist-mono)', fontSize: '11px', color: 'rgba(255,255,255,0.6)', textDecoration: 'none', border: '1px solid rgba(255,255,255,0.2)', padding: '8px 16px', letterSpacing: '0.8px', textTransform: 'uppercase' }}>
            BROWSE OPPORTUNITIES →
          </Link>
        </div>
      )}

      {items && items.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
          {items.map(item => (
            <div key={item.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '16px 20px', background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', gap: '16px' }}>
              <div style={{ flex: 1, overflow: 'hidden' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '4px', flexWrap: 'wrap' }}>
                  <Link href={`/niches/${item.id}`} style={{ fontFamily: 'var(--font-inter)', fontSize: '14px', color: '#ffffff', textDecoration: 'none' }}>
                    {item.tool_concept || item.keyword}
                  </Link>
                  {item.verdict && (
                    <span style={{ fontFamily: 'var(--font-geist-mono)', fontSize: '9px', color: VERDICT_COLOR[item.verdict] || 'rgba(255,255,255,0.35)', border: `1px solid ${VERDICT_COLOR[item.verdict] || 'rgba(255,255,255,0.2)'}`, padding: '1px 6px' }}>
                      {item.verdict}
                    </span>
                  )}
                  {item.momentum_label && (
                    <span style={{ fontFamily: 'var(--font-geist-mono)', fontSize: '10px', color: item.momentum_label === 'growing' ? 'rgba(74,222,128,0.7)' : 'rgba(255,255,255,0.3)' }}>
                      {TREND_EMOJI[item.momentum_label]} {item.momentum_label}
                    </span>
                  )}
                </div>
                <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
                  <span style={{ fontFamily: 'var(--font-geist-mono)', fontSize: '12px', color: '#ffffff' }}>
                    {item.llm_score?.toFixed(0) ?? '—'}
                  </span>
                  <span style={{ fontFamily: 'var(--font-geist-mono)', fontSize: '10px', color: 'rgba(255,255,255,0.3)', letterSpacing: '0.5px', textTransform: 'uppercase' }}>
                    {item.keyword}
                  </span>
                  {item.note && (
                    <span style={{ fontFamily: 'var(--font-inter)', fontSize: '12px', color: 'rgba(255,255,255,0.4)', fontStyle: 'italic' }}>
                      {item.note}
                    </span>
                  )}
                  <span style={{ fontFamily: 'var(--font-inter)', fontSize: '11px', color: 'rgba(255,255,255,0.2)' }}>
                    {new Date(item.added_at).toLocaleDateString()}
                  </span>
                </div>
              </div>
              <button
                onClick={() => handleRemove(item.id)}
                title="Remove from shortlist"
                style={{ background: 'transparent', border: 'none', color: 'rgba(255,255,255,0.25)', cursor: 'pointer', fontSize: '16px', padding: '4px 8px', flexShrink: 0 }}
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
