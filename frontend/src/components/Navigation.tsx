'use client';
import { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { color, font, fontSize } from '@/lib/tokens';

const NAV_LINKS = [
  { href: '/pipeline', label: 'PIPELINE' },
  { href: '/niches', label: 'OPPORTUNITIES' },
  { href: '/entities', label: 'ENTITIES' },
  { href: '/shortlist', label: 'SHORTLIST' },
  { href: '/reports', label: 'REPORTS' },
  { href: '/cost', label: 'COST' },
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
        backgroundColor: color.bg,
        borderBottom: `1px solid ${color.border}`,
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
            fontFamily: font.mono,
            fontSize: fontSize.xl,
            fontWeight: 400,
            color: color.fg,
            textDecoration: 'none',
            letterSpacing: '1.4px',
            textTransform: 'uppercase' as const,
          }}
        >
          NICHE RADAR
        </Link>

        {/* Mobile menu button — hidden by default, shown via CSS media query */}
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
            color: color.fgMuted,
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
                  fontFamily: font.body,
                  fontSize: fontSize.base,
                  color: active ? color.fg : color.fgMuted,
                  textDecoration: 'none',
                  letterSpacing: '0.8px',
                  textTransform: 'uppercase' as const,
                  borderBottom: active ? `1px solid ${color.borderFocus}` : '1px solid transparent',
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
          fontFamily: font.mono,
          fontSize: fontSize.base,
          color: color.fgGhost,
          letterSpacing: '1px',
          textTransform: 'uppercase' as const,
        }}
      >
        ALPHA
      </span>
    </nav>
  );
}
