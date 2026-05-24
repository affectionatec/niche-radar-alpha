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

// ── Source registry ──────────────────────────────────────────────────────
// Single source of truth for all 17 data sources.
// Backend: niche_radar/collectors/__init__.py ALL_SOURCES

export const ALL_SOURCES = [
  'reddit', 'hn', 'google_trends', 'github', 'youtube',
  'product_hunt', 'stack_overflow', 'twitter', 'g2_reviews',
  'indie_hackers', 'app_store', 'play_store',
  // Chinese social media sources
  'xiaohongshu', 'bilibili', 'zhihu', 'weibo', 'douyin',
] as const;

export type SourceSlug = typeof ALL_SOURCES[number];

export const sourceLabel: Record<string, string> = {
  reddit: 'Reddit',
  hn: 'Hacker News',
  google_trends: 'Google Trends',
  github: 'GitHub Trending',
  youtube: 'YouTube',
  product_hunt: 'Product Hunt',
  stack_overflow: 'Stack Overflow',
  twitter: 'Twitter / X',
  g2_reviews: 'G2 Reviews',
  indie_hackers: 'Indie Hackers',
  app_store: 'App Store',
  play_store: 'Play Store',
  xiaohongshu: 'Xiaohongshu',
  bilibili: 'Bilibili',
  zhihu: 'Zhihu',
  weibo: 'Weibo',
  douyin: 'Douyin',
};

export const sourceIcon: Record<string, string> = {
  reddit: '◆',
  hn: '▲',
  github: '◎',
  google_trends: '◇',
  youtube: '▶',
  product_hunt: '◈',
  stack_overflow: '▣',
  twitter: '✕',
  g2_reviews: '★',
  indie_hackers: '◉',
  app_store: '▧',
  play_store: '▷',
  xiaohongshu: '📕',
  bilibili: '📺',
  zhihu: '💬',
  weibo: '🔥',
  douyin: '🎵',
};

export const sourceFreshnessRule: Record<string, string> = {
  reddit: 'reddit_hours',
  hn: 'hn_hours',
  github: 'github_hours',
  google_trends: 'google_trends_hours',
  youtube: 'youtube_hours',
  product_hunt: 'product_hunt_hours',
  stack_overflow: 'stack_overflow_hours',
  twitter: 'twitter_hours',
  g2_reviews: 'g2_reviews_hours',
  indie_hackers: 'indie_hackers_hours',
  app_store: 'app_store_hours',
  play_store: 'play_store_hours',
  xiaohongshu: 'xiaohongshu_hours',
  bilibili: 'bilibili_hours',
  zhihu: 'zhihu_hours',
  weibo: 'weibo_hours',
  douyin: 'douyin_hours',
};

// ── Source reliability labels ────────────────────────────────────────────
// Classification: how fragile is each collector?
// 🟢 Stable = official API / RSS, rarely breaks
// 🟡 Fragile = unofficial API, may change without notice
// 🟠 Brittle = scraping, anti-bot measures, breaks periodically
// 🔴 Very Brittle = aggressive anti-bot, requires auth/cookies, breaks often

export type ReliabilityLevel = 'stable' | 'fragile' | 'brittle' | 'very_brittle';

export const sourceReliability: Record<string, { level: ReliabilityLevel; label: string; color: string; icon: string; note: string }> = {
  reddit:         { level: 'stable',       label: 'Stable',       color: 'rgba(74,222,128,0.85)',  icon: '🟢', note: 'Official API via PRAW' },
  hn:             { level: 'stable',       label: 'Stable',       color: 'rgba(74,222,128,0.85)',  icon: '🟢', note: 'Official Algolia API' },
  google_trends:  { level: 'fragile',      label: 'Fragile',      color: 'rgba(251,191,36,0.85)',  icon: '🟡', note: 'Unofficial pytrends library' },
  github:         { level: 'stable',       label: 'Stable',       color: 'rgba(74,222,128,0.85)',  icon: '🟢', note: 'Official REST API' },
  youtube:        { level: 'stable',       label: 'Stable',       color: 'rgba(74,222,128,0.85)',  icon: '🟢', note: 'Official Data API v3' },
  product_hunt:   { level: 'fragile',      label: 'Fragile',      color: 'rgba(251,191,36,0.85)',  icon: '🟡', note: 'GraphQL API, auth changes possible' },
  stack_overflow: { level: 'stable',       label: 'Stable',       color: 'rgba(74,222,128,0.85)',  icon: '🟢', note: 'Official API v2.3' },
  twitter:        { level: 'very_brittle', label: 'Very Brittle', color: 'rgba(255,80,80,0.85)',   icon: '🔴', note: 'Cookie auth + GraphQL, breaks often' },
  g2_reviews:     { level: 'brittle',      label: 'Brittle',      color: 'rgba(255,160,60,0.85)',  icon: '🟠', note: 'HTML scraping, anti-bot' },
  indie_hackers:  { level: 'brittle',      label: 'Brittle',      color: 'rgba(255,160,60,0.85)',  icon: '🟠', note: 'HTML scraping' },
  app_store:      { level: 'fragile',      label: 'Fragile',      color: 'rgba(251,191,36,0.85)',  icon: '🟡', note: 'Unofficial itunes API / scraping' },
  play_store:     { level: 'fragile',      label: 'Fragile',      color: 'rgba(251,191,36,0.85)',  icon: '🟡', note: 'google-play-scraper' },
  xiaohongshu:    { level: 'stable',       label: 'Stable',       color: 'rgba(74,222,128,0.85)',  icon: '🟢', note: 'TikHub API' },
  bilibili:       { level: 'stable',       label: 'Stable',       color: 'rgba(74,222,128,0.85)',  icon: '🟢', note: 'Community API library' },
  zhihu:          { level: 'fragile',      label: 'Fragile',      color: 'rgba(251,191,36,0.85)',  icon: '🟡', note: 'Cookie-based scraping' },
  weibo:          { level: 'fragile',      label: 'Fragile',      color: 'rgba(251,191,36,0.85)',  icon: '🟡', note: 'Cookie-based scraping' },
  douyin:         { level: 'very_brittle', label: 'Very Brittle', color: 'rgba(255,80,80,0.85)',   icon: '🔴', note: 'TikHub API, aggressive anti-bot' },
};

// ── LLM Provider registry ────────────────────────────────────────────────
// Each provider maps to a backend provider type (openai_compat or anthropic)
// plus a curated model list and default base URL.

export interface LLMProvider {
  id: string;
  label: string;
  backendProvider: 'openai_compat' | 'anthropic';
  baseUrl: string;           // default base URL (empty = provider default)
  models: string[];          // curated model list
  defaultModel: string;
  needsBaseUrl: boolean;     // show base URL field?
  needsApiKey: boolean;      // require API key?
}

export const LLM_PROVIDERS: LLMProvider[] = [
  {
    id: 'deepseek',
    label: 'DeepSeek',
    backendProvider: 'openai_compat',
    baseUrl: 'https://api.deepseek.com',
    models: ['deepseek-v4-flash', 'deepseek-v4-pro', 'deepseek-v4-pro-max', 'deepseek-chat', 'deepseek-reasoner'],
    defaultModel: 'deepseek-v4-flash',
    needsBaseUrl: false,
    needsApiKey: true,
  },
  {
    id: 'openai',
    label: 'OpenAI',
    backendProvider: 'openai_compat',
    baseUrl: '',
    models: ['gpt-5.2', 'gpt-5.2-mini', 'gpt-5.1', 'gpt-4.1', 'gpt-4.1-mini', 'gpt-4.1-nano', 'o3', 'o4-mini'],
    defaultModel: 'gpt-4.1-mini',
    needsBaseUrl: false,
    needsApiKey: true,
  },
  {
    id: 'anthropic',
    label: 'Anthropic',
    backendProvider: 'anthropic',
    baseUrl: '',
    models: ['claude-opus-4-7', 'claude-sonnet-4-6', 'claude-haiku-4-5-20251001', 'claude-sonnet-4-20250514'],
    defaultModel: 'claude-sonnet-4-6',
    needsBaseUrl: false,
    needsApiKey: true,
  },
  {
    id: 'groq',
    label: 'Groq',
    backendProvider: 'openai_compat',
    baseUrl: 'https://api.groq.com/openai/v1',
    models: ['meta-llama/llama-4-scout-17b-16e-instruct', 'llama-3.3-70b-versatile', 'llama-3.1-8b-instant', 'qwen/qwen3-32b', 'mixtral-8x7b-32768'],
    defaultModel: 'llama-3.3-70b-versatile',
    needsBaseUrl: false,
    needsApiKey: true,
  },
  {
    id: 'google',
    label: 'Google Gemini',
    backendProvider: 'openai_compat',
    baseUrl: 'https://generativelanguage.googleapis.com/v1beta/openai/',
    models: ['gemini-3.1-pro', 'gemini-3.1-flash', 'gemini-3.5-flash', 'gemini-2.5-pro', 'gemini-2.5-flash'],
    defaultModel: 'gemini-2.5-flash',
    needsBaseUrl: false,
    needsApiKey: true,
  },
  {
    id: 'xai',
    label: 'xAI (Grok)',
    backendProvider: 'openai_compat',
    baseUrl: 'https://api.x.ai/v1',
    models: ['grok-4.3', 'grok-3', 'grok-3-mini'],
    defaultModel: 'grok-4.3',
    needsBaseUrl: false,
    needsApiKey: true,
  },
  {
    id: 'ollama',
    label: 'Ollama (Local)',
    backendProvider: 'openai_compat',
    baseUrl: 'http://localhost:11434/v1',
    models: ['llama3.3', 'qwen2.5', 'deepseek-r1', 'gemma2', 'phi4', 'mistral'],
    defaultModel: 'llama3.3',
    needsBaseUrl: true,
    needsApiKey: false,
  },
  {
    id: 'custom',
    label: 'Custom',
    backendProvider: 'openai_compat',
    baseUrl: '',
    models: [],
    defaultModel: '',
    needsBaseUrl: true,
    needsApiKey: true,
  },
];

// ─── SCORING DIMENSIONS ────────────────────────────────────────────────
export const SCORING_DIMENSIONS: {
  key: string;
  label: string;
  description: string;
  defaultWeight: number;
}[] = [
  { key: 'problem_clarity', label: 'Problem Clarity', description: 'How clearly defined the user pain is', defaultWeight: 1.0 },
  { key: 'market_size', label: 'Market Size', description: 'TAM/SAM estimation from market signals', defaultWeight: 1.5 },
  { key: 'willingness_to_pay', label: 'Willingness to Pay', description: 'Evidence of users paying for similar solutions', defaultWeight: 2.0 },
  { key: 'competition_gap', label: 'Competition Gap', description: 'How underserved the niche currently is', defaultWeight: 1.5 },
  { key: 'technical_feasibility', label: 'Technical Feasibility', description: 'Complexity to build an MVP', defaultWeight: 1.0 },
  { key: 'distribution_clarity', label: 'Distribution Clarity', description: 'How easy to reach the target audience', defaultWeight: 1.5 },
  { key: 'trend_momentum', label: 'Trend Momentum', description: 'Growth trajectory of the problem space', defaultWeight: 1.0 },
];
