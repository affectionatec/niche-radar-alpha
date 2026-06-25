# Verification Log

> Append-only record of independent verdicts, **newest first**. A task moves to ✅ in `docs/status.md` only when a verifier with **fresh context** (sub-agent or fresh session — never the producer's conversation) re-runs the task's done condition from `docs/plans/implementation-plan.md` + `docs/spec/` and records PASS here with evidence. Never edit a past verdict.

## Verdict format

```
## YYYY-MM-DD — [Task ID]: [Title] — VERDICT: PASS | FAIL
> Verifier context: fresh session/sub-agent · Diff: [commit range or branch]
Test ratchet: baseline N → now M (✅ holds / ❌ decreased)
Scope: clean / ⚠️ drift — [files outside the task's declared list]
Commands executed: | Command | Exit | Key output |
Criteria: | # | Criterion | Verdict | Evidence |
Failure detail (if any): expected vs observed, file/line — no fix proposals
Round: [1/3]
```

The canonical commands a verifier runs (from `AGENTS.md` §6 / `docs/spec/collectors.md` §7):
`pytest` (full suite, ratchet vs baseline) and `python -m niche_radar.eval.runner` (golden-set eval).

---

## 2026-06-25 — M2-T1: Reddit multi-backend + Jina tier — VERDICT: PASS

> Verifier context: fresh sub-agent (independent, did not write the code) · Diff: `7b56b0e..7d3d749` (branch `claude/practical-carson-ufbuen`)

**Test ratchet:** baseline 397 → now 401 (✅ holds, +4). No test deleted, skipped, weakened, or xfail'd (`grep "def test_"` across `tests/` = 401; zero `@pytest.mark.skip`/`xfail`/`pytest.skip(`). The only test file in the diff is the new `tests/test_collectors/test_reddit_jina.py` (additions only).

**Scope:** clean. `git diff 7b56b0e..7d3d749 --stat` touches exactly `niche_radar/collectors/reddit.py`, `tests/test_collectors/test_reddit_jina.py`, `docs/adr/ADR-006-reddit-multi-backend-jina-tier.md`, `docs/adr/README.md`, `docs/status.md`, `docs/verification-log.md` — all within the declared set. Note: the IMPL-PLAN M2-T1 row names `rdt-cli`/OpenCLI; ADR-006 (Accepted) explicitly supersedes that recipe with a `praw → public_json → jina_reader` tier (OpenCLI desktop-only / a CLI on the same datacenter IP is 403'd too). The locked done condition for this verdict is the producer self-check criteria table below, which the ADR matches. Not drift.

**Existing Reddit tests unchanged + green:** `git diff 7b56b0e..7d3d749 -- tests/test_collectors/test_reddit_search.py tests/test_collectors/test_reddit_public.py` = empty (untouched). Both pass: `10 passed`.

**Commands executed:**

| Command | Exit | Key output |
|---------|------|-----------|
| `python3 -m pytest -q` | 0 | `401 passed in 55.71s` (== expected 401, ≥ baseline 397) |
| `python3 -m pytest tests/test_collectors/test_reddit_jina.py -v` | 0 | `4 passed`; `test_praw_wins_when_creds_present`, `..._public_json_without_creds`, `..._jina_when_public_blocked`, `..._jina_off_by_default_makes_no_calls` all PASSED |
| `python3 -m pytest tests/test_collectors/test_reddit_search.py tests/test_collectors/test_reddit_public.py -q` | 0 | `10 passed` (existing Reddit tests, unmodified) |
| `python3 -m niche_radar.eval.runner ; echo EXIT=$?` | 0 | `EXIT=0`; accuracy 40% — pre-existing offline-no-LLM artifact (`got=None`), unaffected by this collectors change (matches prior verdicts) |

**Per-criterion (producer done-condition table / spec §3.2,§3.3,§2.3 / ADR-006):**

| # | Criterion | Verdict | Evidence |
|---|-----------|---------|----------|
| 1 | PRAW wins when creds present | PASS | `test_praw_wins_when_creds_present` → `metadata["active_backend"]=="praw"`, `items[0]["source_id"]=="a"`. Chain `return`s on first backend with items (`multi_backend.py:108-114`) → no fallthrough to public_json/jina, no network. |
| 2 | No creds → public_json | PASS | `test_falls_through_to_public_json_without_creds` → `active_backend=="public_json"`, `items[0]["source_id"]=="pj1"`. PRAW `is_available` False (no cid/secret). |
| 3 | public 403 + Jina enabled → jina_reader | PASS | `test_falls_through_to_jina_when_public_blocked` → `JINA_READER_ENABLED=1`, public_json raises (403, no items+errors), `active_backend=="jina_reader"`, `items[0]["metadata"]["capture"]=="jina_reader"`. |
| 4 | Jina off by default → no outbound call | PASS | `test_jina_off_by_default_makes_no_calls` patches `_http.request` to raise `AssertionError` if hit; passes. `JinaReaderBackend.is_available`→`_jina.is_enabled` is False without `JINA_READER_ENABLED`/`jina_api_key`/`jina_fallback`, so `fetch` (the only `_http.request` caller) is never invoked (`multi_backend.py:91-93`). Result degrades to `partial`/`failed`, never raises; `jina_reader` still present in `metadata["backends"]` chain. |
| 5 | Existing Reddit tests unchanged | PASS | Both files byte-identical across the range (empty diff); `10 passed`. |
| 6 | Full suite + eval | PASS | `pytest` 401 pass exit 0 (≥397); `eval.runner` exit 0. |

**Design-claim sanity check:** confirmed independently of the tests — (a) creds-present chain stops at `praw` because `_run` returns on the first item-yielding backend; (b) Jina-off path makes zero `_http.request` calls because the opt-in `is_available` gate short-circuits before `fetch`. Both hold.

**Failure detail:** none.

**Round:** 1 (first independent verdict) — PASS.

---

## 2026-06-25 — M2-T1: Reddit multi-backend + Jina tier — VERDICT: ⏳ AWAITING VERIFICATION (producer self-check)

> Producer self-check, not an independent verdict.

**Diff:** branch `claude/practical-carson-ufbuen` (new commit on merged main `7b56b0e`) · **Files:** `niche_radar/collectors/reddit.py`, `tests/test_collectors/test_reddit_jina.py`, `docs/adr/ADR-006-*`, `docs/adr/README.md`, `docs/status.md`, `docs/verification-log.md`
**Test ratchet:** baseline 397 → now 401 (✅ holds, +4)
**Scope:** `collectors/reddit.py` refactor + new test + ADR-006/docs

| Command | Exit | Key output |
|---------|------|-----------|
| `python3 -m pytest -q` | 0 | 401 passed |
| `python3 -m niche_radar.eval.runner` | 0 | runs; offline-no-LLM artifact unchanged |

**Done condition (for a verifier):**

| # | Criterion | Verify via | Expected |
|---|-----------|------------|----------|
| 1 | PRAW wins when creds present | `pytest tests/test_collectors/test_reddit_jina.py -k praw_wins` | `active_backend=="praw"` |
| 2 | No creds → public_json | `pytest tests/test_collectors/test_reddit_jina.py -k public_json` | `active_backend=="public_json"` |
| 3 | public 403 + Jina enabled → jina_reader | `pytest tests/test_collectors/test_reddit_jina.py -k jina_when_public_blocked` | `active_backend=="jina_reader"` |
| 4 | Jina off by default → no outbound call | `pytest tests/test_collectors/test_reddit_jina.py -k off_by_default` | pass |
| 5 | Existing Reddit tests unchanged | `pytest tests/test_collectors/test_reddit_search.py tests/test_collectors/test_reddit_public.py` | all pass |
| 6 | Full suite + eval | `pytest` ; `python3 -m niche_radar.eval.runner` | 401 pass; exit 0 |

**Round:** 1 (producer) — independent verdict pending.

---

## 2026-06-24 — M1-T3: yt-dlp YouTube backend — VERDICT: PASS

> Verifier context: fresh sub-agent (independent, did not write the code) · Diff: `d304393..817b4aa` (branch `claude/practical-carson-ufbuen`)

**Test ratchet:** baseline 384 → now 397 (✅ holds, +13). No test deleted, skipped, weakened, or xfail'd in the diff (`git diff d304393..817b4aa -- tests/` shows only additions; `grep "def test_"` = 397).

**Scope:** clean. Diff touches `niche_radar/collectors/backends/{__init__,ytdlp}.py`, `niche_radar/collectors/youtube.py`, `tests/test_collectors/test_youtube.py`, `requirements.txt`, `pyproject.toml`, `docs/{adr/ADR-005-*,adr/README.md,status.md,verification-log.md}` — all within the allowed set. The impl-plan declared-files list names `Dockerfile (add yt-dlp)`; the Dockerfile was NOT edited. This is a defensible, documented choice (not drift): yt-dlp is a pip console-script, and the existing `Dockerfile` already runs `pip install -r requirements.txt` (lines 5–14), which now includes the `yt-dlp` line. ADR-005 explicitly records this ("the existing Dockerfile `pip install` already provisions it; no apt step"). Spec §6 requires the binary be declared in the Dockerfile + an ADR — satisfied transitively via requirements.txt + ADR-005.

**Commands executed:**

| Command | Exit | Key output |
|---------|------|-----------|
| `python3 -m pytest -q` | 0 | `397 passed in 56.62s` (re-run; both runs 397). Known network-flake `test_api/test_sources.py::test_test_source_endpoint_exists` passed (not reported as failure). |
| `python3 -m pytest tests/test_collectors/test_youtube.py -q` | 0 | `13 passed in 0.02s` (the 13 new tests) |
| `python3 -m niche_radar.eval.runner` | 0 | exit 0; golden cases report `got=None` — the pre-existing offline-no-LLM artifact noted in prior verdicts, unaffected by this collectors change |

**Per-criterion (IMPL PLAN M1-T3 / producer done-condition table / spec §3.2,§3.3,§6):**

| # | Criterion | Verdict | Evidence |
|---|-----------|---------|----------|
| 1 | `is_available()` False when `yt-dlp` absent; never raises | PASS | `test_ytdlp_available_false_when_binary_absent`, `test_ytdlp_available_true_when_binary_present`, `test_available_never_raises` (mock `shutil.which`, incl. one that raises OSError → swallowed) all pass |
| 2 | Mocked yt-dlp payload incl. transcript → raw item with transcript in `body` | PASS | `test_normalize_folds_transcript_into_body`, `test_vtt_to_text_strips_and_dedupes`, `test_fetch_maps_videos_and_enriches_transcripts` pass; `has_transcript` True, `"Transcript:\n..."` in body |
| 3 | yt-dlp preferred when present; falls through to API/scrape when absent | PASS | `test_youtube_uses_ytdlp_when_available` → `active_backend == "yt_dlp"`; `test_youtube_falls_through_to_legacy_when_no_ytdlp` → `active_backend == "youtube_api_scrape"` |
| 4 | No live network/CLI in tests | PASS | suite ran with sandboxed egress; all CLI seams (`ytdlp_available`, `search_videos`, `fetch_transcript`) mocked; `__init__` does no network (cheap-construct, spec §3.3) |
| 5 | Full suite ratchet + eval | PASS | `pytest` 397 pass exit 0 (≥384); `eval.runner` exit 0 |
| 6 | Dockerfile installs yt-dlp; absence degrades, no crash | PASS | yt-dlp in `requirements.txt`/`pyproject.toml`; Dockerfile pip-installs requirements (lines 5–14); fallthrough proven by criterion 3. Documented in ADR-005. |

**Corroborating:** CI on PR #12 `test` job reported green (cited by dispatcher; local run is the primary verdict).

**Failure detail:** none.

**Round:** 1 (first independent verdict) — PASS.

---

## 2026-06-24 — M1-T3: yt-dlp YouTube backend — VERDICT: ⏳ AWAITING REVIEW (producer self-check)

> Producer self-check, not an independent verdict. (M1-T1/T2 above were merged via PR #11 — the repo owner reviewed and merged, satisfying the human gate.)

**Diff:** branch `claude/practical-carson-ufbuen` (new commit, on top of merged main) · **Files:** `niche_radar/collectors/backends/ytdlp.py`, `niche_radar/collectors/backends/__init__.py`, `niche_radar/collectors/youtube.py`, `tests/test_collectors/test_youtube.py`, `requirements.txt`, `pyproject.toml`, `docs/adr/ADR-005-*`, `docs/adr/README.md`
**Test ratchet:** baseline 384 → now 397 (✅ holds, +13)
**Scope:** `collectors/` + dependency manifests + ADR/docs (yt-dlp dependency recorded in ADR-005)

**Producer self-check commands:**

| Command | Exit | Key output |
|---------|------|-----------|
| `pytest -q` | 0 | 397 passed (one unrelated network test, `test_api/test_sources.py::test_test_source_endpoint_exists`, flaked once under the sandbox proxy and passed on rerun — it catches its own exceptions; environmental, not a regression) |
| `python -m niche_radar.eval.runner` | 0 | runs; accuracy unchanged (offline-no-LLM artifact, unaffected by collectors) |
| `yt-dlp --version` | 0 | 2026.06.09 (binary on PATH after `pip install`) |

**Done condition (for a verifier — IMPL PLAN M1-T3 / `docs/spec/collectors.md` §3.2,§6):**

| # | Criterion | Verify via | Expected evidence |
|---|-----------|------------|-------------------|
| 1 | `is_available()` False when `yt-dlp` absent; never raises | `pytest tests/test_collectors/test_youtube.py -k available` | pass (mocks `shutil.which`) |
| 2 | A mocked yt-dlp payload incl. transcript → raw item with transcript in `body` | `pytest tests/test_collectors/test_youtube.py -k transcript or enriches` | pass; `has_transcript` True |
| 3 | yt-dlp preferred when present; falls through to Data-API/scrape when absent | `pytest tests/test_collectors/test_youtube.py -k uses_ytdlp or falls_through` | pass; `active_backend` flips correctly |
| 4 | No live network/CLI in tests | run offline | suite passes with egress blocked |
| 5 | Full suite ratchet + eval | `pytest` ; `python -m niche_radar.eval.runner` | 397 pass; eval exit 0 |

**Round:** 1 (producer) — review pending.

---

## 2026-06-24 — M1-T1 + M1-T2: Jina Reader resilient fallback — VERDICT: ⏳ AWAITING INDEPENDENT VERIFICATION

> This is the **producer self-check**, not an independent verdict. Per the maker-checker gate, a verifier with fresh context must re-run the done condition and append a PASS/FAIL below before STATUS moves these tasks to ✅. They sit at 🔍 until then.

**Diff:** branch `claude/practical-carson-ufbuen` (code commit) · **Files:** `niche_radar/collectors/_jina.py`, `niche_radar/collectors/backends/{__init__,jina}.py`, `niche_radar/collectors/g2_reviews.py`, `niche_radar/collectors/indie_hackers.py`, `tests/test_collectors/test_jina_backend.py`
**Test ratchet:** baseline 371 → now 384 (✅ holds, +13)
**Scope:** clean — only `collectors/` + the new test

**Producer self-check commands:**

| Command | Exit | Key output |
|---------|------|-----------|
| `pytest -q` | 0 | 384 passed in ~55s |
| `python -m niche_radar.eval.runner` | 0 | runs; accuracy is an offline-no-LLM artifact, unaffected by this change |

**Done condition (for the verifier — from `docs/spec/collectors.md` §7 / IMPL PLAN M1):**

| # | Criterion | Verify via | Expected evidence |
|---|-----------|------------|-------------------|
| 1 | Jina fallback is opt-in (unavailable by default; enabled by env/key/cred) | `pytest tests/test_collectors/test_jina_backend.py -k jina_disabled or _enabled` | pass |
| 2 | Blocked direct scrape falls through to Jina and returns items | `pytest tests/test_collectors/test_jina_backend.py -k falls_through` | pass; `active_backend == "jina_reader"` |
| 3 | Blocked with Jina off degrades (no crash), still partial/failed | `pytest tests/test_collectors/test_jina_backend.py -k degrades_not_crashes` | pass |
| 4 | No live network in tests | run offline | suite passes with egress blocked |
| 5 | Full suite ratchet + eval | `pytest` ; `python -m niche_radar.eval.runner` | 384 pass; eval exit 0 |

**Round:** 1 (producer) — independent verdict pending.

---

## 2026-06-24 — Baseline established (pre-port)

> Not a task verdict — the reference point future verdicts ratchet against.

**Baseline suite:** 371 test functions across 44 files (`grep -rhoE "def test_" tests/ | wc -l` = 371; `find tests -name 'test_*.py' | wc -l` = 44).
**CI gate:** `pytest --tb=short` + `python -m niche_radar.eval.runner` (`.github/workflows/ci.yml`).
**Note:** The documentation-chain migration (PR #1) is documentation-only — no `niche_radar/` code changed — so the suite count is unchanged from this baseline. The first feature task (M1-T1) is the first entry that will carry a full PASS/FAIL verdict with executed commands.
