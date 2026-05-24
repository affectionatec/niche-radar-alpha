# Niche Radar Alpha — MVP Specification

> **Codename:** NicheRadar
> **Version:** 0.2.0-alpha
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
| 5 | Resilient operation | Gracefully degrade when individual sources fail; never lose scored data |

---

## 2. Target Data Sources (Top 5)

The MVP focuses on five high-value, publicly accessible platforms that collectively cover search behavior, developer communities, tech products, and mainstream social trends.

Each collector MUST:
- Return data in the normalized `CollectorResult` format (see section 3.1).
- Handle its own rate limiting internally.
- Raise `CollectorUnavailableError` when the source is unreachable after retries, so the scheduler can continue with remaining sources.

### 2.1 Google Trends

| Attribute | Value |
|-----------|-------|
| **Why** | The authoritative signal for search-interest trajectory over time. Reveals whether a topic is rising, stable, or declining. |
| **Open-source library** | [`trendspyg`](https://pypi.org/project/trendspyg/) (MIT) — free, no API key, 188K+ config combinations. Fallback: [`pytrends`](https://github.com/GeneralMills/pytrends) (Apache-2.0). |
| **Data to collect** | Interest-over-time (past 12 months), related queries (rising), related topics (rising), regional breakdown. |
| **Frequency** | Every 6 hours for tracked keywords; daily full sweep for new keyword discovery. |
| **Rate limits** | `trendspyg` handles rate limiting internally. For `pytrends` fallback: max 5 requests/minute with 12-second delays between batches. |
| **Failure mode** | Google may block via CAPTCHA. On 3 consecutive failures, mark source as `degraded` and skip until next cycle. Log warning. |

### 2.2 Reddit

| Attribute | Value |
|-----------|-------|
| **Why** | The richest source of unfiltered user pain-points, feature requests, and "is there a tool that..." signals in the English-speaking internet. |
| **Open-source library** | [`PRAW`](https://praw.readthedocs.io/) (BSD-2) — official Python Reddit API Wrapper (requires free Reddit API credentials). |
| **Target subreddits (initial)** | `r/SaaS`, `r/selfhosted`, `r/webdev`, `r/smallbusiness`, `r/Entrepreneur`, `r/sideproject`, `r/macapps`, `r/devops`, `r/dataengineering`, `r/nocode` |
| **Pain-point trigger phrases** | `"is there a tool"`, `"I wish there was"`, `"alternative to"`, `"how do you automate"`, `"pricing is crazy"`, `"looking for"`, `"recommend a"`, `"frustrated with"` |
| **Data to collect** | Top 50 hot posts per subreddit (last 24 h), top-level comments (score >= 5), post score, comment count, post flair. |
| **Frequency** | Every 4 hours. |
| **Rate limits** | Reddit API: 100 requests/minute per OAuth token. PRAW handles this automatically via built-in rate limiter. |
| **Failure mode** | On `403 Forbidden` (revoked credentials): halt and log error. On `503 Service Unavailable`: retry 3x with exponential backoff, then skip. |

### 2.3 Hacker News

| Attribute | Value |
|-----------|-------|
| **Why** | Early-signal hub for developer tools, AI products, and technical infrastructure trends. Show HN and Ask HN threads surface real launches and real needs. |
| **Open-source library** | [`haxor`](https://pypi.org/project/haxor/) (MIT) — Python wrapper for the [official HN Firebase API](https://github.com/HackerNews/API) (free, no API key, no rate limit). |
| **Data to collect** | Top stories (50), Best stories (50), Ask HN (30), Show HN (30), including title, URL, score, comment count, full comment trees for top items. |
| **Frequency** | Every 2 hours. |
| **Rate limits** | No official rate limit. Self-impose 30 requests/second ceiling to be a good citizen. |
| **Failure mode** | Firebase API is highly reliable. On timeout (>10s): retry 2x. On persistent failure: skip and log. |

### 2.4 GitHub Trending

| Attribute | Value |
|-----------|-------|
| **Why** | Reveals which open-source projects are gaining sudden traction — a strong proxy for developer tool demand and emerging tech categories. |
| **Open-source approach** | Scrape [github.com/trending](https://github.com/trending) via `requests` + `BeautifulSoup` (no official API for trending). Alternatively use the GitHub REST API `search/repositories` sorted by stars with `created:>YYYY-MM-DD`. |
| **Data to collect** | Repo name, description, language, stars today, total stars, forks, topics/tags. |
| **Frequency** | Every 6 hours (daily, weekly, monthly views). |
| **Rate limits** | Unauthenticated: 60 requests/hour. With PAT: 5,000 requests/hour. Scraping: 2-second delay between page fetches. |
| **Failure mode** | On `403 Rate Limit Exceeded`: respect `X-RateLimit-Reset` header, retry after reset. On scraping `429`: back off 60 seconds, retry once. |

### 2.5 YouTube (Trending and Search)

| Attribute | Value |
|-----------|-------|
| **Why** | Mainstream consumer trend signal with massive reach. "How to" and product-review videos reveal real purchasing intent. |
| **Open-source library** | [`scrapetube`](https://pypi.org/project/scrapetube/) (MIT) — scrapes YouTube without API key. Backup: YouTube Data API v3 (free tier: 10,000 units/day). |
| **Data to collect** | Trending videos by category, search results for seed keywords (title, view count, like count, publish date, channel). |
| **Frequency** | Every 8 hours for trending; on-demand for keyword searches. |
| **Rate limits** | `scrapetube`: self-impose 1-second delay between requests. YouTube API v3: 10,000 quota units/day (search = 100 units each, so ~100 searches/day max). |
| **Failure mode** | `scrapetube` may break if YouTube changes HTML structure. On parse error: log warning, fall back to YouTube API v3 if configured. On API quota exhaustion: skip until next day. |

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
| **NLP Pipeline** | Extract keywords, cluster related terms, produce niche candidates | `keybert`, `scikit-learn` |
| **Validation Engine** | Score each discovered niche across multiple dimensions | `trendspyg` (trend slope), custom scorers |
| **Data Store** | Persist raw + scored data | `SQLite` (local / default), `PostgreSQL` (Docker Compose production) |
| **Report Generator** | Produce human-readable and machine-readable output | `Jinja2` (Markdown templates), `json` stdlib |

#### CollectorResult Contract

Every collector returns a `CollectorResult` dataclass:

```python
@dataclass
class CollectorResult:
    source: str                  # e.g. 'reddit', 'hn', 'github', 'google_trends', 'youtube'
    items: list[RawItemDict]     # List of normalized item dicts (see raw_items schema)
    run_id: str                  # UUID for this collection run
    status: str                  # 'completed' | 'partial' | 'failed'
    items_collected: int
    error_message: str | None
    duration_seconds: float
```

Each `RawItemDict` maps directly to a row in the `raw_items` table (section 5.1). Source-specific fields go into the `metadata` JSON column.

### 3.2 NLP & Keyword Extraction Pipeline

This is the core intelligence that transforms raw ingested data into actionable niche candidates.

**Pipeline steps (executed once per scheduler cycle, after all collectors have completed or timed out):**

```
raw_items --> [1. Text Preprocessing] --> [2. Keyword Extraction] --> [3. Clustering] --> [4. Deduplication] --> niche_candidates
```

#### Step 1: Text Preprocessing

- Concatenate `title` + `body` for each `raw_item`.
- Strip HTML tags, URLs, code blocks, and markdown formatting.
- Normalize unicode, lowercase, remove stopwords.
- Minimum text length: 20 characters. Items shorter than this are skipped.

#### Step 2: Keyword Extraction

Use [`KeyBERT`](https://github.com/MaartenGr/KeyBERT) (MIT) with the `all-MiniLM-L6-v2` sentence-transformer model:

- Extract top 5 keyphrases per item (1-gram to 3-gram).
- Use MMR (Maximal Marginal Relevance) diversity with `diversity=0.5` to avoid near-duplicate phrases.
- Output: list of `(keyphrase, relevance_score)` tuples per item.

**Why KeyBERT over spaCy NER:** KeyBERT captures conceptual phrases ("self-hosted analytics", "AI code review") while spaCy NER is designed for named entities (people, orgs, places). Niche discovery needs concept extraction, not entity recognition.

#### Step 3: Clustering

Group related keyphrases across items using cosine similarity on their sentence embeddings:

- Compute embeddings for all extracted keyphrases using the same `all-MiniLM-L6-v2` model.
- Agglomerative clustering with `distance_threshold=0.35` (empirically tuned).
- Each cluster becomes one `niche_candidate`. The keyphrase closest to the cluster centroid becomes the `keyword`; others become `aliases`.

#### Step 4: Deduplication & Merging

- Before inserting a new `niche_candidate`, check existing candidates:
  - Compute cosine similarity between the new candidate's embedding and all existing candidates.
  - If similarity > 0.85 with an existing candidate: merge (increment `occurrence_count`, update `last_seen`, append new aliases).
  - Otherwise: insert as new candidate.
- Minimum occurrence threshold: a candidate must appear in >= 2 distinct `raw_items` from >= 1 source before it enters the scoring pipeline. Single-mention items are stored but not scored.

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

**Normalization:** Collect all scores from the current day's `raw_items` for the relevant sources. Compute the percentile rank of the candidate's associated items. The 95th percentile maps to score 100; the 50th percentile maps to score 50.

#### Dimension 2 — Search Interest Trend (weight: 0.30)

Measures whether real people are actively searching for this topic.

| Metric | Source | Scoring Logic |
|--------|--------|---------------|
| 12-month interest slope | Google Trends (`trendspyg`) | Linear regression slope of weekly interest values. Positive slope = score up; negative = score down. |
| Breakout queries | Google Trends (related queries, "rising") | Breakout (>5000%) = 100 pts; >200% = 70 pts |
| Search volume proxy | Google Trends absolute scale | Normalize peak interest (0-100 from Trends) directly |

**Normalization:** The slope is computed via `numpy.polyfit(x, y, 1)[0]` on the 52-week interest series. Slopes are clamped to [-5, +5] and linearly mapped to [0, 100] where slope=0 maps to 50.

#### Dimension 3 — Content & Product Gap (weight: 0.25)

Measures whether existing solutions are inadequate.

| Metric | Source | Scoring Logic |
|--------|--------|---------------|
| Pain-point phrase hits | Reddit, HN comments | Count of trigger-phrase matches (see section 2.2) in top comments |
| "Alternative to" mentions | Reddit | Count of posts/comments mentioning alternatives to established tools |
| Show HN / sideproject signals | HN, Reddit (`r/sideproject`) | New launches in this space = validates demand but check saturation |

**Normalization:** Raw phrase-hit counts are log-scaled (`min(100, 20 * log2(count + 1))`) to avoid outlier dominance.

#### Dimension 4 — Market Traction (weight: 0.20)

Measures whether there is commercial momentum.

| Metric | Source | Scoring Logic |
|--------|--------|---------------|
| YouTube view counts | YouTube search for seed keywords | Average views on top 10 recent videos (>10K avg = high signal) |
| GitHub repo growth | GitHub Trending | Total stars + fork ratio as adoption proxy |
| Trending rank persistence | All sources | Number of consecutive collection cycles a topic appears in top results |

**Normalization:** YouTube views use log-scale (`min(100, 15 * log10(avg_views + 1))`). GitHub stars use percentile rank within that day's trending set.

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

### 4.3 Score Staleness

A niche's composite score is valid for **24 hours**. If no new data arrives for a niche within 48 hours, the composite score decays by 10% per day (e.g., a score of 80 becomes 72 after one day, 64.8 after two). After 7 consecutive days without new data, the niche is moved to `archived` status and excluded from reports.

---

## 5. Data Model

### 5.1 Core Tables

```sql
-- Track each collection run for observability
CREATE TABLE collection_runs (
    id              TEXT PRIMARY KEY,
    source          TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'running',  -- 'running' | 'completed' | 'failed' | 'partial'
    items_collected INTEGER DEFAULT 0,
    error_message   TEXT,
    started_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at    TIMESTAMP
);
CREATE INDEX idx_collection_runs_source ON collection_runs(source);
CREATE INDEX idx_collection_runs_started ON collection_runs(started_at);

-- Raw ingested items from all sources
CREATE TABLE raw_items (
    id              TEXT PRIMARY KEY,       -- UUID
    collection_run  TEXT REFERENCES collection_runs(id),
    source          TEXT NOT NULL,           -- 'reddit' | 'hn' | 'github' | 'google_trends' | 'youtube'
    source_id       TEXT,                    -- Platform-native ID (for dedup across runs)
    title           TEXT,
    body            TEXT,
    url             TEXT,
    score           INTEGER,                -- Upvotes / stars / views
    comment_count   INTEGER,
    metadata        JSON,                   -- Source-specific fields
    collected_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_raw_items_source ON raw_items(source);
CREATE INDEX idx_raw_items_source_id ON raw_items(source_id);
CREATE INDEX idx_raw_items_collected ON raw_items(collected_at);
CREATE UNIQUE INDEX idx_raw_items_dedup ON raw_items(source, source_id);

-- Extracted niche candidates after NLP / grouping
CREATE TABLE niche_candidates (
    id              TEXT PRIMARY KEY,
    keyword         TEXT NOT NULL,           -- Primary keyword / phrase
    aliases         JSON,                    -- Related terms
    embedding       BLOB,                   -- Sentence embedding for similarity matching
    status          TEXT DEFAULT 'active',   -- 'active' | 'archived'
    first_seen      TIMESTAMP,
    last_seen       TIMESTAMP,
    occurrence_count INTEGER DEFAULT 1
);
CREATE INDEX idx_niche_candidates_keyword ON niche_candidates(keyword);
CREATE INDEX idx_niche_candidates_status ON niche_candidates(status);

-- Link table: which raw_items contributed to which niche_candidate
CREATE TABLE niche_item_links (
    niche_id        TEXT REFERENCES niche_candidates(id),
    raw_item_id     TEXT REFERENCES raw_items(id),
    keyphrase       TEXT,                   -- The extracted keyphrase that linked them
    relevance_score REAL,
    PRIMARY KEY (niche_id, raw_item_id)
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
CREATE INDEX idx_niche_scores_niche ON niche_scores(niche_id);
CREATE INDEX idx_niche_scores_composite ON niche_scores(composite_score);
CREATE INDEX idx_niche_scores_scored ON niche_scores(scored_at);

-- Historical trend snapshots for each niche
CREATE TABLE trend_snapshots (
    id              TEXT PRIMARY KEY,
    niche_id        TEXT REFERENCES niche_candidates(id),
    source          TEXT,                   -- 'google_trends' | 'reddit' | etc.
    data            JSON,                   -- Time-series or structured payload
    snapshot_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_trend_snapshots_niche ON trend_snapshots(niche_id);
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
python -m niche_radar collect            # One-shot: collect from all sources
python -m niche_radar collect --source reddit  # Collect from Reddit only
python -m niche_radar score              # Run scoring on existing data
python -m niche_radar report             # Generate report from latest scores
python -m niche_radar serve              # Start scheduler (continuous mode)
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
    command: ["python", "-m", "niche_radar", "serve"]

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
CMD ["serve"]
```

### 6.4 Error Handling & Resilience

| Scenario | Behavior |
|----------|----------|
| Single collector fails | Log error, record `failed` status in `collection_runs`, continue with remaining collectors. The system operates in degraded mode. |
| All collectors fail | Log critical error, send notification (if configured), retry full cycle in 15 minutes. After 3 consecutive total failures, pause scheduler and alert. |
| Database write fails | Retry 3x with 1-second backoff. On persistent failure, write raw data to a `data/fallback/` JSON file for manual recovery. |
| Malformed API response | Validate response schema before processing. Log warning with full response body (truncated to 1KB) and skip the item. |
| Network timeout | Per-request timeout: 30 seconds. Per-collector timeout: 5 minutes. Exceeded = `CollectorUnavailableError`. |

**Retry strategy:** Use [`tenacity`](https://github.com/jd/tenacity) (Apache-2.0) with exponential backoff:
```python
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=30))
```

### 6.5 Rate Limiting

| Source | Limit | Implementation |
|--------|-------|----------------|
| Reddit (PRAW) | 100 req/min (automatic) | PRAW handles internally |
| Google Trends | 5 req/min (self-imposed) | `time.sleep(12)` between batches |
| Hacker News | 30 req/sec (self-imposed) | Token bucket via `aiolimiter` or simple sleep |
| GitHub (unauthenticated) | 60 req/hr | Check `X-RateLimit-Remaining` header; sleep until reset when < 5 |
| GitHub (with PAT) | 5,000 req/hr | Same header check |
| YouTube (scrapetube) | 1 req/sec (self-imposed) | `time.sleep(1)` between requests |
| YouTube (API v3) | 10,000 units/day | Track daily quota usage in memory; stop when 90% consumed |

### 6.6 Data Retention

| Data Type | Retention | Cleanup Method |
|-----------|-----------|----------------|
| `raw_items` | 90 days | Daily cleanup job deletes rows where `collected_at < now - 90 days` |
| `niche_candidates` (active) | Indefinite | Never auto-deleted |
| `niche_candidates` (archived) | 180 days after archival | Deleted after 180 days in `archived` status |
| `niche_scores` | 365 days | Keep the most recent 365 days of scores per niche |
| `trend_snapshots` | 365 days | Same as niche_scores |
| `collection_runs` | 30 days | Log-style data, purge older runs |
| Generated reports | Indefinite | User manages manually or via disk quota |

Cleanup runs as a scheduled job once per day at 03:00 UTC (configurable via `CLEANUP_HOUR_UTC`).

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
CLEANUP_HOUR_UTC=3              # Hour (0-23) to run daily data cleanup

# -- Retry --
MAX_RETRIES=3                   # Max retries per collector on failure
RETRY_BACKOFF_BASE=2            # Base seconds for exponential backoff

# -- Data Retention (days) --
RETENTION_RAW_ITEMS=90
RETENTION_ARCHIVED_NICHES=180
RETENTION_SCORES=365
RETENTION_COLLECTION_RUNS=30

# -- Report --
REPORT_OUTPUT_DIR=./reports
REPORT_FORMAT=both              # 'markdown' | 'json' | 'both'

# -- Logging --
LOG_LEVEL=INFO                  # DEBUG | INFO | WARNING | ERROR
LOG_FORMAT=json                 # 'json' (structured) | 'text' (human-readable)

# -- Notifications (optional) --
SLACK_WEBHOOK_URL=
DISCORD_WEBHOOK_URL=

# -- NLP --
KEYBERT_MODEL=all-MiniLM-L6-v2  # Sentence-transformer model for KeyBERT
MIN_OCCURRENCE_THRESHOLD=2       # Min appearances before a niche enters scoring
CLUSTER_DISTANCE_THRESHOLD=0.35  # Agglomerative clustering distance threshold
```

---

## 8. CLI Interface

The application is invoked via `python -m niche_radar <command> [options]`.

### Commands

| Command | Description | Example |
|---------|-------------|---------|
| `collect` | Run a one-shot collection from all sources | `python -m niche_radar collect` |
| `collect --source <name>` | Collect from a specific source only | `python -m niche_radar collect --source reddit` |
| `extract` | Run the NLP pipeline on un-processed raw items | `python -m niche_radar extract` |
| `score` | Score all active niche candidates | `python -m niche_radar score` |
| `report` | Generate a report from the latest scores | `python -m niche_radar report` |
| `report --format json` | Generate report in a specific format | `python -m niche_radar report --format json` |
| `serve` | Start the scheduler for continuous operation | `python -m niche_radar serve` |
| `cleanup` | Manually trigger data retention cleanup | `python -m niche_radar cleanup` |
| `status` | Show system status (last run times, DB stats, source health) | `python -m niche_radar status` |

### Global Options

| Option | Description | Default |
|--------|-------------|---------|
| `--config <path>` | Path to `.env` file | `.env` |
| `--db <url>` | Override `DATABASE_URL` | From env |
| `--log-level <level>` | Override log level | From env / `INFO` |
| `--dry-run` | Run without writing to DB or files | `false` |

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Partial success (some collectors failed, others succeeded) |
| 2 | Complete failure (all collectors failed or critical error) |
| 3 | Configuration error (missing required env vars) |

---

## 9. Output: Daily Niche Report

Each scoring cycle generates a report. Example structure:

```markdown
# Niche Radar — Daily Report
**Generated:** 2026-05-11 06:00 UTC | **Cycle:** #142
**Sources active:** 5/5 | **Niches scored:** 47 | **New this cycle:** 3

## High Priority (Score >= 80)

### 1. "AI-powered browser testing" — Score: 87
| Dimension        | Score | Key Signal |
|------------------|-------|------------|
| Engagement       | 82    | 3 Reddit threads (avg 240 upvotes), 2 HN front-page items |
| Search Trend     | 91    | Google Trends: +45% slope, "breakout" related query |
| Content Gap      | 88    | 12 "looking for" / "alternative to Selenium" mentions |
| Market Traction  | 79    | 2 GitHub repos trending (1.2K stars/week), YouTube avg 28K views |

**Related keywords:** browser automation AI, AI QA testing, codeless testing tool
**First seen:** 2026-05-08 | **Trend:** Rising (3 consecutive cycles)
**Sources:** [Reddit](...), [HN](...), [GitHub](...)

---

## Watchlist (Score 65-79)
| # | Niche | Score | Trend | Top Signal |
|---|-------|-------|-------|------------|
| 1 | Self-hosted analytics | 74 | Rising | Reddit engagement + rising Google Trends |
| 2 | ... | ... | ... | ... |

## Archived (Score 40-64)
_15 niches archived this cycle. See reports/2026-05-11-archive.json._

## System Health
| Source | Status | Last Run | Items |
|--------|--------|----------|-------|
| Reddit | OK | 05:42 UTC | 487 |
| Google Trends | OK | 05:38 UTC | 52 |
| Hacker News | OK | 05:45 UTC | 160 |
| GitHub Trending | OK | 05:40 UTC | 75 |
| YouTube | OK | 05:35 UTC | 120 |
```

A machine-readable `report.json` is also generated for downstream automation.

---

## 10. Technology Stack Summary

| Layer | Technology | License | API Key Required? |
|-------|-----------|---------|-------------------|
| Runtime | Python 3.11+ | PSF | — |
| Google Trends | `trendspyg` (primary) / `pytrends` (fallback) | MIT / Apache-2.0 | No |
| Reddit | `PRAW` | BSD-2 | Yes (free Reddit dev app) |
| Hacker News | `haxor` + official Firebase API | MIT | No |
| GitHub Trending | `requests` + `BeautifulSoup4` / GitHub REST API | Apache-2.0 | No (optional PAT) |
| YouTube | `scrapetube` (primary) / YouTube Data API v3 (fallback) | MIT | No / Yes (free tier) |
| NLP / Keywords | `keybert` + `sentence-transformers` | MIT | No |
| Clustering | `scikit-learn` (AgglomerativeClustering) | BSD-3 | No |
| Scheduling | `APScheduler` | MIT | — |
| Retry / Resilience | `tenacity` | Apache-2.0 | — |
| Database | SQLite (default) / PostgreSQL (optional) | Public domain / PostgreSQL License | — |
| Logging | `structlog` | MIT / Apache-2.0 | — |
| Report templating | `Jinja2` | BSD-3 | — |
| Containerization | Docker + Docker Compose | Apache-2.0 | — |

---

## 11. Project Structure

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
|   |-- __main__.py              # CLI entry point (argparse)
|   |-- config.py                # Settings from env vars (pydantic-settings)
|   |-- scheduler.py             # APScheduler setup
|   |
|   |-- collectors/              # One module per data source
|   |   |-- __init__.py
|   |   |-- base.py              # Abstract BaseCollector + CollectorResult dataclass
|   |   |-- google_trends.py     # trendspyg / pytrends
|   |   |-- reddit.py            # PRAW
|   |   |-- hackernews.py        # haxor
|   |   |-- github_trending.py   # requests + BS4
|   |   +-- youtube.py           # scrapetube
|   |
|   |-- nlp/                     # NLP pipeline
|   |   |-- __init__.py
|   |   |-- preprocessor.py      # Text cleaning, normalization
|   |   |-- extractor.py         # KeyBERT keyword extraction
|   |   +-- clusterer.py         # Agglomerative clustering + dedup
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
|   |   |-- repository.py        # CRUD operations
|   |   +-- cleanup.py           # Data retention enforcement
|   |
|   +-- reports/                 # Report generation
|       |-- __init__.py
|       |-- generator.py
|       +-- templates/
|           +-- daily_report.md.j2
|
|-- tests/
|   |-- conftest.py              # Shared fixtures (mock DB, sample data)
|   |-- test_collectors/
|   |   |-- test_reddit.py
|   |   |-- test_hackernews.py
|   |   |-- test_google_trends.py
|   |   |-- test_github_trending.py
|   |   +-- test_youtube.py
|   |-- test_nlp/
|   |   |-- test_preprocessor.py
|   |   |-- test_extractor.py
|   |   +-- test_clusterer.py
|   |-- test_scoring/
|   |   |-- test_engagement.py
|   |   |-- test_search_trend.py
|   |   |-- test_content_gap.py
|   |   |-- test_market_traction.py
|   |   +-- test_composite.py
|   |-- test_reports/
|   |   +-- test_generator.py
|   +-- test_integration/
|       +-- test_full_pipeline.py # End-to-end with fixture data
|
|-- data/                        # SQLite DB lives here (git-ignored)
+-- reports/                     # Generated reports (git-ignored)
```

---

## 12. Testing Strategy

### 12.1 Unit Tests

Each collector, NLP module, and scorer has dedicated unit tests using `pytest`.

| Module | Testing Approach |
|--------|-----------------|
| **Collectors** | Mock HTTP responses (via `responses` or `pytest-httpx`). Each test provides a fixture JSON matching the real API shape. Assert that the collector returns the correct `CollectorResult` and handles error responses gracefully. |
| **NLP Pipeline** | Use a small set of fixture texts (~20 items). Assert that keyphrases are extracted, clusters are formed, and dedup logic merges correctly. |
| **Scorers** | Provide deterministic input data. Assert exact score values. Test edge cases: empty data, single item, all zeros, max values. |
| **Report Generator** | Provide scored niche data. Assert the Markdown output contains expected sections and the JSON output parses cleanly. |

### 12.2 Integration Tests

One end-to-end test (`test_full_pipeline.py`) that:
1. Loads fixture raw data into an in-memory SQLite database.
2. Runs the NLP extraction pipeline.
3. Runs the scoring engine.
4. Generates a report.
5. Asserts: at least 1 niche candidate scored, report file created, no errors logged.

### 12.3 Test Fixtures

Store representative API responses in `tests/fixtures/`:
```
tests/fixtures/
|-- reddit_hot_posts.json
|-- hn_top_stories.json
|-- google_trends_interest.json
|-- github_trending_page.html
+-- youtube_search_results.json
```

### 12.4 Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=niche_radar --cov-report=term-missing

# Specific module
pytest tests/test_collectors/test_reddit.py -v
```

**Coverage target:** >= 80% line coverage on non-trivial modules (collectors, NLP, scoring). Config and CLI modules are tested via integration test.

---

## 13. Logging & Observability

### 13.1 Structured Logging

Use [`structlog`](https://github.com/hynek/structlog) (MIT) for structured JSON logging.

```python
import structlog
logger = structlog.get_logger()

logger.info("collection_complete", source="reddit", items=487, duration_s=12.3)
logger.warning("collector_degraded", source="google_trends", reason="captcha_detected")
logger.error("collector_failed", source="youtube", error="parse_error", details="...")
```

### 13.2 Log Levels

| Level | When |
|-------|------|
| `DEBUG` | Individual API calls, raw response sizes, SQL queries |
| `INFO` | Collection cycle start/end, item counts, score summaries, report generation |
| `WARNING` | Collector degraded, rate limit approached, data anomalies |
| `ERROR` | Collector failed, DB write failed, invalid configuration |

### 13.3 Key Structured Fields

Every log entry includes: `timestamp`, `level`, `event`, `source` (if applicable), `collection_run_id` (if applicable).

### 13.4 Error Alerting

When `SLACK_WEBHOOK_URL` or `DISCORD_WEBHOOK_URL` is configured, the following events trigger a notification:
- Collector failure (after retries exhausted)
- All collectors failed in a cycle
- Score >= 80 detected (high-priority niche alert)
- Scheduler stopped unexpectedly

---

## 14. MVP Milestones

| Phase | Scope | Deliverable | Acceptance Criteria |
|-------|-------|-------------|---------------------|
| **P0 — Skeleton** | Project scaffolding, Docker Compose, config, DB schema, CLI framework | Runnable container that boots and creates tables | `docker compose up` succeeds; `python -m niche_radar status` prints DB stats; all tables exist |
| **P1 — Collectors** | Implement all 5 collectors with normalized output | Raw data flowing into `raw_items` table | Each collector has >=3 unit tests passing with mocked data; `collect` command populates `raw_items`; `collection_runs` table records each run |
| **P2 — NLP Pipeline** | KeyBERT extraction, clustering, dedup | `niche_candidates` populated from raw items | `extract` command produces >=1 candidate from fixture data; dedup merges similar terms; unit tests pass |
| **P3 — Scoring** | Build 4-dimension scoring engine + composite score | `niche_scores` table populated each cycle | `score` command produces scores for all active candidates; scores are 0-100; composite matches formula; unit tests pass for each dimension |
| **P4 — Reports** | Markdown + JSON report generator, Jinja2 templates | Daily report files in `reports/` directory | `report` command creates both `.md` and `.json` files; report contains High Priority, Watchlist, and Archived sections; JSON is valid and parseable |
| **P5 — Scheduler** | APScheduler integration, configurable intervals, data retention cleanup | Fully autonomous continuous operation | `serve` command runs without crashing for 24h; collection, extraction, scoring, and reporting execute on schedule; cleanup removes expired data |
| **P6 — Notifications** | Optional Slack / Discord webhook push for high-priority niches | Alert on score >= 80 | When a niche scores >= 80, webhook is called (verified with mock server); no notification when score < 80 |

---

## 15. Future Enhancements (Post-MVP)

- **LLM-powered summarization** — Use a local model (Ollama + Llama) to generate one-paragraph niche descriptions.
- **Web dashboard** — Streamlit or Gradio UI for browsing scored niches and trend charts.
- **GitHub Actions mode** — Scheduled workflow that runs collection + scoring and commits reports to a GitHub Pages site.
- **Additional sources** — Stack Overflow, Product Hunt (GraphQL API), X/Twitter, IndieHackers.
- **SEO depth** — Integrate free SEO data sources (Google Search Console API, Bing Webmaster) for keyword difficulty estimates.
- **De-duplication & clustering** — Cross-source NLP-based merging of related niche candidates.
- **Historical trend visualization** — Sparkline charts in reports showing score trajectory over time.
- **Configurable scoring weights** — Allow users to adjust dimension weights via config without code changes.
