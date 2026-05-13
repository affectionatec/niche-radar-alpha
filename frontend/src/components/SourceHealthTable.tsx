import { SourceHealth } from '@/lib/types';

const cell: React.CSSProperties = {
  fontFamily: 'var(--font-inter)',
  fontSize: '13px',
  color: '#ffffff',
  padding: '12px 16px',
  textAlign: 'left',
};

const head: React.CSSProperties = {
  fontFamily: 'var(--font-geist-mono)',
  fontSize: '10px',
  color: 'rgba(255, 255, 255, 0.35)',
  textTransform: 'uppercase',
  letterSpacing: '1px',
  padding: '8px 16px',
  textAlign: 'left',
  fontWeight: 400,
};

export default function SourceHealthTable({ sources }: { sources: SourceHealth[] }) {
  return (
    <div style={{ border: '1px solid rgba(255,255,255,0.1)', overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
            <th style={head}>SOURCE</th>
            <th style={head}>STATUS</th>
            <th style={head}>LAST RUN</th>
            <th style={head}>ITEMS</th>
          </tr>
        </thead>
        <tbody>
          {sources.map((s) => (
            <tr
              key={s.source}
              style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}
            >
              <td style={{ ...cell, fontFamily: 'var(--font-geist-mono)', fontSize: '12px', letterSpacing: '0.5px', textTransform: 'uppercase' }}>
                {s.source}
              </td>
              <td
                style={{
                  ...cell,
                  fontFamily: 'var(--font-geist-mono)',
                  fontSize: '12px',
                  color: s.status === 'OK' ? '#ffffff' : 'rgba(255,255,255,0.4)',
                }}
              >
                {s.status}
              </td>
              <td style={{ ...cell, color: 'rgba(255,255,255,0.45)', fontSize: '12px' }}>
                {s.last_run === '-' ? '—' : new Date(s.last_run).toLocaleString()}
              </td>
              <td style={{ ...cell, fontFamily: 'var(--font-geist-mono)', fontSize: '13px' }}>
                {s.items.toLocaleString()}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
