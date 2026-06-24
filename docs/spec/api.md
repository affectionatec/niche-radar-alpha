# Technical Specification: API Surface

> Source PRD: `docs/prd.md` §3 (P0 web dashboard + pipeline control)
> Status: Draft — consolidating. Endpoint behavior is authoritative in `niche_radar/api/server.py` + `routes/`; this spec hardens it into contracts incrementally.
> Last updated: 2026-06-24

## 1. Overview

FastAPI REST API on `:8000` serving niche data, pipeline control, and settings. ~23 endpoints (`niche_radar/api/server.py`, `routes/`, `jobs.py`). The Next.js dashboard reaches it at runtime via the `/api/[...proxy]` rewrite — no build-time API URL baking (ADR-004 follow-up; `.ralph/prd.json` US-001).

## 2. Endpoint Groups

| Group | Purpose | Key endpoints |
|-------|---------|---------------|
| Status / niches | List & detail scored niches, momentum | `GET /api/status`, niches list/detail, momentum |
| Shortlist | User curation | shortlist add/remove/notes |
| Pipeline control | Trigger & track runs | collect/analyze triggers, job status (`jobs.py` in-memory manager) |
| Settings | LLM + data-source config | `GET /api/settings`, save, `POST /api/settings/test` (LLM connection test) |
| Reports | Markdown report retrieval | report list/detail |

## 3. Contracts (invariants that must hold)

- `POST /api/settings/test` MUST return HTTP 200 with `{ok: bool, message: str}` and MUST NOT raise 5xx on a bad key/URL — connection failures are reported in the body (`.ralph/prd.json` US-003).
- `GET /api/settings` MUST expose `llm_api_key_set: bool` without leaking the key value (drives first-run onboarding redirect — US-002).
- Settings reads/writes go through `app_settings` (→ `storage.md`); the LLM client is built via `niche_radar.analysis.analyzer._get_llm_client`.
- Pipeline job state is in-memory (`jobs.py`); a process restart loses in-flight job status (acceptable for single-user; see Open Questions).

## 4. Acceptance Criteria

| # | Criterion | Verify via | Evidence |
|---|-----------|------------|----------|
| 1 | API test suite passes | `pytest tests/test_api -v` | exit 0 |
| 2 | `POST /api/settings/test` returns 200 with `ok` field on any input | `pytest tests/test_api/test_server.py -k settings_test` | exit 0 |
| 3 | Full suite + eval green | `pytest && python -m niche_radar.eval.runner` | exit 0 |

## 5. Open Questions

- Should pipeline job state persist across restarts (`pipeline_jobs` table) instead of in-memory only? (Deferred — non-blocking for single-user.)
- Enumerate all ~23 endpoints with request/response schemas here as decomposition continues.
