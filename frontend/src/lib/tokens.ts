// Design tokens — single source of truth for the xAI-inspired dark brutalist theme.
// Reference: DESIGN.md

export const color = {
  bg: '#1f2228',
  fg: '#ffffff',
  fgSecondary: 'rgba(255,255,255,0.7)',
  fgMuted: 'rgba(255,255,255,0.5)',
  fgDisabled: 'rgba(255,255,255,0.35)',
  fgGhost: 'rgba(255,255,255,0.25)',

  border: 'rgba(255,255,255,0.1)',
  borderStrong: 'rgba(255,255,255,0.2)',
  borderFocus: 'rgba(255,255,255,0.5)',

  surface: 'rgba(255,255,255,0.03)',
  surfaceHover: 'rgba(255,255,255,0.06)',
  surfaceActive: 'rgba(255,255,255,0.08)',
  surfaceSelected: 'rgba(255,255,255,0.12)',

  success: 'rgba(74,222,128,0.85)',
  successMuted: 'rgba(74,222,128,0.5)',
  error: 'rgba(255,80,80,0.85)',
  errorMuted: 'rgba(255,80,80,0.5)',
  warning: 'rgba(251,191,36,0.85)',
  warningMuted: 'rgba(251,191,36,0.5)',
  info: 'rgba(125,211,252,0.9)',
} as const;

export const font = {
  mono: 'var(--font-geist-mono)',
  body: 'var(--font-inter)',
} as const;

export const fontSize = {
  xs: '9px',
  sm: '10px',
  base: '11px',
  md: '12px',
  lg: '13px',
  xl: '14px',
  '2xl': '18px',
  '3xl': '20px',
  '4xl': '28px',
  '5xl': '30px',
} as const;

export const spacing = {
  xs: '4px',
  sm: '8px',
  md: '12px',
  lg: '16px',
  xl: '20px',
  '2xl': '24px',
  '3xl': '32px',
  '4xl': '48px',
  '5xl': '64px',
} as const;

// Shared inline-style fragments for common UI patterns
export const text = {
  pageTitle: {
    fontFamily: font.body,
    fontSize: fontSize['5xl'],
    fontWeight: 400,
    color: color.fg,
  },
  sectionTitle: {
    fontFamily: font.body,
    fontSize: fontSize['3xl'],
    fontWeight: 400,
    color: color.fg,
  },
  label: {
    fontFamily: font.body,
    fontSize: fontSize.base,
    color: color.fgDisabled,
    textTransform: 'uppercase' as const,
    letterSpacing: '0.8px',
  },
  mono: {
    fontFamily: font.mono,
    fontSize: fontSize.base,
    letterSpacing: '0.5px',
  },
  monoSmall: {
    fontFamily: font.mono,
    fontSize: fontSize.sm,
    letterSpacing: '0.5px',
  },
  body: {
    fontFamily: font.body,
    fontSize: fontSize.lg,
    color: color.fgDisabled,
  },
} as const;

export const button = {
  primary: {
    background: color.fg,
    border: 'none',
    color: color.bg,
    fontFamily: font.mono,
    fontSize: fontSize.base,
    fontWeight: 600,
    letterSpacing: '1px',
    textTransform: 'uppercase' as const,
    padding: '0 20px',
    height: '40px',
    cursor: 'pointer',
  },
  secondary: {
    background: 'transparent',
    border: `1px solid ${color.borderStrong}`,
    color: color.fg,
    fontFamily: font.mono,
    fontSize: fontSize.base,
    letterSpacing: '1px',
    textTransform: 'uppercase' as const,
    padding: '0 20px',
    height: '40px',
    cursor: 'pointer',
  },
  ghost: {
    background: 'transparent',
    border: `1px solid ${color.border}`,
    color: color.fgMuted,
    fontFamily: font.mono,
    fontSize: fontSize.sm,
    letterSpacing: '0.5px',
    textTransform: 'uppercase' as const,
    padding: '7px 12px',
    cursor: 'pointer',
  },
} as const;

export const input = {
  base: {
    width: '100%',
    background: color.surfaceHover,
    border: `1px solid ${color.border}`,
    color: color.fg,
    fontFamily: font.mono,
    fontSize: fontSize.md,
    letterSpacing: '0.5px',
    padding: '10px 14px',
    outline: 'none',
    boxSizing: 'border-box' as const,
  },
} as const;

// Verdict colors used in niche tables/cards
export const verdictColor: Record<string, string> = {
  GO: color.success,
  'NO-GO': color.error,
  PIVOT: color.warning,
};

// Trend display
export const trendEmoji: Record<string, string> = {
  growing: '📈',
  stable: '➡️',
  declining: '📉',
};

export function trendColor(label: string | null): string {
  if (label === 'growing') return color.success;
  if (label === 'declining') return color.error;
  return color.fgDisabled;
}

// Tier display
export const tierLabel: Record<string, string> = {
  high_priority: 'HIGH',
  watchlist: 'WATCH',
  archive: 'ARCH',
};

// Status colors for pipeline jobs
export function jobStatusColor(status: string): string {
  if (status === 'done') return 'rgba(255,255,255,0.9)';
  if (status === 'failed') return color.error;
  if (status === 'running') return color.fgSecondary;
  return color.fgGhost;
}
