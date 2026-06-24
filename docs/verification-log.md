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
