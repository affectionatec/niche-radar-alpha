# Niche Radar Alpha

Automated trend-intelligence pipeline that monitors 5 public platforms, extracts emerging niche opportunities via NLP, and produces scored daily reports.

## Data Sources

| Source | Library | API Key? |
|--------|---------|----------|
| Google Trends | trendspyg | No |
| Reddit | PRAW | Yes (free) |
| Hacker News | haxor | No |
| GitHub Trending | requests + BS4 | No (optional PAT) |
| YouTube | scrapetube | No |

## Quick Start (Local)

```bash
python -m venv .venv && .venv\Scripts\activate  # Windows
# source .venv/bin/activate                     # Linux/macOS
pip install -r requirements.txt
cp .env.example .env   # Edit with your Reddit credentials
python -m niche_radar collect --dry-run   # Verify setup
python -m niche_radar collect             # Collect from all sources
python -m niche_radar extract             # Run NLP pipeline
python -m niche_radar score               # Score niche candidates
python -m niche_radar report              # Generate daily report
python -m niche_radar status              # Check system health
```

## Docker Compose

```bash
docker compose up -d --build                  # SQLite (default)
docker compose --profile postgres up -d       # With PostgreSQL
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `collect [--source NAME]` | Collect from all or one source |
| `extract` | Run NLP keyword extraction + clustering |
| `score` | Score active niche candidates |
| `report [--format json\|markdown\|both]` | Generate report |
| `serve` | Start continuous scheduler |
| `cleanup` | Run data retention cleanup |
| `status` | Show system health |

## Testing

```bash
pytest -v                                    # Run all tests
pytest --cov=niche_radar --cov-report=term   # With coverage
```

## Architecture

```
Scheduler → Collectors (5) → NLP Pipeline (KeyBERT + clustering)
  → Scoring Engine (4 dimensions) → Report Generator (MD + JSON)
```

See [spec.md](spec.md) for full specification and [DESIGN.md](DESIGN.md) for UI/UX reference.
