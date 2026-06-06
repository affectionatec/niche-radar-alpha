'use client';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import useSWR from 'swr';
import { endpoints, fetcher } from '@/lib/api';
import { EntityDetail, EntityMentionListResponse } from '@/lib/types';
import { color, font } from '@/lib/tokens';

const TYPE_COLORS: Record<string, string> = {
  company: 'rgba(125,211,252,0.9)',
  product: 'rgba(74,222,128,0.85)',
  technology: 'rgba(251,191,36,0.85)',
  person: 'rgba(192,132,252,0.85)',
  category: 'rgba(255,255,255,0.5)',
};

const SENTIMENT_COLOR: Record<string, string> = {
  positive: 'rgba(74,222,128,0.85)',
  negative: 'rgba(255,80,80,0.85)',
  neutral: 'rgba(255,255,255,0.5)',
};

export default function EntityDetailPage() {
  const params = useParams();
  const id = params.id as string;

  const { data: entity, error } = useSWR<EntityDetail>(
    id ? endpoints.entity(id) : null,
    fetcher,
  );
  const { data: mentionsData } = useSWR<EntityMentionListResponse>(
    id ? endpoints.entityMentions(id, 0, 50) : null,
    fetcher,
  );

  if (error) return (
    <div style={{ padding: '96px 0', textAlign: 'center' }}>
      <p style={{ fontFamily: font.mono, fontSize: '12px', color: color.fgGhost, letterSpacing: '0.8px', textTransform: 'uppercase' }}>
        {error.message?.includes('404') ? 'ENTITY NOT FOUND' : 'CANNOT CONNECT TO API'}
      </p>
      <Link href="/entities" style={{ fontFamily: font.mono, fontSize: '11px', color: color.fgMuted, textDecoration: 'none', marginTop: '16px', display: 'inline-block' }}>
        BACK TO ENTITIES
      </Link>
    </div>
  );

  if (!entity) return (
    <div style={{ padding: '96px 0', textAlign: 'center' }}>
      <div style={{ height: '200px', backgroundColor: color.surface }} />
    </div>
  );

  const mentions = mentionsData?.items ?? [];
  const velocity_history = entity.velocity_history ?? [];

  return (
    <div>
      <Link href="/entities" style={{ fontFamily: font.mono, fontSize: '10px', color: color.fgMuted, textDecoration: 'none', letterSpacing: '0.8px', textTransform: 'uppercase', marginBottom: '24px', display: 'inline-block' }}>
        BACK TO ENTITIES
      </Link>

      {/* Header */}
      <div style={{ marginBottom: '32px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '8px' }}>
          <h1 style={{ fontFamily: font.body, fontSize: '30px', fontWeight: 400, color: color.fg, margin: 0 }}>
            {entity.canonical_name}
          </h1>
          <span style={{
            fontFamily: font.mono, fontSize: '10px', letterSpacing: '0.5px',
            color: TYPE_COLORS[entity.type] || color.fgDisabled,
            border: `1px solid ${TYPE_COLORS[entity.type] || color.borderStrong}`,
            padding: '3px 8px', textTransform: 'uppercase',
          }}>
            {entity.type}
          </span>
        </div>
        {entity.aliases && entity.aliases.length > 0 && (
          <div style={{ fontFamily: font.mono, fontSize: '11px', color: color.fgDisabled, marginBottom: '8px' }}>
            Also known as: {entity.aliases.join(', ')}
          </div>
        )}
      </div>

      {/* Stats Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: '16px', marginBottom: '32px' }}>
        {[
          { label: 'MENTIONS', value: entity.mention_count },
          { label: 'SOURCES', value: entity.source_diversity },
          { label: 'VELOCITY', value: entity.velocity_score > 0 ? entity.velocity_score.toFixed(1) : '—' },
          { label: 'FIRST SEEN', value: new Date(entity.first_seen).toLocaleDateString() },
          { label: 'LAST SEEN', value: new Date(entity.last_seen).toLocaleDateString() },
        ].map(s => (
          <div key={s.label} style={{ border: `1px solid ${color.border}`, padding: '16px' }}>
            <div style={{ fontFamily: font.body, fontSize: '10px', color: color.fgDisabled, letterSpacing: '0.8px', textTransform: 'uppercase', marginBottom: '6px' }}>{s.label}</div>
            <div style={{ fontFamily: font.mono, fontSize: '18px', color: color.fg }}>{s.value}</div>
          </div>
        ))}
      </div>

      {/* Velocity History */}
      {velocity_history.length > 0 && (
        <div style={{ marginBottom: '32px' }}>
          <h2 style={{ fontFamily: font.body, fontSize: '20px', fontWeight: 400, color: color.fg, marginBottom: '16px' }}>VELOCITY HISTORY</h2>
          <div style={{ border: `1px solid ${color.border}` }}>
            <div style={{ display: 'grid', gridTemplateColumns: '130px 90px 90px 90px', gap: '12px', padding: '10px 16px', borderBottom: `1px solid ${color.surfaceActive}` }}>
              {['WEEK', 'MENTIONS', 'VELOCITY', 'SCORE'].map(h => (
                <span key={h} style={{ fontFamily: font.body, fontSize: '10px', color: color.fgDisabled, letterSpacing: '0.8px', textTransform: 'uppercase' }}>{h}</span>
              ))}
            </div>
            {velocity_history.map(v => (
              <div key={v.week_start} style={{ display: 'grid', gridTemplateColumns: '130px 90px 90px 90px', gap: '12px', padding: '12px 16px', borderBottom: `1px solid ${color.surfaceHover}` }}>
                <span style={{ fontFamily: font.body, fontSize: '12px', color: color.fgMuted }}>{new Date(v.week_start).toLocaleDateString()}</span>
                <span style={{ fontFamily: font.mono, fontSize: '13px', color: color.fgSecondary }}>{v.mention_count}</span>
                <span style={{ fontFamily: font.mono, fontSize: '11px', color: v.velocity === 'growing' ? color.success : v.velocity === 'declining' ? color.error : color.fgDisabled }}>
                  {v.velocity}
                </span>
                <span style={{ fontFamily: font.mono, fontSize: '13px', color: color.fgSecondary }}>{v.score.toFixed(1)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent Mentions */}
      <div>
        <h2 style={{ fontFamily: font.body, fontSize: '20px', fontWeight: 400, color: color.fg, marginBottom: '16px' }}>
          RECENT MENTIONS
          {mentionsData && <span style={{ fontFamily: font.mono, fontSize: '13px', color: color.fgDisabled, marginLeft: '12px' }}>{mentionsData.total}</span>}
        </h2>
        {mentions.length === 0 ? (
          <div style={{ border: `1px solid ${color.surfaceActive}`, padding: '32px', textAlign: 'center' }}>
            <span style={{ fontFamily: font.body, fontSize: '13px', color: color.fgGhost }}>No mentions recorded yet.</span>
          </div>
        ) : (
          <div style={{ border: `1px solid ${color.border}` }}>
            {mentions.map((m, i) => (
              <div key={`${m.raw_item_id}-${i}`} style={{ padding: '14px 16px', borderBottom: `1px solid ${color.surfaceHover}`, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ flex: 1, overflow: 'hidden' }}>
                  <div style={{ fontFamily: font.body, fontSize: '13px', color: color.fg, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {m.title || m.raw_item_id}
                  </div>
                  <div style={{ display: 'flex', gap: '12px', marginTop: '4px' }}>
                    {m.source && <span style={{ fontFamily: font.mono, fontSize: '10px', color: color.fgDisabled, textTransform: 'uppercase' }}>{m.source}</span>}
                    <span style={{ fontFamily: font.mono, fontSize: '10px', color: SENTIMENT_COLOR[m.sentiment] || color.fgDisabled }}>{m.sentiment}</span>
                    <span style={{ fontFamily: font.body, fontSize: '10px', color: color.fgDisabled }}>{new Date(m.extracted_at).toLocaleDateString()}</span>
                  </div>
                </div>
                {m.url && (
                  <a href={m.url} target="_blank" rel="noopener noreferrer" style={{ fontFamily: font.mono, fontSize: '10px', color: color.fgMuted, textDecoration: 'none', flexShrink: 0 }}>
                    OPEN
                  </a>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
