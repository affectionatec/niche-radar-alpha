# Project Status & Progress

> **Single source of truth for "where we are."** Read at the start of every session; update at the end. The stable build plan is `docs/plans/implementation-plan.md`; **this file tracks live progress** against it.

- **Current phase:** Agent-Reach capability port — **M1 complete and merged** (Jina keystone PR #11; yt-dlp YouTube PR #12, independent verifier PASS). Starting M2. 🟡
- **Next up:** M2-T1 (Reddit `rdt-cli`/OpenCLI backend tier), then M2-T2 (Twitter `twitter-cli` tier).
- **Code status:** 397 tests pass (baseline 384 → 397, +13). Eval runner exits 0. M1-T3 independently verified PASS (see `docs/verification-log.md`, 2026-06-24).

## In-Flight Checkpoint

> Live scratch state for the current session only. Overwritten freely while working; reset to `none` at session end. **If this is not `none` at session start, the previous session crashed — recover from here.**

none

## Module Progress

Plan & contracts: `docs/plans/implementation-plan.md`. Legend: ⬜ not started · 🟡 in progress · 🔍 built, awaiting verification · ✅ verified done

| Module | Status | Notes / next action |
| ------ | :----: | ------------------- |
| Doc-chain migration (AGENTS.md + PRD/SPEC/ADR/PLAN/STATUS/VERIFY) | ✅ | Merged to main (PR #11), human-gated. |
| M1-T1 Jina Reader backend | ✅ | Merged (PR #11). `_jina.py` + `backends/jina.py`. |
| M1-T2 Harden G2 + Indie Hackers | ✅ | Merged (PR #11). `direct_scrape → jina_reader`. |
| M1-T3 yt-dlp YouTube backend | ✅ | **Verified PASS** (`docs/verification-log.md`, 2026-06-24) + merged (PR #12). `backends/ytdlp.py` + `youtube.py` → `MultiBackendCollector` (`yt_dlp → youtube_api_scrape`); ADR-005. |
| M2 Extra tiers (Reddit, Twitter, GitHub) | 🟡 | M2-T1 (Reddit) starting. |
| M3 New channels (V2EX, Xueqiu, Exa, Bilibili, 小宇宙) | ⬜ | Keyless/native first |
| M4 Cookie/ToS channels (小红书, LinkedIn) | ⬜ | Last; per-channel ADR required |

## Decisions

Locked in `docs/adr/`. **Do not relitigate** — raise changes with the user.
- ADR-001 SQLite default · ADR-002 multi-backend fallback · ADR-003 eight-agent pipeline · ADR-004 adopt agentic-engineering chain · ADR-005 yt-dlp YouTube backend.

## Open Items (non-blocking)

- `docs/spec.md` (monolith) coexists with `docs/spec/` during incremental decomposition (ADR-004). Becomes blocking only if the two diverge — `docs/spec/` is authoritative on conflict.
- `.ralph/` and `docs/superpowers/` remain as legacy/historical. Retire once open items are absorbed; non-blocking.
- `docs/spec/{analysis-pipeline,api,storage}.md` are Draft (consolidating) — harden as their domains get touched.
- ⚠️ **Env blocker for code work:** `pip install -e ".[dev]"` fails in this fresh container — the transitive dep `pyjsparser` (via `trendspyg`/Google Trends) won't build against the system setuptools (`AttributeError: install_layout`). Becomes blocking at M1-T1 (first code task needs `pytest`). Fix before M1: upgrade build tooling (`pip install -U pip setuptools wheel` in a venv) or install a prebuilt `pyjsparser`/skip `trendspyg` for local test runs.

## Session Handoff Log

Newest first.

- **2026-06-24** — **Built M1-T3: yt-dlp YouTube backend (transcripts, keyless).** New `niche_radar/collectors/backends/ytdlp.py` (`YtDlpBackend` + mockable seams `ytdlp_available` / `search_videos` / `fetch_transcript` / `vtt_to_text` / `normalize_video`). Refactored `niche_radar/collectors/youtube.py` from `BaseCollector` to `MultiBackendCollector` with chain `yt_dlp → youtube_api_scrape`: the existing Data-API/scrapetube path is preserved verbatim inside `YouTubeApiScrapeBackend` (fallback), and yt-dlp is preferred when its binary is present — captures the full description + auto-caption transcript folded into the item body, keyless (no Data-API quota). Transcript enrichment is bounded (`max_transcripts` cap) and fail-soft. Added `yt-dlp` to `requirements.txt` + `pyproject.toml` (Dockerfile installs via pip → binary on PATH; no apt step) and recorded **ADR-005** (new dependency, per AGENTS.md §5). **Verified (producer self-check):** `pytest` 397/397 (baseline 384 → 397, +13 in `tests/test_collectors/test_youtube.py`); `python -m niche_radar.eval.runner` exits 0; scope = `collectors/` + deps + ADR/docs. One unrelated network test flaked once under the sandbox proxy and passed on rerun (not a regression; it catches its own exceptions). **Caveats:** ⚠️ awaiting review in a new PR (M1 keystone already merged via PR #11); ⚠️ real transcript fetch needs the `yt-dlp` binary + network — gated by `is_available()`, so its absence degrades to the Data-API/scrapetube backend. **What the next session should do:** per the user's pacing choice, pause after this PR; when resumed, start M2 (Reddit `rdt-cli`/OpenCLI tier, then Twitter `twitter-cli` tier) per `docs/plans/implementation-plan.md`.

- **2026-06-24** — **Built M1 keystone of the Agent-Reach port: Jina Reader resilient fallback (M1-T1 + M1-T2).** New `niche_radar/collectors/_jina.py` (opt-in Jina Reader helper: `read_url` via `_http.request(raw=True)`, `is_enabled` gate, `page_to_items` document normalizer) and `niche_radar/collectors/backends/jina.py` (`JinaReaderBackend` — composed per source with a urls-fn + parse-fn, no subclass explosion). Converted `g2_reviews.py` and `indie_hackers.py` from `BaseCollector` to `MultiBackendCollector`: chain is `direct_scrape` → `jina_reader`, so when the Cloudflare-blockable HTML scrape fails the source falls through to r.jina.ai (captures the readable page as one document item). **Key design:** the Jina fallback is *opt-in* (per-source `jina_fallback`/`jina_api_key` cred or `JINA_READER_ENABLED` env) — keeps unattended runs and the test-suite from surprise outbound calls, and keeps the existing `test_cloudflare_block_returns_partial_not_crash` fully offline. **Verified (producer self-check):** `pytest` 384/384 (baseline 371 → 384, +13 new in `tests/test_collectors/test_jina_backend.py`); `python -m niche_radar.eval.runner` exits 0; scope clean (only `collectors/` + the new test). **Caveats:** ⚠️ awaiting independent verification (producer cannot self-grade ✅ — see `docs/verification-log.md`); ⚠️ landing on the same branch as the doc-chain commit (session is single-branch), so it joins PR #11 as a second commit. **What the next session should do:** after verification, start M1-T3 (yt-dlp YouTube backend) per `docs/plans/implementation-plan.md` — adds transcript capture + drops the Data API quota dependency; remember to add `yt-dlp` to the Dockerfile and gate it behind `is_available()`.

- **2026-06-24** — **Migrated the documentation system to the agentic-engineering chain.** Created root `AGENTS.md` (single source of truth, 6-section template) with `CLAUDE.md` + `.github/copilot-instructions.md` reduced to one-line pointers. Built the chain under `docs/`: `prd.md` (absorbs `PRODUCT.md` + README + `.ralph/prd.json`); `spec/` bounded contexts (`README`, **`collectors.md` full/Approved**, `analysis-pipeline`/`api`/`storage` Draft-consolidating); `adr/ADR-001..004` (+ index) seeded from `ARCHITECTURE.md` "Key Decisions" and the multi-backend code, with ADR-004 recording this migration; `plans/implementation-plan.md` (the full Agent-Reach port, M1–M4); this `status.md`; `verification-log.md`. Renamed `docs/AGENTS.md` → `docs/agent-pipeline.md` (name collision with the door) and updated `README.md` references. **Verified:** doc-only change — no `niche_radar/` code modified; baseline suite is 371 test functions / 44 files (not re-run this session as nothing executable changed). **Caveats:** ⚠️ dependencies not installed in this fresh container; first code task (M1-T1) must `pip install -e ".[dev]"` and run `pytest` + eval. **Next session should:** open the doc-chain draft PR, then start M1-T1 (Jina Reader backend) per `docs/plans/implementation-plan.md`, branching per the git-workflow.
