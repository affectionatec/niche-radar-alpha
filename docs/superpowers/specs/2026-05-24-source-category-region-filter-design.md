# Source Category & Region Filter Design

**Date**: 2026-05-24
**Status**: Implemented

## Problem

When opportunities are generated from collected data, users cannot tell which data sources contributed to each opportunity. Chinese social media sources (Xiaohongshu, Bilibili, Zhihu, Weibo, Douyin) need visual separation from global sources (Reddit, HN, GitHub, etc.) because they produce Chinese-language content targeting different markets.

## Solution

### Data Model

The linkage already exists: `niche_item_links` → `raw_items.source`. No schema changes needed.

**Backend enrichment**: The `GET /api/niches` endpoint now returns:
- `sources: string[]` — list of contributing data sources per opportunity
- `region: "global" | "chinese" | "mixed" | "unknown"` — computed from source membership

**New query param**: `?region=all|global|chinese` for server-side filtering.

### Source Classification

Single source of truth: `CN_SOURCES` set in `frontend/src/lib/tokens.ts` (frontend) and `niche_radar/api/server.py` (backend).

Chinese sources: `xiaohongshu`, `bilibili`, `zhihu`, `weibo`, `douyin`
Everything else: Global

### Frontend Changes

**Opportunities list page** (`/niches`):
- Region filter tabs: ALL REGIONS / 🌐 GLOBAL / 🇨🇳 CHINESE
- Source icon badges on each row (Chinese sources highlighted in warning color)
- Client-side filtering using `sources[]` from API

**Niche detail page** (`/niches/[id]`):
- SOURCE ITEMS grouped by region when both regions present
- Section headers: 🌐 GLOBAL (N) / 🇨🇳 CHINESE (N)
- Source icons and color-coded labels per item

### Performance

Backend source enrichment uses a single bulk query with GROUP BY instead of N+1 per-niche queries. The old `?source=` filter also benefits from this optimization.
