# PRD: Niche Radar Alpha

> Status: Approved (baseline — describes the shipped alpha)
> Last updated: 2026-06-24
> Absorbs: `docs/PRODUCT.md`, `README.md` overview, `.ralph/prd.json` (Docker-runtime epic)

## 1. Problem & Vision

Entrepreneurs and indie hackers spend hours manually scanning Reddit, Hacker News, Twitter/X, and YouTube for emerging product ideas and unmet user needs. By the time a trend is obvious, the market is crowded. There is no automated, cross-platform system that continuously monitors public signals, extracts pain points, scores opportunity quality, and delivers actionable daily reports of high-potential niches.

**Vision:** A self-hosted radar that watches the public web for *validated pain*, clusters it into candidate niches, scores each on opportunity quality, and hands the operator a ranked shortlist with a build-ready brief — so the decision becomes "which of these 10 do I build," not "where do I even look."

## 2. Users

- **Solo founders / indie hackers** — validated product ideas with low build complexity.
- **Side-project builders** — quick signal on trending topics before committing weekends.
- **Micro-SaaS operators** — monitoring adjacent opportunities in their space.
- **Content creators** — trending topics for articles, videos, courses.

Single-user, self-hosted. No auth, no multi-tenancy.

## 3. Features & Priority Triage

### P0 — Product fails without it
- **Multi-source ingestion** through a resilient collector layer. Each source normalizes to `CollectorResult` / `raw_items`. Fragile or blockable sources run an ordered **multi-backend fallback chain** (ADR-002) so one backend breaking does not take the source down.
- **8-agent LLM pipeline** (A1–A8): signal filter → pain extractor → (clustering) → market researcher → opportunity scorer → feasibility analyst → go/no-go judge → PRD writer (GO only) → brief creator. Zero-shot, structured-JSON, partial-failure tolerant (ADR-003).
- **Scored niche candidates** — 7-dimension 0–100 composite score, GO/NO-GO/PIVOT verdict, build-complexity estimate; persisted to SQLite (ADR-001).
- **Web dashboard** — opportunity table, niche detail, shortlist, pipeline control, report viewer. Reaches the backend at runtime via the Next.js `/api` proxy.
- **Background automation** — APScheduler: collection every 4h, analysis every 6h, cleanup daily.
- **Pluggable LLM** — OpenAI-compatible (OpenAI/DeepSeek/Groq/Ollama) + Anthropic, configured from the web UI; connection testable before a run.

### P1 — Ship shortly after
- Source expansion beyond the launch set (Stack Overflow, Product Hunt, G2, Indie Hackers, App/Play Store, Bluesky, ScrapeCreators trio).
- Cost observability — per-niche cost attribution, cache-hit tracking, A1 filter-rate.
- First-run onboarding (settings redirect when no LLM key configured).

### P2 — Defer
- Entity-intelligence layer (tracking specific products/companies over time).
- Score-transparency UI (per-dimension breakdown).
- Server decomposition (`server.py` split by concern).

## 4. Boundaries / Non-Goals

- **Not** a market-research platform with paid data providers — sources are free/public (a key may unlock a more stable path, but no source is gated behind a mandatory paid API).
- **Not** a CRM or project-management tool — stops at idea validation + PRD/brief.
- **No** user authentication or multi-tenancy — single-user self-hosted.
- **No** real-time streaming — batch collection/analysis cycles.

## 5. Technical Direction

- Python 3.11+ pipeline; FastAPI + Uvicorn API; SQLite default with PostgreSQL opt-in; Next.js 14 dashboard; Docker Compose deployment. Pluggable LLM behind `niche_radar/llm/`.
- Resilience over breadth: a source is only as good as its most reliable backend. Capture paths are interchangeable `SourceBackend`s behind `MultiBackendCollector` (→ `docs/spec/collectors.md`).
- Cost control is architectural: clustering before per-cluster analysis; bounded per-run LLM budget.

## 6. Extensibility

- **New source:** implement `BaseCollector` (or `MultiBackendCollector` + `SourceBackend`s), register in `niche_radar/collectors/__init__.py::ALL_SOURCES`, add a `CREDENTIAL_SCHEMA`. Credential-gated sources stay silent (`is_available()`) until configured.
- **New backend for an existing source:** add a `SourceBackend` to that collector's chain — no rewrite. This is the seam the Agent-Reach capability port targets (→ `docs/plans/implementation-plan.md`).
- **New LLM provider:** add a client under `niche_radar/llm/` implementing the shared `chat()` interface.

## 7. Success Metrics

- Operator can go from "nothing configured" to a scored shortlist with zero paid API keys.
- A single fragile source backend failing degrades that source gracefully (fallback or skip), never the run.
- Daily report surfaces a ranked, deduplicated set of niche candidates with verdict + build complexity.

## 8. Status

Active alpha — core pipeline functional; 16 collectors implemented; dashboard operational; LLM analysis producing scored results. No stable release yet.
