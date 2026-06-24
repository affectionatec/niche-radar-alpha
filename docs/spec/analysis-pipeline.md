# Technical Specification: Analysis Pipeline (A1–A8 + Clustering)

> Source PRD: `docs/prd.md` §3 (P0 8-agent pipeline)
> Related ADR: ADR-003 (eight-agent pipeline)
> Status: Draft — consolidating. Authoritative design detail currently lives in `docs/agent-pipeline.md` and `docs/spec.md` §4; this spec hardens it into contracts incrementally.
> Last updated: 2026-06-24

## 1. Overview

Transforms `raw_items` into scored `niche_candidates`. Four phases: **A** (per item: A1 Signal Filter → A2 Pain Extractor), **B** (clustering: Jaccard + LLM refinement), **C** (per cluster: A3 Market Researcher → A4 Opportunity Scorer → A5 Feasibility Analyst → A6 Go/No-Go Judge → A7 PRD Writer [GO only] → A8 Brief Creator), **D** (persist). Entry: `niche_radar/agents/pipeline.py::run_analysis`.

## 2. Agent I/O Contracts

Each agent has a Pydantic input/output model in `niche_radar/agents/models.py` (A1Output … A8Output). Contracts (full field lists in `docs/agent-pipeline.md`):

- **A1** → binary classification + confidence (0.0–1.0) + signal type ∈ {pain_point, feature_request, competitor_complaint, noise}. Biased to precision; drops ~90% of noise before A2.
- **A2** → structured pain profile (who/what/when/current_workaround/why_current_sucks/desired_outcome) + emotional_intensity (1–10) + 3–5 clustering keywords.
- **A3** → competitor list, market leader, gap, TAM (with uncertainty), saturation (1–10).
- **A4** → 7 calibrated dimensions (1–10) → weighted 0–100 composite; strengths/risks/comparables. Weights per `docs/agent-pipeline.md` (willingness-to-pay highest at 2.0).
- **A5** → feasibility_score (1–10), solo_buildable bool, MVP scope + explicit out-of-scope, build_complexity (1–5).
- **A6** → verdict ∈ {GO, NO-GO, PIVOT} + killer risk + conditions_to_reconsider. Controls flow: A7 runs only on GO.
- **A7** (GO only) → lean PRD. **A8** (always) → 60-second brief.

**Design invariants (must hold):** structured JSON only; null over hallucination; calibrated scoring (9–10 rare); partial-failure tolerance (missing upstream → "unknown" substituted, downstream still runs).

## 3. Clustering (Phase B)

Per `docs/ARCHITECTURE.md` (Clustering Strategy):
- Step 1 — Jaccard pre-grouping (deterministic, no LLM): keyword sets from A2 (fallback A1 tokens) → trivial stemmer → Union-Find merge where Jaccard ≥ `JACCARD_THRESHOLD` (default 0.5).
- Step 2 — LLM refinement only for pre-clusters ≥ `LLM_REFINE_MIN_SIZE` (default 4), chunked at `LLM_MAX_ITEMS_PER_CALL` (default 40), temperature `LLM_TEMPERATURE` (default 0.2). Orphans → "leftover" cluster (never lose items).
- Failure modes: refinement failure / bad JSON / no keywords → documented fallbacks (single cluster or token extraction).

## 4. Cost Control (must hold)

- A1 filters before A2–A8; clustering collapses items before A3–A8.
- Per-run LLM budget bounded by `2N + 10C + 50` (N = items passing A1, C = clusters). The pipeline MUST NOT exceed the cap; overflow is truncated/deferred, not silently spent.

## 5. Acceptance Criteria

| # | Criterion | Verify via | Evidence |
|---|-----------|------------|----------|
| 1 | Agent contracts validate (A1–A8 models) | `pytest tests/test_agents -v` | exit 0 |
| 2 | Clustering groups/leftover behavior holds | `pytest tests/ -k cluster` | exit 0 |
| 3 | Golden-set eval passes (calibration regression gate) | `python -m niche_radar.eval.runner` | exit 0 |
| 4 | Partial-failure tolerance: a failing upstream agent does not abort downstream | `pytest tests/ -k "partial or failure"` | exit 0 |

## 6. Open Questions

- Decompose remaining `docs/spec.md` §4 detail (validation/scoring rubric tables) into this spec. (Tracked under ADR-004 follow-ups.)
