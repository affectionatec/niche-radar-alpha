# Niche Radar — Platform Hardening Roadmap

> **Design doc**: 7-phase roadmap to harden engineering foundations — CI quality gate, god-file decomposition, test coverage, cost observability, data-layer robustness, frontend Entity pages, and frontend engineering baseline.

**Status:** draft
**Date:** 2026-06-06
**Parallel to:** `docs/superpowers/plans/2026-06-03-intelligence-platform-roadmap.md` (product roadmap)

---

## §1 — Goal & Non-Goals

**Goal**: Make Niche Radar a disciplined, test-protected, well-architected codebase ready for rapid product expansion (Radars, Correlation, Graph, Chat, MCP) without quality regressions and god-file hell.

**Non-goals** (unchanged boundaries from the product roadmap):
- No multi-tenancy, auth, or real-time streaming
- No desktop app
- No pivot away from self-hosted indie-maker audience

**Relationship to product roadmap:** This doc runs **in parallel** with the 7-phase product roadmap (`intelligence-platform-roadmap.md`). Phase 1 (Entity Intelligence) is partially shipped — backend exists, frontend missing. This roadmap's P6 delivers the frontend; the other 6 phases are shared infrastructure both roadmaps depend on.

---

## §2 — Phase Overview

| # | Phase | Goal | Key Deliverables |
|---|---|---|---|
| **P1** | CI / Eval Quality Gate | Prevent LLM pipeline quality regressions | GitHub Actions workflow running pytest + golden-set eval on every push; eval failures block merge |
| **P2** | Decompose `api/server.py` | Stop the 906-line god-file from blocking new endpoints | Split into 6 APIRouters: `routes/niches.py`, `sources.py`, `entities.py`, `settings.py`, `pipeline.py`, `cost.py` |
| **P3** | Test Coverage Gaps | Protect critical modules | Integration tests for orchestrator, pipeline phase A/C/D, top-3 collectors |
| **P4** | Cost & Token Observability | Know where money goes | Per-niche cost attribution, prompt-cache hit-rate tracking, dashboard cost page enhancement |
| **P5** | SQLite WAL + PG First-Class | Remove data-layer bottlenecks | Enable WAL, connection-per-worker, PG profile smoke in CI |
| **P6** | Frontend Entity Pages | Release Phase 1 value to users | Entities list, Trending list, Entity Detail with mention timeline chart |
| **P7** | Frontend Engineering Baseline | Ready for Radars/Signals/Graph expansion | API client layer, Playwright smoke tests, design-token hygiene |

**Estimated total:** 12–17 working days. Each phase is an independent PR; any can be merged or reverted independently.

---

## §3 — Architecture Principles (All Phases)

1. **Vertical slice**: Each phase delivers one complete, demo-able capability; no unused abstractions
2. **Test-driven**: Write failing test first, then implementation; test isolation follows existing `tests/test_entities/conftest.py` monkeypatch pattern
3. **End-to-end verification**: Every phase must pass `docker compose up -d` → manual green-path walk → all integration tests green
4. **No new dependencies unless necessary**: Reuse FastAPI, SQLAlchemy, Next.js 14, SWR, Tailwind; introduce libraries only when the cost of hand-rolling exceeds the dependency cost
5. **No backward-compat shims**: Change the code, update callers, done; no `_legacy_*` or `// removed` markers

---

## §4 — Phase Template (repeated per phase in implementation plans)

```
Goal           — one sentence
Why now        — dependency rationale + risk motivation
Deliverables   — files, routes, UI changes, configuration
Test plan      — failing-test list, integration test paths, manual smoke steps
Success criteria — machine-verifiable done conditions
```

---

## §5 — P1: CI / Eval Quality Gate

**Goal:** Block merges when the LLM pipeline degrades.

**Deliverables:**
- `.github/workflows/ci.yml` — `on: push` runs pytest + golden-set eval
- `eval/` golden-set runner upgraded: reads `eval/golden_set.json`, replays against A1/A4/A6 with mocked LLM (fixture responses, zero token cost), compares to expected outputs
- Fail threshold: A1 pass-rate drop > 5pp, A6 verdict mismatch > 10pp from last tagged baseline
- Readme updated with CI badge

**Test plan:**
- Mocked golden-set eval (0-token, deterministic)
- `pytest` full suite (all 36 existing + new eval runner test)
- Manual: push to branch, watch Actions run, observe red→green

**Success criteria:**
- `gh run list` shows passing CI on this branch
- Artificially breaking a golden expectation makes CI red

**Estimated:** 1–2 days

---

## §6 — P2: Decompose `api/server.py`

**Goal:** Split the 906-line monolith APIRouter into 6 focused modules.

**Why now:** P3 (test coverage) is painful until routes are in separate files; P6 (Entity frontend) adds more endpoints.

**Deliverables:**
- `niche_radar/api/routes/__init__.py` — FastAPI app that mounts all sub-routers
- `niche_radar/api/routes/niches.py` — `/api/niches`, `/api/niches/{id}`, shortlist, validate, momentum, reports
- `niche_radar/api/routes/sources.py` — `/api/sources`, `/api/sources/{slug}`
- `niche_radar/api/routes/entities.py` — `/api/entities`, `/api/entities/trending`, `/api/entities/{id}`, `/api/entities/{id}/mentions`
- `niche_radar/api/routes/settings.py` — `/api/settings`, scoring-weights, models, prompt-packs
- `niche_radar/api/routes/pipeline.py` — `/api/pipeline/collect`, `/analyze`, `/report`, `/run-all`, `/jobs`
- `niche_radar/api/routes/cost.py` — `/api/cost/summary`
- `niche_radar/api/server.py` shrinks to: `app = FastAPI(...)`, middleware, `_db()` helper, mount routers

**Key constraint:** Zero endpoint path changes. Every existing frontend API call must route identically. `_db()` helper and `_tier()` move to `routes/_common.py` or shared utility.

**Test plan:**
- Move existing tests into corresponding `tests/test_api/test_niches.py`, `test_sources.py`, `test_entities.py`, `test_settings.py`, `test_pipeline.py`
- `tests/test_api/test_basic.py` — smoke test every endpoint returns 200
- Verify with `pytest tests/test_api/` — must be green

**Success criteria:**
- `wc -l niche_radar/api/server.py` < 100
- All 35 endpoints still return identical status codes
- Pytest all green

**Estimated:** 1 day

---

## §7 — P3: Test Coverage Gaps

**Goal:** Integration-test the modules with lowest coverage — orchestrator, pipeline phases, top-3 collectors.

**Why now:** P2 unblocks clean test organization by route. Without basic coverage on pipeline orchestration, P4 (cost tracking) and P5 (data layer) changes have no safety net.

**Deliverables:**
- `tests/test_agents/test_orchestrator.py` — `run_single()` and `run_cluster()` with mock LLM; verify A1→A2 chain, A3→A8 chain, BudgetExceeded handling
- `tests/test_agents/test_pipeline.py` — phase-A persistence (pain extraction saved), phase-C output → `niche_candidates` rows, phase-D `attach_latest_analysis`
- `tests/test_collectors/test_reddit.py` — mock PRAW, verify `run_collector()` produces `CollectorResult`
- `tests/test_collectors/test_hackernews.py` — mock Firebase, same shape
- `tests/test_collectors/test_github_trending.py` — mock REST, same shape
- `tests/test_llm/test_usage.py` — `flush_usage()` writes to DB, per-agent token counting

**Test approach:** All use `monkeypatch` for external dependencies (LLM, HTTP, PRAW). Real SQLite. Follow `tests/test_entities/conftest.py` pattern: test-scoped DB, no module-level env var mutation.

**Success criteria:**
- `pytest --cov=niche_radar --cov-report=term-missing` shows > 60% line coverage (from current ~25% estimated)
- No test touches real LLM/network

**Estimated:** 2–3 days

---

## §8 — P4: Cost & Token Observability

**Goal:** Know per-niche token spend and cache hit rate.

**Why now:** `llm_usage` table already tracks per-call cost. But no per-niche attribution, no cache-hit visibility. P5 (data-layer changes) is easier to justify with cost data.

**Deliverables:**
- **Per-niche cost attribution**: `llm_usage` gets a nullable `niche_candidate_id` column; pipeline writes it during Phase C (cluster→niche mapping already in `pipeline.py`)
- **Prompt cache tracking**: OpenAI/Anthropic clients record `cached_tokens` + `cache_write_tokens` in `llm_usage`; `/api/cost/summary` returns cache-hit ratio
- **Frontend cost page**: Add "Cost by Niche" table (niche name → token cost → cache rate) and a sparkline of daily spend
- **Cache hit-rate gauge** on home page status card (optional — defer to iteration)

**Test plan:**
- `tests/test_cost/test_attribution.py` — run pipeline with mock LLM, verify `niche_candidate_id` populated
- Manual: trigger a run with real LLM, open cost page, verify per-niche breakdown renders

**Success criteria:**
- `/api/cost/summary` response includes `per_niche: [{niche_id, name, tokens, cost_usd}]`
- `/api/cost/summary` response includes `cache_hit_ratio: float`
- Cost page shows the new table with at least one real run's data

**Estimated:** 2 days

---

## §9 — P5: SQLite WAL + PostgreSQL Production-Ready

**Goal:** Eliminate SQLite single-writer bottleneck and make PG profile a first-class deployment option.

**Deliverables:**
- `niche_radar/storage/database.py`: `PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;` on every `get_db()` for SQLite
- `niche_radar/storage/database.py`: `check_same_thread=False` removed; connections created per-thread via `threading.local()` cache
- `docker-compose.yml`: PG profile smoke — verify the `postgres` profile starts, migrations run, API responds
- `.github/workflows/ci.yml`: add PG matrix (`sqlite`, `postgres`) — test suite against both

**Key risk:** Per-thread SQLite connections must not cross threads. The existing code already wraps writes in the main thread (pipeline.py docs confirm). Per-worker read-only connections for A1/A2 LLM context assembly are safe. Verify with assertion.

**Test plan:**
- `tests/test_storage/test_wal.py` — open 2 concurrent connections, verify no `SQLITE_BUSY` on reads
- CI matrix: `strategy: {database: [sqlite, postgres]}` — green on both

**Success criteria:**
- `PRAGMA journal_mode` returns `wal` in production
- Two concurrent SELECTs succeed under WAL
- CI green on both DB backends

**Estimated:** 2 days

---

## §10 — P6: Frontend Entity Pages

**Goal:** Expose Phase 1 entity intelligence to users via the Next.js dashboard. Entities list, Trending, Entity Detail with mention timeline chart.

**Why now:** Backend routes `/api/entities`, `/api/entities/trending`, `/api/entities/{id}`, `/api/entities/{id}/mentions` are live but invisible. Frontend needs entity pages before Phase 2 product work (Radars) starts, because Radars will depend on entity references.

**Deliverables:**
- `frontend/src/app/entities/page.tsx` — paginated Entity list table: name, type badge, mention count, velocity score, source diversity. Sort by velocity / name / mentions.
- `frontend/src/app/entities/trending/page.tsx` — Top entities by velocity score, card layout with sparkline placeholder
- `frontend/src/app/entities/[id]/page.tsx` — Entity Detail: canonical name, type, aliases, first/last seen, mention count, source diversity chart (server-rendered or client bar chart), mention timeline (API-driven line chart), velocity history table
- `frontend/src/lib/api/entities.ts` — typed fetch helpers: `getEntities()`, `getTrendingEntities()`, `getEntity(id)`, `getEntityMentions(id, page)`
- Navigation: "Entities" link in sidebar/top-nav (whichever the current dashboard uses)

**Chart library:** Install `recharts` (React, Tailwind-friendly, no extra deps beyond react). Lightweight — ~50KB gzipped.

**UX pattern:** Follow existing dashboard pages (`niches/`, `cost/`) layout conventions. Dark design system, responsive. Entity Detail reuses the "score breakdown" visual pattern from Niche Detail for mention stats.

**Test plan:**
- `next build` succeeds
- Manual: `docker compose up -d`, navigate to `/entities`, verify list renders (even empty is OK), verify trending page, click through to detail. Verify API data flows to rendered UI.

**Success criteria:**
- 3 new pages render without errors
- Entity list shows real data from `/api/entities`
- Entity detail page shows mentions from `/api/entities/{id}/mentions`
- `next build` green

**Estimated:** 2–3 days

---

## §11 — P7: Frontend Engineering Baseline

**Goal:** Make the frontend ready to absorb Radars, Signals, Graph, Chat without rebuilds.

**Deliverables:**
- `frontend/src/lib/api/client.ts` — shared `fetchJson<T>(url)` wrapper with base URL from env, error handling, typed response
- Refactor existing API call sites (niches, settings, cost, pipeline) to use shared client — performance-equivalent, code dedup only
- `frontend/src/lib/api/` — typed endpoints per domain: `niches.ts`, `entities.ts`, `settings.ts`, `pipeline.ts`, `cost.ts`, `sources.ts`
- `playwright.config.ts` — 5 critical-path E2E tests:
  1. Home page loads, shows status card
  2. Niches list loads, click-through to detail
  3. Entity list loads, click-through to detail
  4. Settings → change LLM model → test connection (mocked)
  5. Pipeline → trigger run → see job appear
- `.github/workflows/ci.yml` — Playwright step (headless chromium, after backend is up)
- `frontend/tailwind.config.ts` — audit unused design tokens, remove (or comment `// reserved for Phase N`)

**Test plan:**
- `npx playwright test` — 5 tests pass
- `next build` + `next lint` green
- CI: Playwright step green in Actions

**Success criteria:**
- All API calls in the frontend go through `lib/api/client.ts`
- Playwright tests pass in CI
- `next lint` reports no errors or warnings

**Estimated:** 2 days

---

## §12 — Phase Dependencies

```
P1 (CI gate) ──────────────────────────► Must ship first — quality gate protects all subsequent phases
   │
   ├──► P2 (decompose server.py) ──► P3 (test coverage, depends on P2's clean route layout)
   │                                    │
   │                                    └──► P4 (cost observability) ──► P5 (data layer)
   │                                                                       │
   └──► P6 (frontend Entity) ────────────────────────────────────────────── │
                                                                            ▼
                                                         P7 (frontend baseline, last — ties everything together)
```

**Critical path:** P1 → P2 → P3 → P4 → P5 → P7
**Parallelizable:** P6 can run alongside P2–P4 (frontend-only, no server.py dependency)
**P1 is a hard blocker** — no other phase ships before it.

---

## §13 — Test Strategy (End-to-End Standard)

Per user direction (Q3): **pytest integration test + manual green-path walk.**

Per phase:
| Phase | Integration Tests | Manual Smoke |
|---|---|---|
| P1 | CI YAML + golden-eval runner | Push to branch, watch Actions |
| P2 | All 35 endpoints return 200 | `curl` each route group |
| P3 | 5 new test files | `pytest --cov` report |
| P4 | Cost attribution test | Open cost page, verify breakdown |
| P5 | WAL concurrency test | `docker compose --profile postgres up` |
| P6 | `next build` green | Navigate entities→trending→detail |
| P7 | 5 Playwright specs | `npx playwright test` |

**Integration test approach:**
- Real SQLite (in-memory or temp file)
- FastAPI `TestClient` for route tests
- `monkeypatch` for LLM client, HTTP collectors, PRAW (follows `tests/test_entities/conftest.py`)
- No module-level env var mutation (follows `fix(entities)` commit: `52d2e62`)

---

## §14 — Risk Register

| Risk | Likelihood | Mitigation |
|---|---|---|
| P2 breaks a frontend API call silently | Medium | P7 Playwright catches regressions; P1 CI catches before merge |
| Golden eval too brittle (exact-match on LLM output) | High | Threshold-based (5pp/10pp), not exact match; use deterministic mock fixtures |
| WAL breaks existing SQLite code that assumes serialized access | Low | Pipeline already serializes writes in main thread; reads are already per-worker in Phase A |
| recharts adds bundle bloat | Low | ~50KB gzipped; tree-shakable; verify with `next build --debug` |
| P6 Entity pages receive empty data in manual smoke | Medium | Pre-populate DB with fixture data or trigger a collection+extraction run first |

---

## §15 — Success Criteria (Roadmap-Level)

- [ ] `gh run list` shows green CI on main after each phase merge
- [ ] `niche_radar/api/server.py` < 100 lines
- [ ] `pytest --cov` > 60% line coverage
- [ ] `/api/cost/summary` includes per-niche attribution + cache-hit ratio
- [ ] SQLite runs in WAL mode; PG profile CI-green
- [ ] 3 Entity pages live on dashboard
- [ ] 5 Playwright E2E tests pass in CI
- [ ] `next lint` clean
