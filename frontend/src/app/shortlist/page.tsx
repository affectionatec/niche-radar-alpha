'use client';
import Link from 'next/link';
import useSWR from 'swr';
import { endpoints, fetcher, toggleShortlist } from '@/lib/api';
import { color, font } from '@/lib/tokens';

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
  GO: color.success, 'NO-GO': color.error, PIVOT: color.warning,
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
      <h1 style={{ fontFamily: font.body, fontSize: '30px', fontWeight: 400, color: color.fg, marginBottom: '8px' }}>
        SHORTLIST
      </h1>
      <p style={{ fontFamily: font.body, fontSize: '13px', color: color.fgDisabled, marginBottom: '48px' }}>
        Opportunities you&apos;ve starred for closer review.
      </p>

      {isLoading && <div style={{ color: color.fgDisabled, fontFamily: font.mono, fontSize: '12px' }}>LOADING...</div>}
      {error && <div style={{ color: color.error, fontFamily: font.mono, fontSize: '12px' }}>Failed to load shortlist</div>}

      {items && items.length === 0 && (
        <div style={{ border: `1px solid ${color.surfaceActive}`, padding: '48px', textAlign: 'center' as const }}>
          <p style={{ fontFamily: font.body, fontSize: '13px', color: color.fgGhost, marginBottom: '20px' }}>
            No starred opportunities yet.
          </p>
          <Link href="/niches" style={{ fontFamily: font.mono, fontSize: '11px', color: color.fgSecondary, textDecoration: 'none', border: `1px solid ${color.borderStrong}`, padding: '8px 16px', letterSpacing: '0.8px', textTransform: 'uppercase' as const }}>
            BROWSE OPPORTUNITIES →
          </Link>
        </div>
      )}

      {items && items.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
          {items.map(item => (
            <div key={item.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '16px 20px', background: color.surface, border: `1px solid ${color.surfaceActive}`, gap: '16px' }}>
              <div style={{ flex: 1, overflow: 'hidden' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '4px', flexWrap: 'wrap' }}>
                  <Link href={`/niches/${item.id}`} style={{ fontFamily: font.body, fontSize: '14px', color: color.fg, textDecoration: 'none' }}>
                    {item.tool_concept || item.keyword}
                  </Link>
                  {item.verdict && (
                    <span style={{ fontFamily: font.mono, fontSize: '9px', color: VERDICT_COLOR[item.verdict] || color.fgDisabled, border: `1px solid ${VERDICT_COLOR[item.verdict] || color.borderStrong}`, padding: '1px 6px' }}>
                      {item.verdict}
                    </span>
                  )}
                  {item.momentum_label && (
                    <span style={{ fontFamily: font.mono, fontSize: '10px', color: item.momentum_label === 'growing' ? color.successMuted : color.fgGhost }}>
                      {TREND_EMOJI[item.momentum_label]} {item.momentum_label}
                    </span>
                  )}
                </div>
                <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
                  <span style={{ fontFamily: font.mono, fontSize: '12px', color: color.fg }}>
                    {item.llm_score?.toFixed(0) ?? '—'}
                  </span>
                  <span style={{ fontFamily: font.mono, fontSize: '10px', color: color.fgGhost, letterSpacing: '0.5px', textTransform: 'uppercase' as const }}>
                    {item.keyword}
                  </span>
                  {item.note && (
                    <span style={{ fontFamily: font.body, fontSize: '12px', color: color.fgMuted, fontStyle: 'italic' }}>
                      {item.note}
                    </span>
                  )}
                  <span style={{ fontFamily: font.body, fontSize: '11px', color: color.fgGhost }}>
                    {new Date(item.added_at).toLocaleDateString()}
                  </span>
                </div>
              </div>
              <button
                onClick={() => handleRemove(item.id)}
                aria-label={`Remove ${item.tool_concept || item.keyword} from shortlist`}
                style={{ background: 'transparent', border: 'none', color: color.fgGhost, cursor: 'pointer', fontSize: '16px', padding: '4px 8px', flexShrink: 0 }}
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
