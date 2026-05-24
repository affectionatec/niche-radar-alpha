# Niche Radar

Self-hosted trend-intelligence pipeline that monitors 12 public platforms, discovers emerging product opportunities via an 8-agent LLM pipeline, and serves scored niche candidates through a web dashboard.

> **Who is this for?** Solo founders, indie hackers, and micro-SaaS operators who want automated, cross-platform opportunity discovery instead of manually scanning Reddit, HN, Twitter, and YouTube every day.

---

## Table of Contents

- [How It Works](#how-it-works)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Dashboard](#dashboard)
- [Data Sources](#data-sources)
- [LLM Providers](#llm-providers)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [CLI Reference](#cli-reference)
- [Development](#development)
- [Documentation](#documentation)

---

## How It Works

```
12 Data Sources → Collect → 8-Agent LLM Pipeline → Scored Niches → Dashboard
```

1. **Collect** — 12 collectors scrape public platforms on a 4-hour cycle (Reddit, HN, GitHub Trending, YouTube, Google Trends, Product Hunt, Twitter/X, Stack Overflow, G2 Reviews, Indie Hackers, App Store, Play Store)
2. **Analyse** — An 8-agent LLM pipeline runs every 6 hours:
   - **A1** Signal Filter — drops noise, keeps genuine pain signals
   - **A2** Pain Extractor — extracts user frustrations with verbatim quotes
   - **Clustering** — groups related items via Jaccard similarity + LLM refinement
   - **A3** Market Researcher — analyses market size and competition
   - **A4** Opportunity Scorer — scores across 7 dimensions (0–100)
   - **A5** Feasibility Analyst — estimates build complexity and stack
   - **A6** Go/No-Go Judge — issues GO, NO-GO, or PIVOT verdict
   - **A7** PRD Writer — generates a product requirements document
   - **A8** Brief Creator — produces a concise founder briefing
3. **Serve** — FastAPI backend + Next.js dashboard display scored opportunities, shortlists, pipeline status, and generated reports

---

## Quick Start

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/)
- An LLM API key (DeepSeek, OpenAI, Anthropic, Groq, xAI, Google Gemini, or a local Ollama instance)

### 1. Clone and configure

```bash
git clone https://github.com/affectionatec/niche-radar-alpha.git
cd niche-radar-alpha
cp .env.example .env
```

Edit `.env` — at minimum, set your LLM API key:

```env
LLM_PROVIDER=openai_compat
LLM_API_KEY=sk-your-key-here
LLM_BASE_URL=https://api.deepseek.com   # or leave empty for OpenAI
LLM_MODEL=deepseek-v4-flash
```

### 2. Start with Docker Compose

```bash
docker compose up -d --build
```

This starts two services:

| Service | URL | Description |
|---------|-----|-------------|
| `radar` | [localhost:8000](http://localhost:8000) | FastAPI backend + background scheduler |
| `frontend` | [localhost:3000](http://localhost:3000) | Next.js dashboard |

Data is persisted in `./data/` (SQLite) and `./reports/` (generated reports) via Docker volumes.

### 3. Open the dashboard

Visit **[http://localhost:3000](http://localhost:3000)**. If no LLM key is configured, you'll be redirected to Settings to enter one.

### Optional: PostgreSQL

```bash
docker compose --profile postgres up -d --build
```

Then update `.env`:

```env
DATABASE_URL=postgresql://radar:changeme@db:5432/niche_radar
```

---

## Configuration

All settings can be configured via `.env` or the web dashboard's **Settings** page.

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `openai_compat` | `openai_compat` or `anthropic` |
| `LLM_API_KEY` | — | Your LLM provider API key |
| `LLM_BASE_URL` | — | API endpoint (empty = OpenAI default) |
| `LLM_MODEL` | `deepseek-v4-flash` | Model name |
| `DATABASE_URL` | `sqlite:///data/niche_radar.db` | SQLite or PostgreSQL connection string |
| `COLLECTION_INTERVAL_HOURS` | `4` | Hours between collection cycles |
| `ANALYSIS_INTERVAL_HOURS` | `6` | Hours between analysis runs |
| `REDDIT_CLIENT_ID` | — | Reddit API credentials ([get free](https://www.reddit.com/prefs/apps)) |
| `REDDIT_CLIENT_SECRET` | — | Reddit API secret |

See [`.env.example`](.env.example) for the full list including data retention, logging, and notification settings.

---

## Dashboard

The web dashboard provides:

- **Home** — System health for all 12 sources, data freshness indicators, collection stats
- **Niches** — Sortable table of scored niche candidates with LLM score, verdict, momentum, and pain points
- **Niche Detail** — Deep dive with full scoring breakdown, raw items, web validation, and generated PRD
- **Shortlist** — User-curated starred opportunities
- **Pipeline** — Visual workflow with stage-by-stage status (GitHub Actions-style), agent activity feed, and run history
- **Reports** — Browse and view generated Markdown analysis reports
- **Settings** — Configure LLM provider (8 providers with live model refresh) and data source credentials

---

## Data Sources

| Source | Method | Credentials |
|--------|--------|-------------|
| Reddit | PRAW (official API) | Client ID + Secret ([free](https://www.reddit.com/prefs/apps)) |
| Hacker News | Firebase API + Algolia | None |
| GitHub Trending | HTML scraping | None (optional PAT for rate limits) |
| YouTube | scrapetube | None |
| Google Trends | trendspyg | None |
| Product Hunt | HTML scraping | None |
| Twitter / X | GraphQL API | Cookie auth (configured in Settings) |
| Stack Overflow | Official API | None |
| G2 Reviews | HTML scraping | None |
| Indie Hackers | HTML scraping | None |
| App Store | HTML scraping | None |
| Play Store | HTML scraping | None |

Most sources work without any credentials. Reddit requires a free API app. All source credentials can be configured from the **Settings → Data Sources** page in the dashboard.

---

## LLM Providers

Niche Radar supports 8 LLM providers. Select and configure from the dashboard Settings page. The model list can be live-refreshed from the provider's API.

| Provider | Protocol | Models (examples) |
|----------|----------|-------------------|
| DeepSeek | OpenAI-compatible | `deepseek-v4-flash`, `deepseek-v4-pro` |
| OpenAI | OpenAI-compatible | `gpt-5.2`, `gpt-4.1-mini`, `o3` |
| Anthropic | Anthropic SDK | `claude-sonnet-4-6`, `claude-opus-4-7` |
| Groq | OpenAI-compatible | `llama-3.3-70b-versatile`, `qwen3-32b` |
| Google Gemini | OpenAI-compatible | `gemini-3.1-pro`, `gemini-2.5-flash` |
| xAI (Grok) | OpenAI-compatible | `grok-4.3` |
| Ollama | OpenAI-compatible | Any local model (`llama3.3`, `phi4`, etc.) |
| Custom | OpenAI-compatible | Any endpoint + model name |

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Docker Compose                     │
│                                                      │
│  ┌──────────────────┐    ┌────────────────────────┐  │
│  │  frontend :3000   │───▶│    radar :8000          │  │
│  │  Next.js 14       │    │    FastAPI + Uvicorn    │  │
│  │  React 18, SWR    │    │    APScheduler          │  │
│  └──────────────────┘    │    8-Agent Pipeline      │  │
│                           │    12 Collectors         │  │
│                           └──────────┬───────────┘  │
│                                      │               │
│                           ┌──────────▼───────────┐  │
│                           │  ./data/ (SQLite)     │  │
│                           │  ./reports/ (Markdown) │  │
│                           └──────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

- **Backend** (`radar`): Python 3.11, FastAPI, handles API, scheduling, collection, and LLM pipeline
- **Frontend** (`frontend`): Next.js 14, proxies `/api/*` to the backend
- **Database**: SQLite (default, zero-config) or PostgreSQL (opt-in via `--profile postgres`)
- **Scheduler**: Embedded APScheduler — collection every 4h, analysis every 6h, cleanup daily

For detailed architecture diagrams and module descriptions, see [ARCHITECTURE.md](ARCHITECTURE.md).

---

## Project Structure

```
niche-radar-alpha/
├── docker-compose.yml          # Primary deployment method
├── Dockerfile                  # Backend container
├── .env.example                # Environment variable template
│
├── niche_radar/                # Python backend
│   ├── __main__.py             # CLI entry point
│   ├── config.py               # Settings (env + database)
│   ├── collectors/             # 12 data source collectors
│   ├── agents/                 # 8-agent LLM pipeline
│   │   ├── pipeline.py         # Pipeline orchestration
│   │   ├── orchestrator.py     # Per-cluster agent runner
│   │   ├── models.py           # A1–A8 Pydantic I/O models
│   │   ├── prompts.py          # Agent system prompts
│   │   └── clustering.py       # Jaccard + LLM clustering
│   ├── llm/                    # LLM client abstraction
│   ├── storage/                # SQLite/PostgreSQL repository
│   ├── api/                    # FastAPI server + job manager
│   │   ├── server.py           # REST endpoints
│   │   └── jobs.py             # SQLite-backed job persistence
│   └── reports/                # Markdown report generator
│
├── frontend/                   # Next.js dashboard
│   ├── Dockerfile              # Frontend container
│   └── src/
│       ├── app/                # Page routes (dashboard, niches, pipeline, settings, ...)
│       ├── components/         # Shared UI components
│       └── lib/                # API client, types, design tokens
│
├── tests/                      # pytest test suite
├── data/                       # SQLite database (git-ignored, Docker volume)
└── reports/                    # Generated reports (git-ignored, Docker volume)
```

---

## CLI Reference

The backend supports CLI commands via `python -m niche_radar <command>`. Inside Docker, these run automatically via the scheduler, but you can also run them manually:

```bash
# Inside the running container
docker exec niche-radar python -m niche_radar <command>
```

| Command | Description |
|---------|-------------|
| `serve` | Start API server + background scheduler (default) |
| `collect [--source NAME]` | Run collection from all or a specific source |
| `analyze [--test]` | Run the 8-agent LLM analysis pipeline |
| `report` | Generate a Markdown analysis report |
| `cleanup` | Run data retention cleanup |
| `status` | Show system health summary |

---

## Development

### Local development (without Docker)

```bash
# Backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m niche_radar serve

# Frontend (separate terminal)
cd frontend && npm install && npm run dev
```

### Running tests

```bash
pip install -e ".[dev]"
pytest -v
pytest --cov=niche_radar --cov-report=term
```

### Rebuilding after changes

```bash
docker compose up -d --build
```

Pipeline run history and opportunity data persist across rebuilds (stored in `./data/` volume).

---

## Documentation

| Document | Description |
|----------|-------------|
| [CONTEXT.md](CONTEXT.md) | Domain glossary — canonical terms used in the codebase |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System design, module map, and Mermaid diagrams |
| [PRODUCT.md](PRODUCT.md) | Problem statement, users, features, and non-goals |
| [DESIGN.md](DESIGN.md) | UI/UX design system (xAI-inspired dark theme) |
| [spec.md](spec.md) | Full MVP specification |

---

## Status

**Alpha** — Core pipeline functional. 12 collectors implemented, 8-agent analysis pipeline operational, frontend dashboard with full pipeline visualization. Not yet a stable release.
