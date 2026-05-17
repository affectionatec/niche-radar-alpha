import Link from 'next/link';

const NAV_LINKS = [
  { href: '/pipeline', label: 'PIPELINE' },
  { href: '/niches', label: 'NICHES' },
  { href: '/reports', label: 'REPORTS' },
  { href: '/settings', label: 'SETTINGS' },
];

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
      <div style={{ display: 'flex', alignItems: 'center', gap: '40px' }}>
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
        <div style={{ display: 'flex', gap: '28px' }}>
          {NAV_LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              style={{
                fontFamily: 'var(--font-inter)',
                fontSize: '11px',
                color: 'rgba(255,255,255,0.45)',
                textDecoration: 'none',
                letterSpacing: '0.8px',
                textTransform: 'uppercase',
              }}
            >
              {link.label}
            </Link>
          ))}
        </div>
      </div>
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
