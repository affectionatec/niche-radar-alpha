# Technical Specification: Storage (Schema & Retention)

> Source PRD: `docs/prd.md` §5
> Related ADR: ADR-001 (SQLite default / PostgreSQL opt-in)
> Status: Draft — consolidating. Schema is authoritative in `niche_radar/storage/` + `docs/spec.md` §5; this spec hardens invariants incrementally.
> Last updated: 2026-06-24

## 1. Overview

Persistence for the whole pipeline. SQLite default (`data/niche_radar.db`, WAL mode); PostgreSQL opt-in via Compose `db` profile (ADR-001). Storage code MUST stay engine-portable — no SQLite-only feature without a fallback.

## 2. Core Tables & Flow

```
collection_runs → raw_items → item_pain_extractions (A1+A2)
                                   → niche_item_links → niche_candidates → niche_analyses (A3–A8)
```

Plus: `shortlist_notes` (user curation), `app_settings` (settings + LLM config), `pipeline_jobs` (job persistence). Full column detail in `docs/spec.md` §5 / `docs/ARCHITECTURE.md` (Data Model).

## 3. Invariants (must hold)

- `raw_items` deduplicate on `(source, source_id)` — re-ingest MUST upsert, never duplicate.
- `niche_candidates.llm_score` ∈ [0, 100]; `momentum_label` ∈ {growing, stable, declining}.
- A `niche_candidate` derives from ≥1 `raw_item` via `niche_item_links`.
- Retention cleanup (`storage/cleanup.py`) removes rows older than the configured window; it MUST NOT delete shortlisted niches.
- Secrets in `app_settings` (LLM key) MUST NOT be returned verbatim by the API (→ `api.md` §3).

## 4. Acceptance Criteria

| # | Criterion | Verify via | Evidence |
|---|-----------|------------|----------|
| 1 | Storage/repository tests pass | `pytest tests/ -k "storage or repository"` | exit 0 |
| 2 | Dedup on `(source, source_id)` holds | `pytest tests/ -k dedup` | exit 0 |
| 3 | Retention preserves shortlisted niches | `pytest tests/ -k "cleanup or retention"` | exit 0 |

## 5. Open Questions

- Mirror the full `docs/spec.md` §5 column tables here as decomposition continues.
