# ADR-002: How should a data source survive one capture path breaking?

> **Status:** Accepted
> **Date:** 2026-06-24 (records the pattern introduced with the X/last30days work)
> **Deciders:** Project maintainer

## Context

Public-platform capture is the most fragile part of the pipeline: APIs change, keys expire, scraping gets Cloudflare-blocked, cookies rot. The original X/Twitter collector was a single capture path — when it broke, the whole source went dark and the day's signal from that platform was lost. Many sources share this fragility (Google Trends, Product Hunt, App/Play Store, G2, Indie Hackers).

## Decision Drivers

- One backend failing must not take a source offline.
- Adding or reordering capture paths should not require rewriting a collector.
- Credential/binary availability differs per environment — unavailable paths must be skipped, not errored.
- Per-backend outcomes must be observable in the dashboard.

## Options Considered

### Option A: One best-effort capture path per source

- ✅ Simplest code.
- ❌ Single point of failure; a broken path = a dead source.
- ❌ Swapping providers means editing the collector's core logic.

### Option B: Ordered multi-backend fallback chain (`MultiBackendCollector` + `SourceBackend`)

- ✅ Walks an ordered list; first *available* backend that returns items wins; falls through on unavailable/empty/error.
- ✅ "Switch capture path = reorder the list," not rewrite code.
- ✅ Per-backend results recorded in `CollectorResult.metadata['backends']` for observability.
- ❌ More moving parts; each backend needs an `is_available()` + `fetch()`.
- ⚠️ Risk: a misordered chain can mask a cheap/reliable path behind a slow one.

## Decision

**Chosen: Option B — an availability-gated, priority-ordered fallback chain.**

### Rationale

Resilience is the property that makes a public-source pipeline trustworthy (Driver 1). The `SourceBackend` ABC turns capture paths into interchangeable units, so hardening a source or adding a provider is an additive change (Driver 2), and `is_available()` lets credential-gated paths stay silent until configured (Driver 3). The X collector (xAI → Xquik → cookie GraphQL) proved the pattern; it generalizes to any source.

### Trade-offs Accepted

- More structure per source; chain ordering becomes a design decision worth getting right.

### Reversibility

Easy — a source can run a single backend by giving it a one-element chain.

### Review Trigger

Re-evaluate the ordering heuristic if backends gain cost/latency metadata that should drive selection dynamically rather than by static priority.

## Consequences

### Enables
- Per-source resilience; clean seam to port external capability recipes (e.g., Agent-Reach: Jina Reader, yt-dlp, rdt-cli) as new backends without touching collector logic — the basis of `docs/plans/implementation-plan.md`.

### Constrains
- Every backend must implement `is_available()`/`fetch()` and must not raise from `is_available()`.

### Follow-up Actions
- [x] `MultiBackendCollector` + `SourceBackend` in `niche_radar/collectors/multi_backend.py`.
- [ ] Migrate remaining single-path fragile sources onto chains (see IMPL PLAN).

## References
- `niche_radar/collectors/multi_backend.py` · `niche_radar/collectors/x_backends/` · `docs/spec/collectors.md`
