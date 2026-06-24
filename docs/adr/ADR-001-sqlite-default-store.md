# ADR-001: Should the default datastore be SQLite or PostgreSQL?

> **Status:** Accepted
> **Date:** 2026-06-24 (records a decision made earlier in the project's life)
> **Deciders:** Project maintainer

## Context

Niche Radar is a single-user, self-hosted tool that ingests from many sources and persists raw items, pain extractions, niche candidates, and analyses. It must be trivially deployable by an indie hacker on a laptop or a small VPS, while still being able to scale to larger working sets if someone runs it hard. The datastore choice sets the deployment floor.

## Decision Drivers

- Zero-friction first run — no external service required to get a scored shortlist.
- Single-instance, single-writer workload (scheduler + API in one process).
- Optional path to more concurrency/scale without a rewrite.
- Docker Compose as the standard deployment.

## Options Considered

### Option A: SQLite as default, PostgreSQL opt-in

- ✅ Zero-dependency: ships and runs with nothing to provision.
- ✅ One file (`data/niche_radar.db`) — trivial backup/move.
- ✅ WAL mode covers the single-writer + concurrent-reader pattern.
- ❌ Weak under high write concurrency / multi-process writers.
- ⚠️ Risk: a future multi-worker design would strain it.

### Option B: PostgreSQL required

- ✅ Strong concurrency, richer types/indexes, scales further.
- ❌ Every user must provision and run a database to try the tool.
- ❌ Heavier Compose footprint for the common single-user case.

## Decision

**Chosen: Option A — SQLite as default, PostgreSQL as an opt-in Compose profile.**

### Rationale

The dominant use case is one operator on one box. Driver 1 (zero-friction first run) and the single-writer workload make SQLite's simplicity worth far more than Postgres's concurrency headroom. Keeping a `DATABASE_URL`/Compose `db` profile escape hatch means scale is available without forcing the cost on everyone.

### Trade-offs Accepted

- We give up strong multi-writer concurrency by default; a heavy-parallel future would lean on the Postgres profile.

### Reversibility

Medium — repository code targets a SQL surface; moving a deployment to Postgres is a profile flip plus schema/connection handling, not an app rewrite.

### Review Trigger

Re-evaluate if we introduce multiple concurrent writer processes, or if working sets routinely exceed comfortable single-file sizes.

## Consequences

### Enables
- `docker compose up` with no external DB; one-file persistence.

### Constrains
- Storage code must stay portable across SQLite and PostgreSQL (no SQLite-only features without a fallback).

### Follow-up Actions
- [x] PostgreSQL available via Compose `db` profile.
- [ ] Keep `docs/spec/storage.md` invariants engine-agnostic.

## References
- `docs/prd.md` §5 · `docs/ARCHITECTURE.md` (Infrastructure, Key Decisions) · `niche_radar/storage/`
