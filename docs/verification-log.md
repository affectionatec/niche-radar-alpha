# Verification Log

> Append-only record of independent verdicts, **newest first**. A task moves to ✅ in `docs/status.md` only when a verifier with **fresh context** (sub-agent or fresh session — never the producer's conversation) re-runs the task's done condition from `docs/plans/implementation-plan.md` + `docs/spec/` and records PASS here with evidence. Never edit a past verdict.

## 2026-06-27 — M4-T1 (Xiaohongshu) + M4-T2 (LinkedIn): Cookie/ToS-risky Jina relay collectors — VERDICT: PASS

> Verifier context: fresh sub-agent (independent, did not write the code) · Diff: `main...task/m4-cookie-channels`

**Test ratchet:** baseline 455 → now 473 (✅ holds, +18). No test deleted, skipped, or xfail'd (`grep -rn "pytest.mark.skip\|@pytest.mark.xfail\|pytest.skip(" tests/` = 0; `grep "def test_" tests/ | wc -l` = 473).

**Scope:** clean. `git diff main...task/m4-cookie-channels --stat` touches exactly `niche_radar/collectors/xiaohongshu.py` (new), `niche_radar/collectors/linkedin.py` (new), `niche_radar/collectors/__init__.py` (+9 lines for registration), `docs/adr/ADR-007-xiaohongshu-jina-tier.md` (new), `docs/adr/ADR-008-linkedin-public-jina-tier.md` (new), `docs/adr/README.md` (+2 lines), `tests/test_collectors/test_xiaohongshu.py` (new), `tests/test_collectors/test_linkedin.py` (new), `docs/status.md` (session-protocol checkpoint). `docs/status.md` is the required session-protocol checkpoint (AGENTS.md §4), consistent with prior verdicts. No changes to `requirements.txt`, `pyproject.toml`, or `Dockerfile` — no new pip dependencies.

**Commands executed:**

| Command | Exit | Key output |
|---------|------|-----------|
| `python3 -m pytest --tb=short 2>&1 \| tail -5` | 0 | `473 passed in 111.31s` (== required ≥ 473, +18 over baseline 455) |
| `python3 -m pytest tests/test_collectors/test_xiaohongshu.py tests/test_collectors/test_linkedin.py -v` | 0 | `18 passed in 0.03s`; all 18 new tests (8 XHS + 10 LinkedIn) individually PASSED |
| `python3 -m niche_radar.eval.runner; echo "EXIT:$?"` | 0 | `EXIT:0`; accuracy 40% — pre-existing offline-no-LLM artifact (`got=None`), unchanged from prior verdicts, unaffected by this collectors change |

**Per-criterion:**

| # | Criterion | Verdict | Evidence |
|---|-----------|---------|----------|
| 1 | Both registered in `ALL_SOURCES` + lazy-import dispatch | PASS | `__init__.py` lines 34–35 (`"xiaohongshu"`, `"linkedin"` in ALL_SOURCES), lines 101–106 (`elif source == "xiaohongshu": ... XiaohongshuCollector()`; `elif source == "linkedin": ... LinkedInCollector()`) |
| 2 | `CREDENTIAL_SCHEMA` on each collector class with at minimum `jina_fallback` and `jina_api_key` | PASS | Xiaohongshu: `xiaohongshu.py` lines 55–77 — `jina_fallback`, `jina_api_key`, `search_queries`. LinkedIn: `linkedin.py` lines 133–155 — `jina_fallback`, `jina_api_key`, `search_queries`. Both are `ClassVar[list[dict]]` with correct `key`, `label`, `secret`, `optional`, `help` fields. |
| 3a | Xiaohongshu `is_available()`: False when `JINA_READER_ENABLED` is off (source skipped in unattended runs) | PASS | `XiaohongshuCollector.is_available()` inherits from `MultiBackendCollector` (multi_backend.py:65–71): `any(b.is_available(...) for b in inst.build_backends())`. `build_backends()` returns `[JinaReaderBackend("xiaohongshu", _xhs_search_urls)]` (xiaohongshu.py:80). `JinaReaderBackend.is_available()` (jina.py:41) returns `_jina.is_enabled(...)`, which is False when neither `jina_fallback` cred, `jina_api_key`, nor `JINA_READER_ENABLED` are set (_jina.py:57–72). Test: `test_collector_skips_when_jina_disabled` → `is_available() is False` PASSED; `test_collector_available_when_jina_enabled` → `is_available() is True` PASSED. |
| 3b | LinkedIn `is_available()`: True even without Jina (public_search always available) | PASS | `LinkedInCollector.build_backends()` returns `[LinkedInPublicSearchBackend(), JinaReaderBackend("linkedin", ...)]` (linkedin.py:157–160). `LinkedInPublicSearchBackend.is_available()` always returns `True` (linkedin.py:78–79). `MultiBackendCollector.is_available()` `any(...)` is always True with at least one always-available backend. Test: `test_collector_available_with_public_search` → `is_available() is True` PASSED; `test_public_search_backend_always_available` → `is True` PASSED. |
| 4 | `collect()` returns `CollectorResult` with correct `metadata["backends"]` + `metadata["active_backend"]` | PASS | `MultiBackendCollector.collect()` (multi_backend.py:108–114) returns `CollectorResult` with `metadata={"backends": attempts, "active_backend": backend.name}`. XHS: `test_collect_returns_items_via_jina_backend` → `metadata["active_backend"] == "jina_reader"`, each `item["metadata"]["capture"] == "jina_reader"` PASSED. LinkedIn: `test_collector_uses_public_search_when_jina_off` → `active_backend == "public_search"` PASSED; `test_collector_prefers_jina_when_enabled` → `active_backend == "jina_reader"` PASSED. |
| 5 | `dry_run=True` returns completed with empty items | PASS | `MultiBackendCollector.collect()` (multi_backend.py:77–78): `if dry_run: return CollectorResult(self.source_name, [], "", "completed", 0)`. Both `test_collect_dry_run_returns_empty` (XHS, LinkedIn) → `status=="completed"`, `items==[]` PASSED. |
| 6 | All network mocked — no live HTTP in tests | PASS | XHS tests: `patch.object(_jina, "read_url", ...)` mocks all Jina outbound calls. LinkedIn tests: `patch("niche_radar.collectors.linkedin.requests.get", ...)` mocks public search; `patch.object(_jina, "read_url", ...)` mocks Jina. Both test files declare "fully offline" in docstrings. Suite passes in sandboxed egress. |
| 7 | pytest count ≥ 473 | PASS | `473 passed in 111.31s` (== required 473; +18 from baseline 455) |
| 8 | `python3 -m niche_radar.eval.runner` exits 0 | PASS | Exit 0; accuracy 40% — pre-existing offline-no-LLM artifact unchanged |
| 9 | ADR-007 and ADR-008 exist and are indexed in `docs/adr/README.md` | PASS | `docs/adr/ADR-007-xiaohongshu-jina-tier.md` exists (Status: Accepted, rejects OpenCLI/xhs-cli in favor of Jina Reader relay). `docs/adr/ADR-008-linkedin-public-jina-tier.md` exists (Status: Accepted, rejects linkedin-mcp in favor of public_search → jina_reader chain). `docs/adr/README.md` lines 13–14: both ADRs listed as Accepted in the index table. |
| 10 | No new pip dependencies | PASS | `git diff main...task/m4-cookie-channels -- requirements.txt pyproject.toml Dockerfile` = empty (no changes to dependency manifests) |
| 11 | LinkedIn: `test_collector_prefers_jina_when_enabled` — when public search fails and Jina is enabled, the chain falls through to `jina_reader` | PASS | Test patches `LinkedInPublicSearchBackend.fetch` to raise `RuntimeError("public search failed")`, enables Jina via `JINA_READER_ENABLED=1`, mocks `read_url`. Asserts `result.metadata["active_backend"] == "jina_reader"` and `result.status == "completed"`. Test PASSED. |

**Design-claim sanity check (independent of tests):** Both ADRs explicitly reject the literal Agent-Reach recipes (OpenCLI/xiaohongshu-mcp/xhs-cli for XHS; linkedin-mcp for LinkedIn) because those are desktop/interactive tools incompatible with an unattended pipeline. Instead, both collectors reuse the proven `JinaReaderBackend` (M1 G2/IH, M2 Reddit), with Xiaohongshu as a single-backend Jina-only collector and LinkedIn as a `public_search → jina_reader` chain where the public tier is always available and keyless. The `is_available()` gating is correct: Xiaohongshu is opt-in only (skipped when Jina is off); LinkedIn is always available (public search is keyless). No new imports beyond the existing stack (`requests`, `structlog`, `sqlite3`, `json`, `re`, `hashlib`, `datetime`). The `MultiBackendCollector` contract (ADR-002) is followed precisely: XHS as single-backend (leaves door open for TikHub later), LinkedIn as priority-ordered chain.

**Failure detail:** none.

**Round:** 1 (first independent verdict) — PASS.

## 2026-06-27 — M3-T4: Bilibili collector — VERDICT: PASS

> Verifier context: fresh sub-agent (independent, did not write the code) · Diff: `main...task/m3-t4-bilibili`

**Test ratchet:** baseline 434 → now 455 (✅ holds, +21). No test deleted, skipped, or xfail'd (`grep -rn "pytest.mark.skip\|@pytest.mark.xfail\|pytest.skip(" tests/` = 0; `grep "def test_" tests/ | wc -l` = 455).

**Scope:** clean. `git diff main...task/m3-t4-bilibili --stat` touches exactly `niche_radar/collectors/bilibili.py` (new), `niche_radar/collectors/__init__.py` (+4 lines for registration), `niche_radar/config.py` (+4 lines for settings), `tests/test_collectors/test_bilibili.py` (new), `docs/status.md` (status checkpoint). `docs/status.md` is the session-protocol checkpoint (AGENTS.md §4), not drift — consistent with prior verdicts.

**Commands executed:**

| Command | Exit | Key output |
|---------|------|-----------|
| `python3 -m pytest --tb=short 2>&1 \| tail -5` | 0 | `455 passed in 109.95s` (== required ≥ 455, +21 over baseline 434) |
| `python3 -m pytest tests/test_collectors/test_bilibili.py -v` | 0 | `21 passed in 56.23s`; all 21 new tests individually PASSED |
| `python3 -m niche_radar.eval.runner; echo "EXIT:$?"` | 0 | `EXIT:0`; accuracy 40% — pre-existing offline-no-LLM artifact (`got=None`), unchanged from prior verdicts, unaffected by this collectors change |

**Per-criterion:**

| # | Criterion | Verdict | Evidence |
|---|-----------|---------|----------|
| 1 | Registered in `ALL_SOURCES` + lazy-import dispatch | PASS | `__init__.py` line 32 (`"bilibili"` in ALL_SOURCES), lines 95–97 (`elif source == "bilibili": ... BilibiliCollector()`) |
| 2 | `CREDENTIAL_SCHEMA` defined on `BilibiliCollector` | PASS | `bilibili.py` lines 226–241: `CREDENTIAL_SCHEMA: ClassVar[list[dict]]` with `sessdata` (secret, optional) and `search_queries` (optional) |
| 3a | `BilibiliAuthApiBackend`: available only when `bilibili_sessdata` set | PASS | `bilibili.py` line 184: `return bool(_sessdata(settings, db))`; `test_auth_backend_unavailable_without_sessdata` (False), `test_auth_backend_available_with_sessdata` (True) both PASSED |
| 3b | `BilibiliPublicApiBackend`: always available | PASS | `bilibili.py` line 206: `return True`; `test_public_backend_always_available` PASSED |
| 4 | `BilibiliCollector.is_available()` returns True when at least one backend available | PASS | Inherited from `MultiBackendCollector` (multi_backend.py:65-71): `any(b.is_available(...) for b in inst.build_backends())`; public_api backend always returns True, so collector is always available. Integration tests confirm `collect()` succeeds without credentials. |
| 5 | `collect()` returns `CollectorResult` with `metadata["backends"]` and `metadata["active_backend"]` | PASS | `MultiBackendCollector.collect()` (multi_backend.py:108-113) returns `CollectorResult` with `metadata={"backends": attempts, "active_backend": backend.name}`; `test_collector_prefers_auth_when_sessdata_set` verifies `active_backend=="auth_api"`, `test_collector_uses_public_without_sessdata` verifies `active_backend=="public_api"`, `test_collector_falls_through_to_public_when_auth_fails` verifies fallthrough with `active_backend=="public_api"` |
| 6 | `dry_run=True` returns completed with empty items | PASS | `MultiBackendCollector.collect()` (multi_backend.py:77-78): `if dry_run: return CollectorResult(self.source_name, [], "", "completed", 0)`; `test_collector_dry_run_returns_empty` PASSED (`status=="completed"`, `items==[]`) |
| 7 | All network mocked — no live HTTP in tests | PASS | All `requests.Session` and `requests.get` calls wrapped in `patch(...)`; zero bare `requests.get/post/...` or `httpx` calls outside mock context; `grep -n "httpx" tests/test_collectors/test_bilibili.py` = empty |
| 8 | pytest count ≥ 455 | PASS | `455 passed` (== required 455; +21 from baseline 434) |
| 9 | `python3 -m niche_radar.eval.runner` exits 0 | PASS | Exit 0; pre-existing offline-no-LLM artifact unchanged |
| 10 | `config.py` has `bilibili_sessdata` and `freshness_bilibili_hours` | PASS | config.py line 51: `bilibili_sessdata: str = ""`; line 66: `freshness_bilibili_hours: int = 336` |
| 11 | Deduplication: same bvid from multiple queries appears once with merged `matched_queries` | PASS | `_search_videos` lines 165-168: appends query to existing item's `matched_queries` when sid already seen; `test_collector_deduplicates_across_queries` PASSED (`ids.count("bili-BVdup")==1`, `len(matched_queries)==n_queries`) |
| 12 | HTML tag stripping (`_clean`) removes Bilibili markup from titles | PASS | `_clean` (bilibili.py:88-92) uses `_HTML_TAG_RE.sub("", text).strip()`; `test_clean_strips_html_tags` PASSED (`<em>工具</em> 推荐` → `工具 推荐`), `test_clean_handles_none` PASSED, `test_clean_handles_no_tags` PASSED; `_normalize` applies `_clean` to both title and description (lines 111-112) |

**Failure detail:** none.

**Round:** 1 (first independent verdict) — PASS.

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

## 2026-06-26 — M3-T1/T2/T3: V2EX, Xueqiu, Exa collectors — VERDICT: PASS

> Verifier context: fresh sub-agent (independent, did not write the code) · Diff: `70d90d8...task/m3-new-channels` (M3 commits only)

**Test ratchet:** baseline 401 → now 434 (✅ holds, +33). No test deleted, skipped, or xfail'd (`grep -r "pytest.mark.skip\|xfail\|pytest.skip("` across `tests/` = 0; `grep "def test_"` = 434).

**Scope:** clean. `git diff 70d90d8...task/m3-new-channels --stat` touches exactly `niche_radar/collectors/{v2ex,xueqiu,exa}.py`, `niche_radar/collectors/__init__.py`, `niche_radar/config.py`, `tests/test_collectors/{test_v2ex,test_xueqiu,test_exa}.py`, `docs/status.md` — all within the declared file list. `docs/status.md` is the required session-protocol checkpoint (AGENTS.md §4), not drift.

**Commands executed:**

| Command | Exit | Key output |
|---------|------|-----------|
| `python3 -m pytest --tb=short 2>&1 \| tail -5` | 0 | `434 passed in 53.98s` (≥ required 434, +33 over baseline 401) |
| `python3 -m pytest tests/test_collectors/test_v2ex.py tests/test_collectors/test_xueqiu.py tests/test_collectors/test_exa.py -v` | 0 | `33 passed in 0.04s`; all 33 new tests individually PASSED |
| `python3 -m niche_radar.eval.runner; echo "EXIT:$?"` | 0 | `EXIT:0`; accuracy 40% — pre-existing offline-no-LLM artifact (`got=None`), unchanged from prior verdicts, unaffected by this collectors change |

**Per-criterion:**

| # | Criterion | Verdict | Evidence |
|---|-----------|---------|----------|
| 1 | v2ex, xueqiu, exa in `ALL_SOURCES` + lazy-import dispatch | PASS | `__init__.py` lines 29–31 (ALL_SOURCES), lines 85–93 (_get_collector dispatch) |
| 2 | `CREDENTIAL_SCHEMA` on each collector class | PASS | `V2exCollector` lines 140–155; `XueqiuCollector` lines 114–123; `ExaCollector` lines 93–108 |
| 3a | V2EX v2_api: available only when `v2ex_api_token` set | PASS | `V2exV2ApiBackend.is_available` returns `bool(_token(settings, db))` (v2ex.py:89); `test_v2_backend_unavailable_without_token`, `test_v2_backend_available_with_token` both PASSED |
| 3b | V2EX v1_api: always available | PASS | `V2exV1ApiBackend.is_available` returns `True` (v2ex.py:115); `test_v1_backend_always_available` PASSED |
| 3c | Xueqiu: always available (auto-guest-session) | PASS | `XueqiuCollector.is_available` returns `True` (xueqiu.py:126); `test_collector_is_always_available` PASSED |
| 3d | Exa: available only when `exa_api_key` set | PASS | `ExaCollector.is_available` returns `bool(_api_key(settings, db))` (exa.py:112); `test_unavailable_without_key`, `test_available_with_key` both PASSED |
| 4 | `collect()` returns `CollectorResult` with correct structure | PASS | All integration tests pass; V2ex via MultiBackendCollector (multi_backend.py:108); Xueqiu and Exa return CollectorResult directly |
| 5 | `dry_run=True` returns completed with empty items | PASS | V2ex: MultiBackendCollector.collect() line 77–78; Xueqiu: xueqiu.py:139–140, `test_collect_dry_run_returns_empty` PASSED; Exa: exa.py:134–136, `test_collect_dry_run_returns_empty` PASSED |
| 6 | All network mocked — no live HTTP in tests | PASS | V2ex: `patch("niche_radar.collectors.v2ex.get_json", ...)`; Xueqiu: `patch("requests.get", ...)` + `patch("...xueqiu._session", ...)`; Exa: `patch("niche_radar.collectors.exa.post_json", ...)`; zero bare `requests.get` calls outside a `patch` context |
| 7 | pytest count ≥ 434 | PASS | `434 passed` (== required 434; +33 from baseline 401) |
| 8 | `python3 -m niche_radar.eval.runner` exits 0 | PASS | Exit 0; pre-existing offline-no-LLM artifact unchanged |
| 9 | config.py has `v2ex_api_token`, `xueqiu_cookie`, `exa_api_key`, `freshness_v2ex_hours`, `freshness_xueqiu_hours` | PASS | config.py lines 45, 48, 51, 61, 62 respectively |

**Failure detail:** none.

**Round:** 1 (first independent verdict) — PASS.

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
