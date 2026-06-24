# Project Status & Progress

> **Single source of truth for "where we are."** Read at the start of every session; update at the end. The stable build plan is `docs/plans/implementation-plan.md`; **this file tracks live progress** against it.

- **Current phase:** Documentation-chain migration → starting Agent-Reach capability port (M1). 🟡
- **Next up:** M1-T1 (shared Jina Reader backend) once the doc-chain PR is open.
- **Code status:** Baseline 371 test functions across 44 files. CI gate = `pytest` + `python -m niche_radar.eval.runner`. Doc-chain migration is documentation-only (no `niche_radar/` code touched).

## In-Flight Checkpoint

> Live scratch state for the current session only. Overwritten freely while working; reset to `none` at session end. **If this is not `none` at session start, the previous session crashed — recover from here.**

none

## Module Progress

Plan & contracts: `docs/plans/implementation-plan.md`. Legend: ⬜ not started · 🟡 in progress · 🔍 built, awaiting verification · ✅ verified done

| Module | Status | Notes / next action |
| ------ | :----: | ------------------- |
| Doc-chain migration (AGENTS.md + PRD/SPEC/ADR/PLAN/STATUS/VERIFY) | 🔍 | Built; ships as draft PR #1 on `claude/practical-carson-ufbuen`. Awaiting human review (doc-only; exempt from verifier gate per independent-verification "doc typo" scope, but human-gated). |
| M1-T1 Jina Reader backend | ⬜ | Next task. Spec: `docs/spec/collectors.md` §3.3 |
| M1-T2 Harden G2 + Indie Hackers | ⬜ | Depends on M1-T1 |
| M1-T3 yt-dlp YouTube backend | ⬜ | Parallel with M1-T1 |
| M2 Extra tiers (Reddit, Twitter, GitHub) | ⬜ | After M1 |
| M3 New channels (V2EX, Xueqiu, Exa, Bilibili, 小宇宙) | ⬜ | Keyless/native first |
| M4 Cookie/ToS channels (小红书, LinkedIn) | ⬜ | Last; per-channel ADR required |

## Decisions

Locked in `docs/adr/`. **Do not relitigate** — raise changes with the user.
- ADR-001 SQLite default · ADR-002 multi-backend fallback · ADR-003 eight-agent pipeline · ADR-004 adopt agentic-engineering chain.

## Open Items (non-blocking)

- `docs/spec.md` (monolith) coexists with `docs/spec/` during incremental decomposition (ADR-004). Becomes blocking only if the two diverge — `docs/spec/` is authoritative on conflict.
- `.ralph/` and `docs/superpowers/` remain as legacy/historical. Retire once open items are absorbed; non-blocking.
- `docs/spec/{analysis-pipeline,api,storage}.md` are Draft (consolidating) — harden as their domains get touched.
- ⚠️ **Env blocker for code work:** `pip install -e ".[dev]"` fails in this fresh container — the transitive dep `pyjsparser` (via `trendspyg`/Google Trends) won't build against the system setuptools (`AttributeError: install_layout`). Becomes blocking at M1-T1 (first code task needs `pytest`). Fix before M1: upgrade build tooling (`pip install -U pip setuptools wheel` in a venv) or install a prebuilt `pyjsparser`/skip `trendspyg` for local test runs.

## Session Handoff Log

Newest first.

- **2026-06-24** — **Migrated the documentation system to the agentic-engineering chain.** Created root `AGENTS.md` (single source of truth, 6-section template) with `CLAUDE.md` + `.github/copilot-instructions.md` reduced to one-line pointers. Built the chain under `docs/`: `prd.md` (absorbs `PRODUCT.md` + README + `.ralph/prd.json`); `spec/` bounded contexts (`README`, **`collectors.md` full/Approved**, `analysis-pipeline`/`api`/`storage` Draft-consolidating); `adr/ADR-001..004` (+ index) seeded from `ARCHITECTURE.md` "Key Decisions" and the multi-backend code, with ADR-004 recording this migration; `plans/implementation-plan.md` (the full Agent-Reach port, M1–M4); this `status.md`; `verification-log.md`. Renamed `docs/AGENTS.md` → `docs/agent-pipeline.md` (name collision with the door) and updated `README.md` references. **Verified:** doc-only change — no `niche_radar/` code modified; baseline suite is 371 test functions / 44 files (not re-run this session as nothing executable changed). **Caveats:** ⚠️ dependencies not installed in this fresh container; first code task (M1-T1) must `pip install -e ".[dev]"` and run `pytest` + eval. **Next session should:** open the doc-chain draft PR, then start M1-T1 (Jina Reader backend) per `docs/plans/implementation-plan.md`, branching per the git-workflow.
