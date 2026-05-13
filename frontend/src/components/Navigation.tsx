import Link from 'next/link';

export default function Navigation() {
  return (
    <nav
      style={{
        backgroundColor: '#1f2228',
        borderBottom: '1px solid rgba(255, 255, 255, 0.1)',
        padding: '0 24px',
        height: '56px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        position: 'sticky',
        top: 0,
        zIndex: 10,
      }}
    >
      <Link
        href="/"
        style={{
          fontFamily: 'var(--font-geist-mono)',
          fontSize: '14px',
          fontWeight: 400,
          color: '#ffffff',
          textDecoration: 'none',
          letterSpacing: '1.4px',
          textTransform: 'uppercase',
        }}
      >
        NICHE RADAR
      </Link>
      <span
        style={{
          fontFamily: 'var(--font-geist-mono)',
          fontSize: '11px',
          color: 'rgba(255, 255, 255, 0.3)',
          letterSpacing: '1px',
          textTransform: 'uppercase',
        }}
      >
        ALPHA
      </span>
    </nav>
  );
}
