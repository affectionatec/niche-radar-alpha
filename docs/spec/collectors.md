# Technical Specification: Collectors (Data-Source Ingestion)

> Source PRD: `docs/prd.md` §3 (P0 multi-source ingestion)
> Related ADR: ADR-002 (multi-backend fallback)
> Status: Approved
> Last updated: 2026-06-24

## 1. Overview

The collector domain fetches content from external public platforms, normalizes it into raw items, and persists them for the analysis pipeline. It covers two collector shapes: the single-path `BaseCollector` and the resilient `MultiBackendCollector` (an ordered chain of interchangeable `SourceBackend`s). This spec is the contract any new source or capture backend — including the Agent-Reach capability port (`docs/plans/implementation-plan.md`) — must satisfy.

Out of scope: how raw items are analyzed (→ `analysis-pipeline.md`), DB schema internals (→ `storage.md`).

## 2. Data Model

### 2.1 `CollectorResult` (return of every collector)

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| source | str | required, non-empty | Source name; must match a key in `ALL_SOURCES` |
| items | list[dict] | required | Normalized raw items (see 2.2) |
| run_id | str | required | Collection-run identifier |
| status | str | enum: `completed` \| `partial` \| `failed` | `partial` = some backends/items failed but ≥1 item captured |
| items_collected | int | ≥ 0, == len(unique items persisted) | Count persisted this run |
| error_message | str \| None | None unless status ≠ completed | Human-readable failure summary |
| duration_seconds | float | ≥ 0 | Wall-clock collection time |
| metadata | dict \| None | optional | Diagnostics; multi-backend collectors MUST populate `metadata['backends']` (see 2.3) |

**Invariants:**
- `status == 'failed'` ⟺ `items_collected == 0` AND every backend/path failed or was unavailable.
- `status == 'partial'` ⟹ `items_collected ≥ 1` AND at least one backend errored or returned empty.
- `error_message` is non-null whenever `status != 'completed'`.

### 2.2 Raw item (element of `items`, shape handed to `upsert_raw_item`)

A normalized dict per ingested piece of content. Required keys: a stable `source_id` (dedup key within a source), `title` and/or `body` text, `url`, and a timestamp. Deduplication is on `(source, source_id)` — re-ingesting the same item MUST NOT create a duplicate row (handled by `upsert_raw_item`). A backend that cannot produce a stable `source_id` MUST derive a deterministic one (e.g., hash of canonical URL); it MUST NOT use a random/time value.

### 2.3 `metadata['backends']` (multi-backend observability)

List of per-backend outcomes, in chain order. Each entry: `{name, available: bool, items: int, status: 'ok'|'empty'|'unavailable'|'error', error: str|null, duration_seconds: float}`. This is surfaced in the dashboard and is the evidence a verifier inspects for fallback behavior.

## 3. Collector Contracts

### 3.1 `BaseCollector` (abstract)

- `source_name: str` — non-empty.
- `CREDENTIAL_SCHEMA: list[dict]` — each `{key, label, secret, optional, help}`.
- `collect(settings, dry_run=False, db=None) -> CollectorResult` — fetch, normalize, persist (unless `dry_run`), return result.
- `is_available(db, settings) -> bool` (classmethod) — MUST NOT raise. Returns False when required credentials/binaries are absent; the runner **skips** (does not fail) unavailable sources.
- `test_connection(db, settings) -> tuple[bool, str]` (classmethod) — optional credential check.

**Rule:** `dry_run=True` MUST perform fetch but MUST NOT write to the DB.

### 3.2 `MultiBackendCollector` (extends `BaseCollector`)

- Subclass sets `source_name` and implements `build_backends() -> list[SourceBackend]` returning **priority-ordered** instances.
- `collect()` walks the chain: for each backend, if `is_available()` is True, call `fetch()`; the **first available backend returning a non-empty list wins**. On unavailable / empty / raised exception, fall through to the next.
- Per-backend outcomes recorded in `metadata['backends']`.
- If all backends are unavailable → `status='failed'`, `items_collected=0`, `error_message` names the absent prerequisites. If backends ran but none returned items → `status='failed'` with the last error, OR `completed` with 0 items only when a backend explicitly reported "available, nothing found" with no errors.

### 3.3 `SourceBackend` (one interchangeable capture path)

- `name: str` — non-empty, unique within a chain.
- `is_available(settings, db) -> bool` — MUST NOT raise; True only when this path's credentials/binaries/network prerequisites are present.
- `fetch(settings, db) -> list[dict]` — returns normalized raw items (2.2). Returns `[]` for "available but nothing found" (triggers fallthrough). MUST raise to signal failure (caught by the collector, recorded, fallthrough).

**Rule:** a backend MUST be cheap to construct (no network in `__init__`). Network/CLI work happens only in `fetch()`.

## 4. Registration

A source is live only when its key is in `niche_radar/collectors/__init__.py::ALL_SOURCES` and `_get_collector()` maps it to a collector class. Credential-gated sources stay in `ALL_SOURCES` but report `is_available() == False` until configured (the runner skips them silently).

## 5. Error Handling & Resilience

| Condition | Required behavior |
|-----------|-------------------|
| Backend prerequisites missing | `is_available()` returns False; backend skipped; recorded `status='unavailable'` |
| Backend raises | Exception caught; recorded `status='error'` with message; chain falls through |
| Backend returns `[]` | Recorded `status='empty'`; chain falls through |
| All paths exhausted, nothing captured | Collector returns `status='failed'`, non-null `error_message`; the run does NOT raise out of the runner |
| Transient network error | Backend MAY retry per `tenacity` policy; retries are internal to `fetch()` |

A single source failing MUST NOT abort the collection run for other sources.

## 6. Non-Functional Requirements

- A backend's `fetch()` MUST honor a bounded timeout (no unbounded hangs); default network timeout ≤ 30s per request.
- `is_available()` MUST be side-effect-free and fast (no network).
- New runtime dependencies (binaries like `yt-dlp`, external readers) MUST be gated by `is_available()` so their absence degrades to fallthrough, never a crash, and MUST be declared in the Dockerfile + an ADR.
- ToS/cookie-dependent or burner-account backends MUST be ordered last (last-resort only) and MUST be clearly marked in `build_backends()`.

## 7. Acceptance Criteria

> The verifier runs **Verify via** exactly as written.

### 7.1 Multi-backend fallback semantics

| # | Criterion (Given / When / Then) | Verify via | Evidence |
|---|--------------------------------|------------|----------|
| 1 | **Given** a chain `[A(unavailable), B(returns items), C]` **When** `collect()` runs **Then** B's items are returned and C is never called | `pytest tests/ -k "multi_backend"` | exit 0, fallthrough test passes |
| 2 | **Given** a backend that raises **When** `collect()` runs **Then** the exception is caught, recorded in `metadata['backends']` as `error`, and the chain falls through | `pytest tests/ -k "backend and (error or raise)"` | exit 0; asserts next backend used |
| 3 | **Given** all backends unavailable **When** `collect()` runs **Then** `status=='failed'`, `items_collected==0`, `error_message` is non-null, and the runner does not raise | `pytest tests/ -k "multi_backend and unavailable"` | exit 0 |
| 4 | **Given** `dry_run=True` **When** `collect()` runs **Then** no rows are written | `pytest tests/ -k "dry_run"` | exit 0 |

### 7.2 Whole-suite + eval gate (every collector change)

| # | Criterion | Verify via | Evidence |
|---|-----------|------------|----------|
| 5 | Full suite passes, ratchet holds | `pytest` | exit 0, count ≥ baseline (371 baseline) |
| 6 | Golden-set eval passes | `python -m niche_radar.eval.runner` | exit 0 |

## 8. Dependencies

| Dependency | Type | Failure Mode | Fallback |
|-----------|------|--------------|----------|
| `storage.upsert_raw_item` | internal | DB error | run marked failed; surfaced to runner |
| Per-source upstream APIs/CLIs | external | rate-limit / block / down | next backend in chain, then skip |
| `tenacity` | lib | — | retry policy for transient errors |

## 9. Open Questions

- Should backend ordering eventually be cost/latency-aware rather than static priority? (Deferred — ADR-002 review trigger.)
