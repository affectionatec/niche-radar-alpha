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

## 2026-06-24 — Baseline established (pre-port)

> Not a task verdict — the reference point future verdicts ratchet against.

**Baseline suite:** 371 test functions across 44 files (`grep -rhoE "def test_" tests/ | wc -l` = 371; `find tests -name 'test_*.py' | wc -l` = 44).
**CI gate:** `pytest --tb=short` + `python -m niche_radar.eval.runner` (`.github/workflows/ci.yml`).
**Note:** The documentation-chain migration (PR #1) is documentation-only — no `niche_radar/` code changed — so the suite count is unchanged from this baseline. The first feature task (M1-T1) is the first entry that will carry a full PASS/FAIL verdict with executed commands.
