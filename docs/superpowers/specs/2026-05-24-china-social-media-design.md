# China Social Media Integration — Design Spec

**Date:** 2026-05-24
**Branch:** `feature/china-social-media`
**Status:** Draft — awaiting user review

---

## 1. Overview

Integrate 5 Chinese social media platforms into the Niche Radar collector pipeline, expanding trend intelligence beyond English-language sources. Each platform becomes a new collector following the existing `BaseCollector` pattern.

### Platforms

| # | Platform | Chinese | Primary Signal | Stability Tier |
|---|----------|---------|----------------|----------------|
| 1 | Xiaohongshu | 小红书 | Product reviews, lifestyle pain-points, "I wish" posts | ⭐⭐⭐ Stable |
| 2 | Bilibili | B站 | Tech tutorials, dev tool complaints, trending topics | ⭐⭐⭐ Stable |
| 3 | Zhihu | 知乎 | Q&A pain-points, "how to solve X" threads | ⭐⭐ Fragile |
| 4 | Weibo | 微博 | Trending topics, public complaints, viral pain-points | ⭐⭐ Fragile |
| 5 | Douyin | 抖音 | Trending product categories, creator pain-points | ⭐ Very Brittle |

### Why These 5

- **Xiaohongshu**: China's #1 product discovery platform (300M+ MAU). Rich "I wish there was..." and product comparison content — directly maps to niche radar's pain-point discovery model.
- **Bilibili**: China's YouTube for tech/dev community (350M+ MAU). Video comments surface tool pain-points in Chinese dev ecosystem.
- **Zhihu**: China's Quora (100M+ MAU). High-quality Q&A with explicit "how to solve X" and "looking for tool" signals.
- **Weibo**: China's Twitter (580M+ MAU). Trending topics reveal mass market pain-points and emerging categories.
- **Douyin**: China's TikTok (750M+ DAU). Creator economy pain-points, trending product categories.

---

## 2. Architecture

### 2.1 Connector Strategy

Two connector approaches, chosen per platform:

**A. TikHub Unified API** (Xiaohongshu, Douyin)
- Single paid API key via [tikhub.io](https://tikhub.io)
- PyPI package: `tikhub`
- Covers keyword search, post details, comments, trending
- Rate-limited but stable; handles anti-bot internally

**B. Open-Source Libraries** (Bilibili, Weibo, Zhihu)
- Bilibili: `bilibili-api-python` (PyPI, well-maintained, async)
- Weibo: `weiboSpider` approach — cookie-based HTML scraping via requests
- Zhihu: Custom scraping via `httpx` + JSON API endpoints (discovered via network sniffing)

### 2.2 New Files

```
niche_radar/collectors/
├── xiaohongshu.py      # TikHub SDK connector
├── bilibili.py         # bilibili-api-python wrapper
├── zhihu.py            # Custom httpx scraper
├── weibo.py            # Cookie-based web scraper
└── douyin.py           # TikHub SDK connector
```

### 2.3 Registration Points

Each new source must be registered in:

1. **Backend:** `niche_radar/collectors/__init__.py` — add to `ALL_SOURCES` and `_get_collector()`
2. **Frontend tokens:** `frontend/src/lib/tokens.ts` — add to `ALL_SOURCES`, `sourceLabel`, `sourceIcon`, `sourceFreshnessRule`, `sourceReliability`
3. **CONTEXT.md** — add domain terms for CN platforms

### 2.4 Credential Schema

Each collector declares its credential requirements via `CREDENTIAL_SCHEMA`. Examples:

- **Xiaohongshu/Douyin (TikHub):** `[{key: "tikhub_api_key", label: "TikHub API Key", secret: true, optional: false}]`
- **Bilibili:** `[{key: "bilibili_sessdata", label: "SESSDATA Cookie", secret: true, optional: true}]` (optional — public API works without auth for basic search)
- **Weibo:** `[{key: "weibo_cookie", label: "Weibo Cookie String", secret: true, optional: false}]`
- **Zhihu:** `[{key: "zhihu_cookie", label: "Zhihu Cookie String", secret: true, optional: false}]`

### 2.5 Search Queries (Chinese)

Each collector gets Chinese-language equivalents of the pain-point search queries:

```python
CN_SEARCH_QUERIES = [
    "有没有什么工具",        # "is there a tool that"
    "好用的替代品",          # "good alternative to"
    "太贵了",               # "pricing is crazy"
    "手动操作太麻烦",        # "manual process is tedious"
    "有人做过",             # "has anyone built"
    "怎么自动化",           # "how to automate"
    "吐槽",                # "complaints about"
    "求推荐",              # "looking for recommendations"
    "效率太低",             # "too inefficient"
    "痛点",                # "pain point"
]
```

### 2.6 Item Normalization

All CN collectors output the standard `CollectorResult` with items containing:

```python
{
    "source_id": str,       # Platform-specific unique ID
    "title": str,           # Post title or first 100 chars (Chinese OK)
    "body": str,            # Full text content
    "url": str,             # Link to original post
    "score": int,           # Likes/upvotes/engagement metric
    "comment_count": int,   # Comment count
    "posted_at": str,       # ISO timestamp
    "metadata": {
        "language": "zh",   # Always "zh" for CN sources
        "platform": str,    # "xiaohongshu" | "bilibili" | etc.
        "author": str,      # Author username
        "tags": list[str],  # Platform-specific tags/topics
    }
}
```

---

## 3. LLM Pipeline Considerations

### 3.1 Chinese Content in Agents

The 8-agent LLM pipeline (A1-A8) must handle Chinese-language raw items:

- **A1 (Intake):** Already receives raw text — Chinese content passes through.
- **A2-A8:** System prompts already instruct agents to analyze "text". LLM providers (OpenAI, DeepSeek, etc.) natively understand Chinese.
- **No prompt changes needed** — the agents analyze meaning, not language-specific patterns.

### 3.2 Mixed-Language Clustering

Items from CN sources will naturally cluster separately from EN sources in Phase B (clustering) due to semantic distance. This is actually desirable — CN-specific niches should form their own clusters.

### 3.3 DeepSeek Advantage

For users running DeepSeek as their LLM provider, Chinese content analysis will be particularly strong since DeepSeek excels at Chinese NLP.

---

## 4. Frontend Changes

### 4.1 Token Registry Updates

```typescript
// ALL_SOURCES — append CN sources
"xiaohongshu", "bilibili", "zhihu", "weibo", "douyin"

// sourceLabel
xiaohongshu: 'XIAOHONGSHU',
bilibili: 'BILIBILI',
zhihu: 'ZHIHU',
weibo: 'WEIBO',
douyin: 'DOUYIN',

// sourceIcon
xiaohongshu: '📕',
bilibili: '📺',
zhihu: '💬',
weibo: '🔥',
douyin: '🎵',

// sourceReliability
xiaohongshu: { level: 'stable', label: 'STABLE', icon: '🟢', note: 'TikHub API' },
bilibili:    { level: 'stable', label: 'STABLE', icon: '🟢', note: 'Community API lib' },
zhihu:       { level: 'fragile', label: 'FRAGILE', icon: '🟡', note: 'Cookie-based scraping' },
weibo:       { level: 'fragile', label: 'FRAGILE', icon: '🟡', note: 'Cookie-based scraping' },
douyin:      { level: 'brittle', label: 'VERY BRITTLE', icon: '🔴', note: 'TikHub API, aggressive anti-bot' },
```

### 4.2 SystemHealth Grid

Currently `repeat(4, 1fr)` for 12 sources. With 17 sources:
- Option A: Keep 4-col → 4×4 + 1 orphan (bad)
- Option B: Switch to `repeat(auto-fill, minmax(220px, 1fr))` with a max — but this caused the original orphan issue
- **Recommended:** Use a CSS variable or JS-computed column count: `repeat(Math.min(sources.length, 6), 1fr)` capped at 6 columns → 6-6-5 for 17 sources, or wait until we have 18 sources (6×3 perfect) by adding one more CN platform

### 4.3 Settings — Source Config

The existing `/settings/sources/[source]` page auto-renders credential fields from `CREDENTIAL_SCHEMA`. No frontend changes needed for individual source config pages.

---

## 5. Dependencies

### New Python Packages

```
tikhub>=0.1.0           # Xiaohongshu + Douyin unified API
bilibili-api-python>=16.0  # Bilibili community API
httpx>=0.27             # Already likely installed; for Zhihu async scraping
```

Weibo and Zhihu use `requests`/`httpx` + `beautifulsoup4` (already in the project or standard).

### Environment Variables / Settings

```
TIKHUB_API_KEY=         # Required for Xiaohongshu + Douyin
BILIBILI_SESSDATA=      # Optional — improves Bilibili rate limits
WEIBO_COOKIE=           # Required for Weibo
ZHIHU_COOKIE=           # Required for Zhihu
```

All stored via the existing source credential system (`source_credentials` table).

---

## 6. Implementation Phases

### Phase 1: Stable Sources (Week 1)
1. Xiaohongshu collector (TikHub SDK)
2. Bilibili collector (bilibili-api-python)
3. Frontend token registration for all 5 CN sources
4. Update `ALL_SOURCES`, `_get_collector()`, `CONTEXT.md`

### Phase 2: Fragile Sources (Week 2)
5. Zhihu collector (custom httpx scraping)
6. Weibo collector (cookie-based scraping)
7. Grid layout adjustment for 17 sources

### Phase 3: Brittle Source + Polish (Week 3)
8. Douyin collector (TikHub SDK)
9. CN-specific search queries tuning
10. Integration testing with live APIs
11. Documentation updates (README, ARCHITECTURE.md)

---

## 7. Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| TikHub API pricing changes | Medium | Xiaohongshu/Douyin collectors degrade to "unconfigured" if no key |
| Weibo cookie expiration | High | Auto-detect expired cookies, warn user in SystemHealth |
| Zhihu anti-bot blocks | Medium | Rotate user-agents, respect rate limits, graceful failure |
| Chinese content confuses EN-focused LLM | Low | DeepSeek/GPT-4o handle Chinese natively; add `language: zh` metadata for filtering |
| Grid layout breaks with 17 sources | Low | Test layout with 17 items before merging |

---

## 8. Success Criteria

- [ ] All 5 CN collectors follow `BaseCollector` interface
- [ ] Each collector has `CREDENTIAL_SCHEMA` for Settings UI
- [ ] `test_connection()` validates credentials for each source
- [ ] CN sources appear in SystemHealth, DataFreshness, pipeline source dropdown
- [ ] Pipeline runs correctly with mixed EN+CN items
- [ ] No regressions on existing 12 sources
- [ ] README updated with CN source documentation

---

## 9. Out of Scope

- Machine translation of CN content to English (LLMs handle this implicitly)
- CN-specific UI localization (i18n)
- WeChat (requires enterprise API partnership, no public access)
- Baidu Tieba (declining platform, low signal quality)
