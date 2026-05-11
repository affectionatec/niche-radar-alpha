# Niche Radar Alpha — MVP Specification

> **Codename:** NicheRadar
> **Version:** 0.1.0-alpha
> **Last updated:** 2026-05-11

---

## 1. Executive Summary

**Vision:** Build a self-hosted, automated trend-intelligence pipeline that continuously monitors the top public platforms on the internet, extracts emerging topics and user pain-points, cross-validates them against search-trend data, and produces a daily scored report of high-potential niche opportunities.

**Key Goals:**

| # | Goal | Detail |
|---|------|--------|
| 1 | Multi-source ingestion | Crawl the top 5 high-signal public websites for trending content |
| 2 | Open-source stack | Use only free, open-source APIs and crawlers — no paid SaaS dependencies |
| 3 | Portable deployment | Run via **Docker Compose** (production) or bare-metal **local** setup (development) |
| 4 | Actionable output | Generate a daily scored report (JSON + Markdown) ranking the most promising niches |

---

## 2. Target Data Sources (Top 5)

The MVP focuses on five high-value, publicly accessible platforms that collectively cover search behavior, developer communities, tech products, and mainstream social trends.

### 2.1 Google Trends

| Attribute | Value |
|-----------|-------|
| **Why** | The authoritative signal for search-interest trajectory over time. Reveals whether a topic is rising, stable, or declining. |
| **Open-source library** | [`trendspyg`](https://pypi.org/project/trendspyg/) (MIT) — free, no API key, 188K+ config combinations. Fallback: [`pytrends`](https://github.com/GeneralMills/pytrends) (Apache-2.0). |
| **Data to collect** | Interest-over-time (past 12 months), related queries (rising), related topics (rising), regional breakdown. |
| **Frequency** | Every 6 hours for tracked keywords; daily full sweep for new keyword discovery. |

### 2.2 Reddit

| Attribute | Value |
|-----------|-------|
| **Why** | The richest source of unfiltered user pain-points, feature requests, and "is there a tool that..." signals in the English-speaking internet. |
| **Open-source library** | [`PRAW`](https://praw.readthedocs.io/) (BSD-2) — official Python Reddit API Wrapper (requires free Reddit API credentials). |
| **Target subreddits (initial)** | `r/SaaS`, `r/selfhosted`, `r/webdev`, `r/smallbusiness`, `r/Entrepreneur`, `r/sideproject`, `r/macapps`, `r/devops`, `r/dataengineering`, `r/nocode` |
| **Pain-point trigger phrases** | `"is there a tool"`, `"I wish there was"`, `"alternative to"`, `"how do you automate"`, `"pricing is crazy"`, `"looking for"`, `"recommend a"`, `"frustrated with"` |
| **Data to collect** | Top 50 hot posts per subreddit (last 24 h), top-level comments (score >= 5), post score, comment count, post flair. |
| **Frequency** | Every 4 hours. |

### 2.3 Hacker News

| Attribute | Value |
|-----------|-------|
| **Why** | Early-signal hub for developer tools, AI products, and technical infrastructure trends. Show HN and Ask HN threads surface real launches and real needs. |
| **Open-source library** | [`haxor`](https://pypi.org/project/haxor/) (MIT) — Python wrapper for the [official HN Firebase API](https://github.com/HackerNews/API) (free, no API key, no rate limit). |
| **Data to collect** | Top stories (50), Best stories (50), Ask HN (30), Show HN (30), including title, URL, score, comment count, full comment trees for top items. |
| **Frequency** | Every 2 hours. |

### 2.4 GitHub Trending

| Attribute | Value |
|-----------|-------|
| **Why** | Reveals which open-source projects are gaining sudden traction — a strong proxy for developer tool demand and emerging tech categories. |
| **Open-source approach** | Scrape [github.com/trending](https://github.com/trending) via `requests` + `BeautifulSoup` (no official API for trending). Alternatively use the GitHub REST API `search/repositories` sorted by stars with `created:>YYYY-MM-DD`. |
| **Data to collect** | Repo name, description, language, stars today, total stars, forks, topics/tags. |
| **Frequency** | Every 6 hours (daily, weekly, monthly views). |

### 2.5 YouTube (Trending and Search)

| Attribute | Value |
|-----------|-------|
| **Why** | Mainstream consumer trend signal with massive reach. "How to" and product-review videos reveal real purchasing intent. |
| **Open-source library** | [`scrapetube`](https://pypi.org/project/scrapetube/) (MIT) — scrapes YouTube without API key. Backup: YouTube Data API v3 (free tier: 10,000 units/day). |
| **Data to collect** | Trending videos by category, search results for seed keywords (title, view count, like count, publish date, channel). |
| **Frequency** | Every 8 hours for trending; on-demand for keyword searches. |

---

## 3. System Architecture

```
+----------------------------------------------------------+
|                     Niche Radar Alpha                    |
+--------------+---------------+---------------------------+
|  Scheduler   |   Ingestion   |  Validation & Scoring     |
|  (APScheduler|   Workers     |  Engine                   |
|   or cron)   |               |                           |
|              | +-----------+ | +-----------------------+ |
|  +--------+  | | Google    | | | Engagement Scorer     | |
|  | Timer  |--+>| Trends    | | | Trend Slope Analyzer  | |
|  | Events |  | | Collector | | | Search Volume Checker | |
|  +--------+  | +-----------+ | | Composite Niche Score | |
|              | | Reddit    | | +-----------+-----------+ |
|              | | Collector | |             |             |
|              | +-----------+ | +-----------v-----------+ |
|              | | HN        |-+>|   SQLite / PostgreSQL | |
|              | | Collector | | |   (Structured Store)  | |
|              | +-----------+ | +-----------+-----------+ |
|              | | GitHub    | |             |             |
|              | | Trending  | | +-----------v-----------+ |
|              | +-----------+ | |  Report Generator     | |
|              | | YouTube   | | |  (JSON + Markdown)    | |
|              | | Trending  | | +-----------------------+ |
|              | +-----------+ |                           |
+--------------+---------------+---------------------------+
|  Infrastructure: Docker Compose / SQLite / Python 3.11+  |
+----------------------------------------------------------+
```

### 3.1 Component Overview

| Component | Responsibility | Key Libraries |
|-----------|---------------|---------------|
| **Scheduler** | Trigger collection jobs on configured intervals | `APScheduler` (MIT) |
| **Ingestion Workers** | Fetch, normalize, and store raw data from each source | `PRAW`, `trendspyg`/`pytrends`, `haxor`, `requests`+`BeautifulSoup`, `scrapetube` |
| **Validation Engine** | Score each discovered niche across multiple dimensions | `trendspyg` (trend slope), custom scorers |
| **Data Store** | Persist raw + scored data | `SQLite` (local / default), `PostgreSQL` (Docker Compose production) |
| **Report Generator** | Produce human-readable and machine-readable output | `Jinja2` (Markdown templates), `json` stdlib |

---

## 4. Validation & Scoring Engine

Inspired by quantitative backtesting, each candidate niche is scored across four dimensions to filter signal from noise.

### 4.1 Four-Dimensional Cross-Validation

#### Dimension 1 — Engagement Momentum (weight: 0.25)

Measures how much organic discussion a topic is generating.

| Metric | Source | Scoring Logic |
|--------|--------|---------------|
| Upvotes / score | Reddit, HN | Normalize to 0-100 using percentile rank across the day's dataset |
| Comment velocity | Reddit, HN | (comments in last 6 h) / (total comments) — higher = still growing |
| Star velocity | GitHub Trending | Stars earned today vs. 7-day average |

#### Dimension 2 — Search Interest Trend (weight: 0.30)

Measures whether real people are actively searching for this topic.

| Metric | Source | Scoring Logic |
|--------|--------|---------------|
| 12-month interest slope | Google Trends (`trendspyg`) | Linear regression slope of weekly interest values. Positive slope = score up; negative = score down. |
| Breakout queries | Google Trends (related queries, "rising") | Breakout (>5000%) = 100 pts; >200% = 70 pts |
| Search volume proxy | Google Trends absolute scale | Normalize peak interest (0-100 from Trends) directly |

#### Dimension 3 — Content & Product Gap (weight: 0.25)

Measures whether existing solutions are inadequate.

| Metric | Source | Scoring Logic |
|--------|--------|---------------|
| Pain-point phrase hits | Reddit, HN comments | Count of trigger-phrase matches (see section 2.2) in top comments |
| "Alternative to" mentions | Reddit | Count of posts/comments mentioning alternatives to established tools |
| Show HN / sideproject signals | HN, Reddit (`r/sideproject`) | New launches in this space = validates demand but check saturation |

#### Dimension 4 — Market Traction (weight: 0.20)

Measures whether there is commercial momentum.

| Metric | Source | Scoring Logic |
|--------|--------|---------------|
| YouTube view counts | YouTube search for seed keywords | Average views on top 10 recent videos (>10K avg = high signal) |
| GitHub repo growth | GitHub Trending | Total stars + fork ratio as adoption proxy |
| Trending rank persistence | All sources | Number of consecutive collection cycles a topic appears in top results |

### 4.2 Composite Niche Score

```
Niche Score = (Engagement x 0.25) + (Search Trend x 0.30) + (Content Gap x 0.25) + (Market Traction x 0.20)
```

All dimension sub-scores are normalized to **0-100** before weighting.

| Score Range | Action |
|-------------|--------|
| **< 40** | Discard — insufficient signal |
| **40 - 64** | Archive — store for future re-evaluation |
| **65 - 79** | Watchlist — include in daily report, monitor for trend acceleration |
| **>= 80** | **High Priority** — flag in report, push notification (if configured) |

---

## 5. Data Model

### 5.1 Core Tables

```sql
-- Raw ingested items from all sources
CREATE TABLE raw_items (
    id              TEXT PRIMARY KEY,       -- UUID
    source          TEXT NOT NULL,           -- 'reddit' | 'hn' | 'github' | 'google_trends' | 'youtube'
    source_id       TEXT,                    -- Platform-native ID
    title           TEXT,
    body            TEXT,
    url             TEXT,
    score           INTEGER,                -- Upvotes / stars / views
    comment_count   INTEGER,
    metadata        JSON,                   -- Source-specific fields
    collected_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Extracted niche candidates after NLP / grouping
CREATE TABLE niche_candidates (
    id              TEXT PRIMARY KEY,
    keyword         TEXT NOT NULL,           -- Primary keyword / phrase
    aliases         JSON,                    -- Related terms
    first_seen      TIMESTAMP,
    last_seen       TIMESTAMP,
    occurrence_count INTEGER DEFAULT 1
);

-- Scored results per evaluation cycle
CREATE TABLE niche_scores (
    id              TEXT PRIMARY KEY,
    niche_id        TEXT REFERENCES niche_candidates(id),
    engagement      REAL,                   -- 0-100
    search_trend    REAL,                   -- 0-100
    content_gap     REAL,                   -- 0-100
    market_traction REAL,                   -- 0-100
    composite_score REAL,                   -- Weighted composite 0-100
    scored_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Historical trend snapshots for each niche
CREATE TABLE trend_snapshots (
    id              TEXT PRIMARY KEY,
    niche_id        TEXT REFERENCES niche_candidates(id),
    source          TEXT,                   -- 'google_trends' | 'reddit' | etc.
    data            JSON,                   -- Time-series or structured payload
    snapshot_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 6. Deployment

### 6.1 Local Development (Bare-Metal)

**Requirements:** Python 3.11+, pip, SQLite 3.

```bash
# Clone and set up
git clone <repo-url> && cd niche-radar-alpha
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
.venv\Scripts\activate           # Windows

# Install dependencies
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env — add Reddit API credentials, optional YouTube API key

# Run
python -m niche_radar            # One-shot collection + scoring
python -m niche_radar --serve    # Start scheduler (continuous)
```

### 6.2 Docker Compose (Production / CI)

```yaml
# docker-compose.yml
version: "3.9"

services:
  radar:
    build: .
    container_name: niche-radar
    env_file: .env
    volumes:
      - ./data:/app/data          # SQLite DB + reports persisted here
      - ./reports:/app/reports    # Generated Markdown reports
    restart: unless-stopped
    command: ["python", "-m", "niche_radar", "--serve"]

  # Optional: PostgreSQL for larger-scale deployments
  db:
    image: postgres:16-alpine
    container_name: niche-radar-db
    environment:
      POSTGRES_DB: niche_radar
      POSTGRES_USER: radar
      POSTGRES_PASSWORD: ${DB_PASSWORD:-changeme}
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    profiles: ["postgres"]        # Only started with --profile postgres

volumes:
  pgdata:
```

```bash
# Run with SQLite (default)
docker compose up -d radar

# Run with PostgreSQL
docker compose --profile postgres up -d
```

### 6.3 Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p /app/data /app/reports

ENV PYTHONUNBUFFERED=1
ENTRYPOINT ["python", "-m", "niche_radar"]
CMD ["--serve"]
```

---

## 7. Configuration

All configuration is via environment variables (loaded from `.env`).

```ini
# .env.example

# -- Reddit (required — free at https://www.reddit.com/prefs/apps) --
REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_client_secret
REDDIT_USER_AGENT=NicheRadar/0.1 by YourUsername

# -- Google Trends --
# No credentials needed — trendspyg works without an API key.

# -- Hacker News --
# No credentials needed — official Firebase API is public.

# -- GitHub Trending --
# No credentials needed for scraping. Optional PAT for higher rate limits:
GITHUB_TOKEN=

# -- YouTube (optional — enables richer data) --
YOUTUBE_API_KEY=

# -- Database --
DATABASE_URL=sqlite:///data/niche_radar.db
# For PostgreSQL: DATABASE_URL=postgresql://radar:changeme@db:5432/niche_radar

# -- Scheduler --
COLLECTION_INTERVAL_HOURS=4     # How often to run full collection
SCORING_INTERVAL_HOURS=6        # How often to re-score niches

# -- Report --
REPORT_OUTPUT_DIR=./reports
REPORT_FORMAT=markdown           # 'markdown' | 'json' | 'both'

# -- Notifications (optional) --
SLACK_WEBHOOK_URL=
DISCORD_WEBHOOK_URL=
```

---

## 8. Output: Daily Niche Report

Each scoring cycle generates a report. Example structure:

```markdown
# Niche Radar — Daily Report
**Generated:** 2026-05-11 06:00 UTC | **Cycle:** #142

## High Priority (Score >= 80)

### 1. "AI-powered browser testing" — Score: 87
| Dimension        | Score | Key Signal |
|------------------|-------|------------|
| Engagement       | 82    | 3 Reddit threads (avg 240 upvotes), 2 HN front-page items |
| Search Trend     | 91    | Google Trends: +45% slope, "breakout" related query |
| Content Gap      | 88    | 12 "looking for" / "alternative to Selenium" mentions |
| Market Traction  | 79    | 2 GitHub repos trending (1.2K stars/week), YouTube avg 28K views |

**Related keywords:** browser automation AI, AI QA testing, codeless testing tool
**Sources:** [Reddit](...), [HN](...), [GitHub](...)

---

## Watchlist (Score 65-79)
| # | Niche | Score | Top Signal |
|---|-------|-------|------------|
| 1 | Self-hosted analytics | 74 | Reddit engagement + rising Google Trends |
| 2 | ... | ... | ... |

## Archived (Score 40-64)
_15 niches archived this cycle. See reports/2026-05-11-archive.json._
```

A machine-readable `report.json` is also generated for downstream automation.

---

## 9. Technology Stack Summary

| Layer | Technology | License | API Key Required? |
|-------|-----------|---------|-------------------|
| Runtime | Python 3.11+ | PSF | — |
| Google Trends | `trendspyg` (primary) / `pytrends` (fallback) | MIT / Apache-2.0 | No |
| Reddit | `PRAW` | BSD-2 | Yes (free Reddit dev app) |
| Hacker News | `haxor` + official Firebase API | MIT | No |
| GitHub Trending | `requests` + `BeautifulSoup4` / GitHub REST API | Apache-2.0 | No (optional PAT) |
| YouTube | `scrapetube` (primary) / YouTube Data API v3 (fallback) | MIT | No / Yes (free tier) |
| Scheduling | `APScheduler` | MIT | — |
| Database | SQLite (default) / PostgreSQL (optional) | Public domain / PostgreSQL License | — |
| NLP / Keywords | `spaCy` or `keybert` | MIT | — |
| Report templating | `Jinja2` | BSD-3 | — |
| Containerization | Docker + Docker Compose | Apache-2.0 | — |

---

## 10. Project Structure

```
niche-radar-alpha/
|-- docker-compose.yml
|-- Dockerfile
|-- requirements.txt
|-- .env.example
|-- spec.md                      # This document
|-- README.md
|
|-- niche_radar/                 # Main Python package
|   |-- __init__.py
|   |-- __main__.py              # CLI entry point
|   |-- config.py                # Settings from env vars
|   |-- scheduler.py             # APScheduler setup
|   |
|   |-- collectors/              # One module per data source
|   |   |-- __init__.py
|   |   |-- base.py              # Abstract collector interface
|   |   |-- google_trends.py     # trendspyg / pytrends
|   |   |-- reddit.py            # PRAW
|   |   |-- hackernews.py        # haxor
|   |   |-- github_trending.py   # requests + BS4
|   |   +-- youtube.py           # scrapetube
|   |
|   |-- scoring/                 # Validation & scoring engine
|   |   |-- __init__.py
|   |   |-- engagement.py
|   |   |-- search_trend.py
|   |   |-- content_gap.py
|   |   |-- market_traction.py
|   |   +-- composite.py         # Weighted score aggregator
|   |
|   |-- storage/                 # Database abstraction
|   |   |-- __init__.py
|   |   |-- models.py            # SQLAlchemy / raw SQL models
|   |   +-- repository.py        # CRUD operations
|   |
|   +-- reports/                 # Report generation
|       |-- __init__.py
|       |-- generator.py
|       +-- templates/
|           +-- daily_report.md.j2
|
|-- tests/
|   |-- test_collectors/
|   |-- test_scoring/
|   +-- test_reports/
|
|-- data/                        # SQLite DB lives here (git-ignored)
+-- reports/                     # Generated reports (git-ignored)
```

---

## 11. MVP Milestones

| Phase | Scope | Deliverable |
|-------|-------|-------------|
| **P0 — Skeleton** | Project scaffolding, Docker Compose, config, DB schema | Runnable container that boots and creates tables |
| **P1 — Collectors** | Implement all 5 collectors with normalized output | Raw data flowing into `raw_items` table |
| **P2 — Scoring** | Build 4-dimension scoring engine + composite score | `niche_scores` table populated each cycle |
| **P3 — Reports** | Markdown + JSON report generator, Jinja2 templates | Daily report files in `reports/` directory |
| **P4 — Scheduler** | APScheduler integration, configurable intervals | Fully autonomous continuous operation |
| **P5 — Notifications** | Optional Slack / Discord webhook push for high-priority niches | Alert on score >= 80 |

---

## 12. Future Enhancements (Post-MVP)

- **LLM-powered summarization** — Use a local model (Ollama + Llama) to generate one-paragraph niche descriptions.
- **Web dashboard** — Streamlit or Gradio UI for browsing scored niches and trend charts.
- **GitHub Actions mode** — Scheduled workflow that runs collection + scoring and commits reports to a GitHub Pages site.
- **Additional sources** — Stack Overflow, Product Hunt (GraphQL API), X/Twitter, IndieHackers.
- **SEO depth** — Integrate free SEO data sources (Google Search Console API, Bing Webmaster) for keyword difficulty estimates.
- **De-duplication & clustering** — NLP-based merging of related niche candidates across sources.
