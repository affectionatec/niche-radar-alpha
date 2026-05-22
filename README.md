# Niche Radar Alpha

Self-hosted trend-intelligence pipeline that monitors 12 public platforms, analyses emerging opportunities via an 8-agent LLM pipeline, and serves scored niche candidates through a web dashboard.

## Quick Start

```bash
# Backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # Add Reddit creds + LLM API key
python -m niche_radar serve   # API on :8000 + scheduler

# Frontend
cd frontend && npm install && npm run dev   # Dashboard on :3000
```

## Docker Compose

```bash
docker compose up -d --build                  # SQLite (default)
docker compose --profile postgres up -d       # With PostgreSQL
```

Images use `docker.1panel.live` mirrors for China-mainland connectivity.

## Stack

- **Language**: Python 3.11+
- **Backend**: FastAPI + Uvicorn
- **Frontend**: Next.js 14, React 18, Tailwind CSS, SWR
- **Database**: SQLite (default) / PostgreSQL (optional)
- **LLM**: OpenAI-compatible, Anthropic, DeepSeek, Groq, Ollama
- **Scheduler**: APScheduler (collection 4h, analysis 6h, cleanup daily)

## Structure

```
niche-radar-alpha/
├── niche_radar/            # Python backend
│   ├── collectors/         # 12 data source collectors (Reddit, HN, GitHub, …)
│   ├── agents/             # 8-agent LLM pipeline (A1–A8)
│   ├── llm/                # LLM client abstraction (OpenAI, Anthropic)
│   ├── storage/            # SQLite repository + cleanup
│   ├── api/                # FastAPI server (23 endpoints)
│   └── reports/            # Markdown report generator
├── frontend/               # Next.js dashboard (xAI dark theme)
│   └── src/
│       ├── app/            # 9 page routes (dashboard, niches, pipeline, …)
│       ├── components/     # Navigation, NicheCard, SourceHealthTable
│       └── lib/            # API client, types
├── tests/                  # pytest suite
├── data/                   # SQLite DB (git-ignored)
└── reports/                # Generated reports (git-ignored)
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `collect [--source NAME]` | Collect from all or one source |
| `analyze [--test]` | Run 8-agent LLM analysis pipeline |
| `report` | Generate Markdown report |
| `serve` | Start API server + background scheduler |
| `cleanup` | Run data retention cleanup |
| `status` | Show system health |

## Data Sources

| Source | Library | API Key? |
|--------|---------|----------|
| Reddit | PRAW | Yes (free) |
| Hacker News | haxor / Algolia | No |
| GitHub Trending | requests + BS4 | No (optional PAT) |
| YouTube | scrapetube | No |
| Google Trends | trendspyg | No |
| Product Hunt | requests + BS4 | No |
| Twitter/X | internal GraphQL | Cookie auth |
| Stack Overflow | official API | No |
| G2 Reviews | requests + BS4 | No |
| Indie Hackers | requests + BS4 | No |
| App Store | requests + BS4 | No |
| Play Store | requests + BS4 | No |

## Testing

```bash
pytest -v                                    # Run all tests
pytest --cov=niche_radar --cov-report=term   # With coverage
```

## Documentation

- [CONTEXT.md](CONTEXT.md) — Domain glossary
- [ARCHITECTURE.md](ARCHITECTURE.md) — System design and module map
- [PRODUCT.md](PRODUCT.md) — Problem, users, features
- [DESIGN.md](DESIGN.md) — UI/UX design system (xAI-inspired)
- [spec.md](spec.md) — Full MVP specification
