# ADR-008: How should we add LinkedIn pain-point discovery?

> **Status:** Accepted
> **Date:** 2026-06-27
> **Deciders:** Project maintainer
> **Relates to:** ADR-002 (multi-backend fallback), ADR-006 (Jina relay pattern)

## Context

The implementation plan (M4-T2) maps Agent-Reach's LinkedIn recipe: `linkedin-mcp` (primary) with a Jina fallback. But `linkedin-mcp` is an MCP server that requires a running browser + logged-in session — it fits an interactive desktop tool, not an unattended scheduled pipeline. LinkedIn's public search API is accessible without authentication for basic queries, and the Jina Reader relay can serve as a resilience tier when that path is rate-limited or blocked.

## Decision Drivers

- Add LinkedIn to Niche Radar; keep it alive in unattended runs.
- Reuse the `MultiBackendCollector` contract (ADR-002) — every source gets an ordered fallback chain.
- No desktop tools, no cookie management, no MCP server dependency.
- Stay testable offline; opt-in for the relay tier.
- No new pip dependency.

## Options Considered

### Option A: Literal Agent-Reach recipe (linkedin-mcp → Jina fallback)

- ✅ Faithful to the plan.
- ❌ `linkedin-mcp` is an MCP server — requires a running process + browser session, incompatible with headless scheduling.
- ❌ Requires live LinkedIn login cookies — periodic refresh burden.
- ❌ Can't be verified offline.

### Option B: LinkedIn public search API only

- ✅ Keyless — no credentials needed.
- ✅ Already reachable from datacenter IPs (verified: HTTP 200).
- ❌ Single point of failure — one rate-limit or block kills the source.
- ❌ LinkedIn's anti-bot may escalate over time.

### Option C: `MultiBackendCollector` — public search → Jina Reader relay

- ✅ Reuses the `JinaReaderBackend` already shipped in M1, proven in M2-T1.
- ✅ Public search is keyless (always available); Jina is opt-in for resilience.
- ✅ Fully offline-testable; zero new dependencies.
- ✅ Consistent with the ADR-002/ADR-006 resilience contract.
- ❌ Jina returns results as a single document item per query.

## Decision

**Chosen: Option C — `MultiBackendCollector` with chain `public_search → jina_reader`.** The public search is the primary (always available, keyless); the Jina Reader serves as opt-in resilience when the public path is rate-limited or blocked.

`linkedin-mcp` is explicitly **not** ported — it is a desktop/interactive tool that violates the unattended pipeline constraint (same reasoning as ADR-006, ADR-007).

## Consequences

- **Pros:** LinkedIn pain-point signals become available with no credentials, no new deps, full offline testability. The Jina tier provides a resilience path if LinkedIn tightens anti-bot measures.
- **Cons:** One document item per search query for the Jina tier; public search may return fewer results than an authenticated session.
- **Risk:** Low — LinkedIn public search is keyless and verified reachable from datacenter IPs. The Jina tier provides defense in depth.
- **Future:** If richer per-post data is ever needed, a cookie-based backend could be added as a last-resort tier (lowest priority, clearly marked ToS-risk), inserted below `public_search` and above `jina_reader` in the chain.
