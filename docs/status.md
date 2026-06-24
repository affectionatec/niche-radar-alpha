# Project Status & Progress

> **Single source of truth for "where we are."** Read at the start of every session; update at the end. The stable build plan is `docs/plans/implementation-plan.md`; **this file tracks live progress** against it.

- **Current phase:** Agent-Reach capability port — M1 keystone (Jina Reader fallback) built, awaiting verification. 🔍
- **Next up:** M1-T3 (yt-dlp YouTube backend), then M2 (extra tiers for Reddit/Twitter).
- **Code status:** 384 tests pass (baseline 371 → 384, +13). Eval runner exits 0. Lint: n/a (none configured). Verified locally in a clean venv (`pip install -e ".[dev]"` after `pip install -U setuptools wheel`).

## In-Flight Checkpoint

> Live scratch state for the current session only. Overwritten freely while working; reset to `none` at session end. **If this is not `none` at session start, the previous session crashed — recover from here.**

none

## Module Progress

Plan & contracts: `docs/plans/implementation-plan.md`. Legend: ⬜ not started · 🟡 in progress · 🔍 built, awaiting verification · ✅ verified done

| Module | Status | Notes / next action |
| ------ | :----: | ------------------- |
| Doc-chain migration (AGENTS.md + PRD/SPEC/ADR/PLAN/STATUS/VERIFY) | 🔍 | Built; PR #11 (draft). Doc-only; human-gated. |
| M1-T1 Jina Reader backend | 🔍 | Built. `_jina.py` + `backends/jina.py`; 13 new tests. 384/384 pass. Awaiting independent verification. Spec: `docs/spec/collectors.md` §3.3 |
| M1-T2 Harden G2 + Indie Hackers | 🔍 | Built. Both → `MultiBackendCollector` (direct → Jina fallback). Existing g2/IH tests still green. Awaiting independent verification. |
| M1-T3 yt-dlp YouTube backend | ⬜ | Next code task. Spec: `docs/spec/collectors.md` §3.2, §6 |
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

- **2026-06-24** — **Built M1 keystone of the Agent-Reach port: Jina Reader resilient fallback (M1-T1 + M1-T2).** New `niche_radar/collectors/_jina.py` (opt-in Jina Reader helper: `read_url` via `_http.request(raw=True)`, `is_enabled` gate, `page_to_items` document normalizer) and `niche_radar/collectors/backends/jina.py` (`JinaReaderBackend` — composed per source with a urls-fn + parse-fn, no subclass explosion). Converted `g2_reviews.py` and `indie_hackers.py` from `BaseCollector` to `MultiBackendCollector`: chain is `direct_scrape` → `jina_reader`, so when the Cloudflare-blockable HTML scrape fails the source falls through to r.jina.ai (captures the readable page as one document item). **Key design:** the Jina fallback is *opt-in* (per-source `jina_fallback`/`jina_api_key` cred or `JINA_READER_ENABLED` env) — keeps unattended runs and the test-suite from surprise outbound calls, and keeps the existing `test_cloudflare_block_returns_partial_not_crash` fully offline. **Verified (producer self-check):** `pytest` 384/384 (baseline 371 → 384, +13 new in `tests/test_collectors/test_jina_backend.py`); `python -m niche_radar.eval.runner` exits 0; scope clean (only `collectors/` + the new test). **Caveats:** ⚠️ awaiting independent verification (producer cannot self-grade ✅ — see `docs/verification-log.md`); ⚠️ landing on the same branch as the doc-chain commit (session is single-branch), so it joins PR #11 as a second commit. **What the next session should do:** after verification, start M1-T3 (yt-dlp YouTube backend) per `docs/plans/implementation-plan.md` — adds transcript capture + drops the Data API quota dependency; remember to add `yt-dlp` to the Dockerfile and gate it behind `is_available()`.

- **2026-06-24** — **Migrated the documentation system to the agentic-engineering chain.** Created root `AGENTS.md` (single source of truth, 6-section template) with `CLAUDE.md` + `.github/copilot-instructions.md` reduced to one-line pointers. Built the chain under `docs/`: `prd.md` (absorbs `PRODUCT.md` + README + `.ralph/prd.json`); `spec/` bounded contexts (`README`, **`collectors.md` full/Approved**, `analysis-pipeline`/`api`/`storage` Draft-consolidating); `adr/ADR-001..004` (+ index) seeded from `ARCHITECTURE.md` "Key Decisions" and the multi-backend code, with ADR-004 recording this migration; `plans/implementation-plan.md` (the full Agent-Reach port, M1–M4); this `status.md`; `verification-log.md`. Renamed `docs/AGENTS.md` → `docs/agent-pipeline.md` (name collision with the door) and updated `README.md` references. **Verified:** doc-only change — no `niche_radar/` code modified; baseline suite is 371 test functions / 44 files (not re-run this session as nothing executable changed). **Caveats:** ⚠️ dependencies not installed in this fresh container; first code task (M1-T1) must `pip install -e ".[dev]"` and run `pytest` + eval. **Next session should:** open the doc-chain draft PR, then start M1-T1 (Jina Reader backend) per `docs/plans/implementation-plan.md`, branching per the git-workflow.
