> **Stop. Read this entire file before doing anything.**
> This is the single source of truth for how we work on this project.
> Tool-specific files (CLAUDE.md, .github/copilot-instructions.md, .cursor/rules/)
> all point here. Do not look for instructions elsewhere.

## 1. Project Identity

- **Name:** Niche Radar Alpha
- **One-liner:** Automated trend-intelligence pipeline that monitors 16 public platforms, runs an 8-agent LLM analysis pipeline, and delivers scored niche/product opportunities through a web dashboard.
- **Tech stack:** Python 3.11+ · FastAPI + Uvicorn (`:8000`) · SQLite default / PostgreSQL opt-in · APScheduler · Next.js 14 dashboard (`:3000`) · Docker Compose · pluggable LLM (OpenAI-compatible + Anthropic).
- **Repo structure:**

```
niche_radar/            Python package — the pipeline
  collectors/           Data-source ingestion. BaseCollector → CollectorResult.
                        multi_backend.py (ordered fallback chain), x_backends/,
                        one module per source (reddit, hackernews, youtube, …)
  agents/               8-agent LLM pipeline. pipeline.py, orchestrator.py,
                        models.py (A1–A8 Pydantic I/O), clustering.py, prompts.py
  llm/                  Pluggable LLM clients (openai_compat.py, anthropic_client.py)
  analysis/             analyzer.py — analysis entry point + _get_llm_client
  storage/              SQLite repository, schema, retention cleanup
  api/                  FastAPI server.py + routes/ + jobs.py
  reports/              Markdown report generation
  eval/                 Golden-set eval harness (runner, golden_set, mock_client)
  entities/             Entity-intelligence
  ui/                   CLI / rich UI
  scheduler.py          APScheduler — collect 4h, analyze 6h, cleanup daily
  config.py             pydantic-settings configuration
frontend/               Next.js 14 dashboard (SWR, /api/[...proxy] → backend)
tests/                  pytest suites (44 files, 371 test functions)
docs/                   Documentation chain — see §2
.ralph/                 Legacy Ralph-loop PRD (superseded by the chain — ADR-004)
docs/superpowers/       Legacy Superpowers plans/specs (absorbed by the chain — ADR-004)
```

## 2. Documentation Chain — Read Before You Code

This project uses a six-document chain. **Read them in order.**

| Doc | Path | Purpose | When to Read |
|-----|------|---------|-------------|
| **PRD** | `docs/prd.md` | What we're building and why | Before any feature work |
| **SPEC** | `docs/spec/*.md` | Precise technical contracts per bounded context | Before writing any code |
| **ADR** | `docs/adr/ADR-*.md` | Why we chose A over B — append-only, never rewrite | Before making architectural decisions |
| **IMPL PLAN** | `docs/plans/implementation-plan.md` | Milestones and dependency-ordered tasks | Before starting a task |
| **STATUS** | `docs/status.md` | Where we are right now — live progress | **First thing every session** |
| **VERIFICATION LOG** | `docs/verification-log.md` | Verdicts with evidence for every completed task — append-only | Before marking anything done |

**Domain glossary:** `CONTEXT.md` is the canonical glossary. Use its exact terms (Collector, Raw Item, Niche Candidate, Pipeline, Verdict, …) in code, comments, and PRs. If a new domain concept recurs, add it to `CONTEXT.md`.

**Legacy / reference docs (absorbed, not authoritative for workflow):** `docs/agent-pipeline.md` (A1–A8 design philosophy), `docs/ARCHITECTURE.md`, `docs/PRODUCT.md`, `docs/DESIGN.md` (UI system), `docs/spec.md` (original monolithic MVP spec, being decomposed into `docs/spec/`).

### Session Protocol

1. **Start of session:** Read `docs/status.md`. If the In-Flight Checkpoint is not `none`, the previous session crashed — recover from it. Otherwise the latest handoff log entry is your briefing.
2. **Before coding:** Read the SPEC for the module you're working on (`docs/spec/`). Follow the contract exactly.
3. **Decision point:** Check `docs/adr/` before making any architectural choice. If no ADR covers it, flag it to the user.
4. **After each completed task:** Checkpoint `docs/status.md` (In-Flight Checkpoint + module table). Push the task branch and open a draft PR, then request independent verification — the task stays at 🔍 until a verifier with fresh context returns PASS. Never mark your own work ✅; never merge your own PR.
5. **End of session:** Update `docs/status.md` — module table, header block, append a handoff log entry, reset the In-Flight Checkpoint to `none`.

---

## 3. Coding Conventions

- **Language:** Python 3.11+, `from __future__ import annotations`, full type annotations, dataclasses / Pydantic models for structured I/O.
- **Domain language:** Reuse `CONTEXT.md` terms. Avoid generic names when a domain term exists.
- **Test framework:** pytest. **Test command:** `pytest` (config in `pyproject.toml` adds `-v --tb=short`).
- **Eval gate:** `python -m niche_radar.eval.runner` — the golden-set eval must pass (CI enforces it alongside pytest).
- **Frontend:** `cd frontend && npm run build` (Next.js build doubles as typecheck).
- **Build:** `docker compose build`.
- **Pre-commit checks (run before any push):** `pytest && python -m niche_radar.eval.runner`.
- **Linter/formatter:** none enforced in CI today. Keep style consistent with surrounding code; do not introduce a formatter or new dependency without an ADR.
- **Discipline:** smallest complete change; surgical edits only — no drive-by refactors; keep behavior explicit — no silent fallbacks or broad `except` swallowing; every changed line maps to the requested outcome.

---

## 4. Architecture Constraints (Quick Reference)

> Full rationale in `docs/adr/`. **Do not relitigate** — raise changes with the user.

- **SQLite is the default store; PostgreSQL is opt-in** via the Docker Compose `db` profile (ADR-001).
- **Fragile/blockable sources run through an ordered multi-backend fallback chain**, not a single capture path — one backend breaking must not take a source down (ADR-002). New capture paths are added as `SourceBackend`s, not rewrites.
- **Analysis is 8 separate zero-shot, structured-JSON LLM agents (A1–A8)**, not one monolithic prompt — focused Pydantic I/O, graceful partial failure (ADR-003).
- **The agentic-engineering documentation chain (this file + `docs/`) is the canonical workflow** (ADR-004), superseding the ad-hoc Superpowers/Ralph setup.
- **Cost is capped:** clustering (Jaccard + LLM refinement) collapses raw items into clusters before A3–A8; per-run LLM budget is bounded by `2N + 10C + 50`.
- **Single-user, self-hosted:** no auth, no multi-tenancy, batch (not real-time) cycles.
- **Frontend reaches the backend at runtime** via the Next.js `/api/[...proxy]` rewrite — no build-time API URL baking.

---

## 5. Boundaries — What You Must NOT Do

- **Do not create files outside the defined structure** without asking.
- **Do not install new dependencies** without asking (and record the choice as an ADR).
- **Do not modify ADRs.** They are append-only. Supersede with a new ADR if needed.
- **Do not skip the status update.** Every session ends with a handoff log entry.
- **Do not guess when the spec is ambiguous.** Ask the user.
- **Do not grade your own work.** Marking a task ✅ requires an independent verifier's PASS, not your claim.
- **Do not delete, skip, or weaken tests to make a run pass.** The suite count only goes up (test ratchet). A failing test is information, not an obstacle.
- **Do not redefine "done" mid-task.** Acceptance criteria are locked when the task starts; changes require the user's explicit approval.
- **Do not commit directly to `main`.** Every task gets its own branch and ships as a draft PR (one task = one PR).
- **Do not merge your own PR.** Merge requires the verifier's PASS and a human who has read the diff.

---

## 6. Verification — Self-Check, Then Independent Gate

### 6.1 Producer self-check (necessary, never sufficient)

Before claiming a task is built:

1. **Tests pass:** `pytest` — report exact count (e.g., "374/374 passed").
2. **Eval passes:** `python -m niche_radar.eval.runner` exits 0.
3. **No regressions:** all pre-existing tests still pass.
4. **Test ratchet holds:** suite count ≥ previous baseline — no tests deleted or skipped.
5. **Spec compliance:** every acceptance criterion in the relevant `docs/spec/` is met.
6. **Status updated:** `docs/status.md` reflects what you just did.

### 6.2 Independent verification (the gate)

- A verifier with **fresh context** — sub-agent or fresh session, never this conversation — re-runs the task's done condition exactly as written in the SPEC / IMPL PLAN and appends a verdict with evidence to `docs/verification-log.md`.
- Only a PASS verdict moves the task from 🔍 to ✅ in STATUS.
- Three consecutive FAILs on the same task → stop and escalate to the user. Do not loop indefinitely; do not weaken criteria to converge.

### 6.3 Human gate (before merge)

- A human reads the diff and can explain the change in their own words before it merges.
- The verification log entry is the review digest: what changed, what was proven, what the risks are.
