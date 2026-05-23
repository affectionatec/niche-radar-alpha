'use client';
import { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

const NAV_LINKS = [
  { href: '/pipeline', label: 'PIPELINE' },
  { href: '/niches', label: 'OPPORTUNITIES' },
  { href: '/shortlist', label: 'SHORTLIST' },
  { href: '/reports', label: 'REPORTS' },
  { href: '/settings', label: 'SETTINGS' },
];

export default function Navigation() {
  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);

  function isActive(href: string) {
    if (href === '/') return pathname === '/';
    return pathname.startsWith(href);
  }

  return (
    <nav
      role="navigation"
      aria-label="Main navigation"
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

        {/* Mobile menu button */}
        <button
          className="mobile-menu-btn"
          onClick={() => setMenuOpen(!menuOpen)}
          aria-label={menuOpen ? 'Close menu' : 'Open menu'}
          aria-expanded={menuOpen}
          style={{
            display: 'none',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'none',
            border: 'none',
            color: 'rgba(255,255,255,0.6)',
            cursor: 'pointer',
            padding: '4px',
            width: '32px',
            height: '32px',
          }}
        >
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
            {menuOpen ? (
              <path d="M5 5l8 8M13 5l-8 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            ) : (
              <>
                <path d="M3 5h12M3 9h12M3 13h12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
              </>
            )}
          </svg>
        </button>

        {/* Nav links */}
        <div
          className={`nav-links${menuOpen ? ' open' : ''}`}
          style={{
            display: 'flex',
            gap: '28px',
          }}
        >
          {NAV_LINKS.map((link) => {
            const active = isActive(link.href);
            return (
              <Link
                key={link.href}
                href={link.href}
                onClick={() => setMenuOpen(false)}
                aria-current={active ? 'page' : undefined}
                style={{
                  fontFamily: 'var(--font-inter)',
                  fontSize: '11px',
                  color: active ? '#ffffff' : 'rgba(255,255,255,0.45)',
                  textDecoration: 'none',
                  letterSpacing: '0.8px',
                  textTransform: 'uppercase',
                  borderBottom: active ? '1px solid rgba(255,255,255,0.5)' : '1px solid transparent',
                  paddingBottom: '2px',
                  transition: 'color 0.15s, border-color 0.15s',
                }}
              >
                {link.label}
              </Link>
            );
          })}
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
