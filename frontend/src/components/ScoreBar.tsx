interface ScoreBarProps {
  label: string;
  value: number;
}

export default function ScoreBar({ label, value }: ScoreBarProps) {
  const clamped = Math.max(0, Math.min(100, value));
  return (
    <div style={{ marginBottom: '10px' }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          marginBottom: '4px',
        }}
      >
        <span
          style={{
            fontFamily: 'var(--font-inter)',
            fontSize: '11px',
            color: 'rgba(255, 255, 255, 0.4)',
            textTransform: 'uppercase',
            letterSpacing: '0.6px',
          }}
        >
          {label}
        </span>
        <span
          style={{
            fontFamily: 'var(--font-geist-mono)',
            fontSize: '11px',
            color: 'rgba(255, 255, 255, 0.6)',
          }}
        >
          {clamped.toFixed(0)}
        </span>
      </div>
      <div
        style={{
          height: '2px',
          backgroundColor: 'rgba(255, 255, 255, 0.08)',
          position: 'relative',
        }}
      >
        <div
          style={{
            position: 'absolute',
            inset: 0,
            width: `${clamped}%`,
            backgroundColor: '#ffffff',
          }}
        />
      </div>
    </div>
  );
}
