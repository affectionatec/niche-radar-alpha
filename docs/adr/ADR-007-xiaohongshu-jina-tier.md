# ADR-007: How should we add 小红书 (XiaoHongShu) pain-point discovery?

> **Status:** Accepted
> **Date:** 2026-06-27
> **Deciders:** Project maintainer
> **Relates to:** ADR-002 (multi-backend fallback), ADR-006 (Jina relay pattern)

## Context

The implementation plan (M4-T1) maps Agent-Reach's 小红书 recipe: `OpenCLI/xiaohongshu-mcp/xhs-cli` backends. But Agent-Reach is an interactive desktop tool — OpenCLI is a desktop app, xiaohongshu-mcp is an MCP server (requires a running process + browser cookie), and xhs-cli is a CLI wrapper around login cookies. None of these fit an unattended scheduled pipeline. ADR-006 already established that a Jina Reader relay defeats datacenter-IP blocks by fetching from a different egress — the same pattern applies here.

The China social-media branch (`feature/china-social-media`) has a TikHub API-based implementation (paid third-party). TikHub works but couples the project to a paid external API with credit constraints, and it didn't use the `MultiBackendCollector` contract.

## Decision Drivers

- Add 小红书 to Niche Radar; keep it alive in unattended runs.
- Reuse proven patterns (ADR-002, ADR-006) — no desktop tools, no questionable CLIs.
- Stay testable offline, opt-in for any outbound relay calls.
- No new pip dependency.
- No cookie management burden on the user.

## Options Considered

### Option A: Literal Agent-Reach recipe (OpenCLI / xiaohongshu-mcp / xhs-cli)

- ✅ Faithful to the plan.
- ❌ OpenCLI is desktop-only — does not fit a headless scheduled pipeline.
- ❌ xiaohongshu-mcp requires a running MCP server + browser cookie — non-portable.
- ❌ xhs-cli wraps the same cookie session — requires periodic cookie refresh.
- ❌ Can't be verified offline.

### Option B: TikHub API (paid third-party)

- ✅ Already implemented on the `feature/china-social-media` branch.
- ✅ Structured JSON responses with per-note metadata.
- ❌ Paid API with credit limits — silent failure when credits run out.
- ❌ New runtime dependency (`httpx`) — conflicts with existing `requests`-based HTTP layer.
- ❌ TikHub could change pricing/availability independently.

### Option C: Jina Reader relay (ADR-006 pattern) — read XHS search pages through the relay

- ✅ Reuses the `JinaReaderBackend` already shipped in M1 and proven in M2-T1.
- ✅ `r.jina.ai` fetches from a different egress, defeating any geo/IP blocks.
- ✅ Fully offline-testable; opt-in so no surprise calls.
- ✅ Zero new dependencies, consistent with the existing resilience contract.
- ✅ No cookie management — the relay handles rendering.
- ❌ Jina returns the search page as one document item, not per-note structure (acceptable: A1/A2 mine the text).
- ⚠️ 小红书's web search may require JS rendering — Jina Reader renders JS, so this is covered.

## Decision

**Chosen: Option C — Jina Reader relay reading 小红书 search result pages.** The collector is a `BaseCollector` with a single Jina Reader backend (opt-in, gated by `JINA_READER_ENABLED` or cred). If TikHub support is ever added, it can be inserted as a second backend via `MultiBackendCollector`.

### Rationale

The Jina Reader pattern is the project's proven answer to "can't reach this page from a datacenter." It has been independently verified twice (M1 G2/IH, M2 Reddit). Adding 小红书 with the same mechanism is low-risk and consistent.

OpenCLI/xiaohongshu-mcp/xhs-cli are explicitly **not** ported — they are desktop/interactive tools that violate the unattended pipeline constraint, just as OpenCLI/rdt-cli was rejected for Reddit (ADR-006).

## Consequences

- **Pros:** 小红书 pain-point signals become available with no new deps, no cookie burden, full offline testability.
- **Cons:** One document item per search query (not per-note richness); opt-in only (off by default).
- **Risk:** Medium — 小红书's anti-bot may escalate against r.jina.ai egress. Mitigation: the collector is opt-in and fails gracefully (chain returns partial/failed rather than crashing).
- **Future:** If per-note metadata becomes necessary, a TikHub backend (like the `feature/china-social-media` branch) can be added as a higher-priority tier via `MultiBackendCollector` without rewriting anything.
