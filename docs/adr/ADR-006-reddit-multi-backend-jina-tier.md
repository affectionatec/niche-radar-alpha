# ADR-006: How should Reddit survive the public-JSON 403?

> **Status:** Accepted
> **Date:** 2026-06-25
> **Deciders:** Project maintainer
> **Relates to:** ADR-002 (multi-backend fallback), ADR-005 (Agent-Reach port)

## Context

The Reddit collector was a `BaseCollector` with a hand-rolled PRAW → public-JSON fallback. CI logs revealed the public-JSON path returns **HTTP 403 from datacenter IPs** (`reddit_public_query_failed`), so on cloud/CI deployments without API credentials, Reddit capture goes dark. The Agent-Reach plan (M2) suggested CLI tiers (`rdt-cli`/OpenCLI) — but OpenCLI is a desktop app (unfit for a headless pipeline) and a CLI on the same datacenter IP would be 403'd too. A relay that fetches from a different egress is what actually defeats the 403.

## Decision Drivers

- Keep Reddit alive when both PRAW (no creds) and public-JSON (403) fail.
- Reuse proven, already-verified code; no questionable external CLIs.
- Stay testable offline; no surprise outbound calls in unattended runs.
- Consistency with the resilience contract (ADR-002).

## Options Considered

### Option A: `rdt-cli` / OpenCLI tier (literal Agent-Reach recipe)

- ✅ Faithful to the plan.
- ❌ OpenCLI is desktop-only — does not fit a headless scheduled pipeline.
- ❌ A CLI on the same datacenter IP is 403'd just like public-JSON; marginal real resilience for cloud.
- ⚠️ External CLI interface can't be verified locally; risks an unfaithful contract.

### Option B: Refactor Reddit to `MultiBackendCollector` and add the existing `JinaReaderBackend` as a third tier

- ✅ Reuses the `JinaReaderBackend` already shipped and independently verified in M1.
- ✅ `r.jina.ai` fetches from a different egress, defeating the datacenter-IP 403.
- ✅ Fully offline-testable; opt-in so no surprise calls (ADR-005 pattern).
- ✅ Makes Reddit's tiering explicit (`praw → public_json → jina_reader`) under the ADR-002 contract.
- ❌ Jina returns the search page as a single document item, not per-post structure (acceptable: A1/A2 mine the text).

## Decision

**Chosen: Option B — `RedditCollector` becomes a `MultiBackendCollector` with chain `praw → public_json → jina_reader`.** OpenCLI/rdt-cli are explicitly **not** ported (desktop-only / no real 403 benefit on cloud).

### Rationale

The observed failure is an egress/IP block, not a missing tool — so the fix is a different egress (the Jina relay), not another local CLI. Reusing the verified `JinaReaderBackend` is lower-risk and higher-confidence than a CLI whose interface can't be validated here. The PRAW and public-JSON paths are preserved verbatim as backends, so existing behavior (and tests) are unchanged when credentials are present.

### Trade-offs Accepted

- The Jina tier yields coarse document items (whole search page) rather than structured per-post records — enough for pain-signal extraction, less precise than PRAW.

### Reversibility

Easy — drop `JinaReaderBackend` from `build_backends()`; the collector reverts to PRAW + public-JSON.

### Review Trigger

Re-evaluate if Reddit blocks the Jina relay too, or if a structured keyless path (authenticated OAuth without full PRAW setup) becomes preferable.

## Consequences

### Enables
- Reddit capture survives the datacenter-IP 403 when the operator opts into the Jina tier.

### Constrains
- The Jina tier is opt-in (`jina_fallback`/`jina_api_key`/`JINA_READER_ENABLED`); off by default.

### Follow-up Actions
- [x] Refactor `reddit.py` to `MultiBackendCollector`; add `RedditPrawBackend`, `RedditPublicJsonBackend`, compose `JinaReaderBackend`.
- [x] Offline tests for the tier ordering (`tests/test_collectors/test_reddit_jina.py`).

## References
- `niche_radar/collectors/reddit.py` · `niche_radar/collectors/backends/jina.py` · `docs/spec/collectors.md` §3.2 · `docs/plans/implementation-plan.md` M2
