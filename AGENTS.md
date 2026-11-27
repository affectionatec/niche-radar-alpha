# Niche Radar Alpha

## Project

Niche Radar is a self-hosted trend-intelligence tool for solo founders, indie
hackers, side-project builders, and micro-SaaS operators. It collects public
signals, extracts pain points, and presents evidence and product opportunities
through a dashboard and Markdown reports.

The goal is an actionable shortlist grounded in original sources, with generated
assessment clearly separated from evidence. The agreed product direction is
automatic evidence discovery plus on-demand Quick Win / Scalable Product
assessment; the current code still automatically runs the full eight-agent
pipeline. See [architecture](docs/architecture.md) for both behaviors.

Scope is a single operator and batch processing. Multi-tenancy, real-time
streaming, CRM/project management, and mandatory paid-data infrastructure are
outside the product goal. Optional sources and LLM providers can require keys.

## Architecture

Python 3.11+, FastAPI/Uvicorn (:8000), SQLite, APScheduler, Next.js 15 with React,
TypeScript and SWR (:3000), and Docker Compose.

```text
niche_radar/
  collectors/   BaseCollector, CollectorResult, ordered SourceBackend fallbacks
  analysis/     Analysis entry point and LLM client selection
  agents/       A1–A8 models, prompts, orchestration, clustering, scoring
  llm/          OpenAI-compatible/Anthropic clients and usage accounting
  storage/      SQLite schema, migrations, repository, retention cleanup
  api/          FastAPI routes, session auth, persistent pipeline jobs
  entities/     Entity extraction, mentions, and velocity
  reports/      Daily reports and weekly digests
  eval/         Fixture replay and live collector canary
  ui/           Rich CLI display
  config.py     Environment-backed settings
  scheduler.py  Embedded collection, analysis, cleanup, and digest jobs
frontend/src/   Dashboard, same-origin API proxy, shared components and client
prompt_packs/  YAML prompt overrides
eval/          Golden labels and response fixtures
tests/         Python tests; frontend/tests/ holds Node proxy tests
```

Data flows from Collectors to Raw Items, A1/A2 extraction, clustering, A3–A8
assessment, Niche Candidates, and reports/API/dashboard. External integrations
include public platform APIs/scrapers, opt-in Jina Reader, yt-dlp, optional Exa
and ScrapeCreators, and configured OpenAI-compatible or Anthropic endpoints.
Production traffic passes through Cloudflare and Traefik to the Next proxy.

## Key decisions & constraints

- SQLite WAL is the implemented store: simple deployment for one operator; the `postgres` Compose profile provisions a database but the Python storage layer has no PostgreSQL adapter.
- Use ordered `SourceBackend` fallbacks for fragile sources: the first available backend yielding items wins, so one capture failure need not disable a source.
- Keep backend construction and availability checks cheap and free of network calls; missing credentials/binaries should skip that path.
- Keep Jina relay calls opt-in to avoid surprise outbound requests; headless collectors must not depend on an interactive desktop browser.
- Prefer yt-dlp for YouTube descriptions/transcripts with bounded enrichment and API/scrape fallback; Xiaoyuzhou currently captures text metadata without audio transcription.
- Preserve focused Pydantic agent outputs and partial-failure reporting to contain malformed model responses.
- Cluster before expensive per-cluster analysis and retain `BudgetTracker` call limits to control cost; do not treat the budget formula as a dollar cap.
- Proxy `/api/*` at runtime through Next using `BACKEND_URL`, preserving Cookie/Set-Cookie and safe methods instead of baking an API host into the client build.
- Production uses application-owned, eight-hour signed Cookie sessions from fixed Docker secrets; development bypasses auth and must remain local.

## Conventions

- Use `from __future__ import annotations`, type annotations, and dataclasses/Pydantic for structured Python I/O. Match existing formatting; no Python formatter is enforced.
- Use the domain terms in [CONTEXT.md](CONTEXT.md), including Collector, Raw Item, Niche Candidate, Pipeline, and Verdict.
- Make focused changes. Record errors with `structlog`; preserve explicit fallback behavior and surface partial failures rather than swallowing exceptions silently.
- Mock network/CLI/LLM calls in regression tests. Live source checks belong in the optional canary, not routine test runs.
- Keep secrets, `.env`, databases, private reports, and session tokens out of commits and logs. Settings responses must mask credentials; auth tokens never belong in Web Storage.
- Preserve the exact production public allowlist, fail-closed secret handling, trusted-proxy login limiting, and secure Cookie attributes described in the architecture notes.
- Work on a focused branch and use a reviewed PR for shared changes; do not commit directly to `main` or merge without owner authorization. Follow the user's explicit local-only instructions when applicable.
- Keep product copy and UI consistent with [PRODUCT.md](PRODUCT.md) and [DESIGN.md](docs/DESIGN.md).

## Commands

Run from the repository root unless the command explicitly changes directory.
These commands come from the CLI, package manifests, Compose files, and CI.

```bash
# Install (Python 3.11+; Node 20 is used by CI)
python -m pip install --upgrade pip setuptools wheel
pip install -e ".[dev]"
(cd frontend && npm ci)

# Run locally: scheduler + API, then frontend in a separate terminal
python -m niche_radar serve
(cd frontend && npm run dev)
# API alone, without scheduled jobs
uvicorn niche_radar.api.server:app --host 127.0.0.1 --port 8000

# One-shot operations (analysis can call the configured paid LLM)
python -m niche_radar collect
python -m niche_radar analyze
python -m niche_radar report
python -m niche_radar status
python -m niche_radar cleanup

# Regression checks, lint, audit, and production build
python -m pytest
python -m niche_radar.eval.runner
(cd frontend && npm test && npm run lint && npm audit --omit=dev --audit-level=high && npm run build)

# Container build/run and production configuration checks
docker compose build
docker compose up -d
docker compose -f docker-compose.yml -f docker-compose.prod.yml config --quiet
docker compose --profile postgres -f docker-compose.yml -f docker-compose.prod.yml config --quiet
docker compose -f docker-compose.yml -f docker-compose.prod.yml build
git diff --check
```

Production deploys the exact successful `main` CI SHA through GitHub Actions.
For an authorized re-run: `gh workflow run deploy-production.yml -f release_sha=<full-main-sha>`.
Release, health checks, secret rotation, and rollback: [deployment](docs/deployment.md).

## Verification

For executable changes, Python tests and golden-set eval must pass; frontend
changes also need Node tests, lint, production audit, and build. Production
wiring changes need both Compose configuration checks and image builds, matching
CI. Report checks actually run and any limits; do not weaken tests to get green.
For documentation-only changes, check links, references, and `git diff --check`.
