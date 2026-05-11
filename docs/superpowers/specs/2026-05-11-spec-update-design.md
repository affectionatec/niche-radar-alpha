# Spec Update Design — Niche Radar Alpha

**Date:** 2026-05-11
**Scope:** Comprehensive polish of `spec.md` to make it implementation-ready

## Problem

The current spec covers the right high-level concepts (5 data sources, scoring engine, deployment) but has gaps that would force an implementer to make undocumented decisions:

1. **NLP pipeline is undefined** — How do `raw_items` become `niche_candidates`? This is the core intelligence and it's barely specified.
2. **No error handling strategy** — What happens when Reddit API is down? Rate limited? Returns garbage?
3. **No rate limiting policy** — No guidance on respecting API limits or avoiding bans.
4. **No testing strategy** — No approach for verifying collectors, scoring, or reports.
5. **No data retention policy** — Database grows unbounded.
6. **No CLI interface spec** — What commands does the user actually type?
7. **No logging/observability** — No way to know what the system is doing.
8. **Milestones lack acceptance criteria** — "Implement collectors" isn't verifiable.

## Approach: Comprehensive Polish (Approach B)

Enhance existing sections with implementation-ready detail AND add missing operational sections. The spec stays as one document (appropriate for an MVP) but becomes a true implementation guide.

**Not chosen:**
- *Surgical gap-fill (A):* Too shallow — existing sections also need precision upgrades.
- *Spec decomposition (C):* Overkill for an MVP with one developer.

## Changes Summary

### New Sections
| Section | Purpose |
|---------|---------|
| 3.2 NLP & Keyword Extraction Pipeline | How raw data becomes niche candidates |
| 8. CLI Interface | Exact commands and flags |
| 13. Testing Strategy | Unit/integration/E2E test plan |
| 14. Logging & Observability | Structured logging, error alerting |

### Enhanced Existing Sections
| Section | Enhancement |
|---------|-------------|
| 2.x Data Sources | Add error handling notes, rate limit info per source |
| 5. Data Model | Add indexes, add `collection_runs` table |
| 6. Deployment | Add subsections for error handling, rate limiting, data retention |
| 7. Configuration | Add new env vars (retry, retention, log level) |
| 10. Tech Stack | Add `structlog`, `tenacity` |
| 11. MVP Milestones | Add acceptance criteria per phase |

## Assumptions (user unavailable)
- User wants a comprehensive improvement, not a directional change
- All 5 data sources remain the same
- Scoring weights remain the same
- SQLite-first, PostgreSQL-optional approach stays
