# ADR-003: One monolithic analysis prompt, or eight focused agents?

> **Status:** Accepted
> **Date:** 2026-06-24 (records a foundational design decision)
> **Deciders:** Project maintainer

## Context

The core transformation is raw item → scored niche candidate. This requires several distinct cognitive jobs: filter noise, extract structured pain, research the market, score opportunity, assess feasibility, judge go/no-go, write a PRD, write a brief. The question is whether to do this in one large prompt or as a chain of specialized agents.

## Decision Drivers

- Cost: the cheap filter (A1) should drop ~90% of noise *before* expensive downstream work runs.
- Reliability: each step should return a small, schema-validated structure.
- Graceful degradation: one step failing should not abort the whole analysis.
- Calibration: scoring and verdict need focused rubrics, not a buried sub-task.

## Options Considered

### Option A: Single monolithic prompt (raw item → full analysis)

- ✅ One call, simplest orchestration.
- ❌ No cheap early filter — pays full cost on noise.
- ❌ Large unstructured output is hard to validate and prone to drift.
- ❌ A single bad field can poison the whole result; no partial recovery.

### Option B: Eight specialized agents (A1–A8), zero-shot, structured JSON

- ✅ A1 filters cheaply before A2–A8; clustering collapses items before per-cluster A3–A8.
- ✅ Each agent has a focused Pydantic I/O model — validated, calibrated rubrics.
- ✅ Partial-failure tolerant: missing upstream values substitute "unknown," downstream still runs.
- ✅ A6 gates flow (A7 PRD only on GO).
- ❌ More orchestration; cross-agent context passing to manage.
- ⚠️ Risk: chained latency and more total calls if clustering/budget caps are absent.

## Decision

**Chosen: Option B — eight zero-shot, structured-JSON agents across four phases.**

### Rationale

The cost driver is decisive: A1 as a cheap gatekeeper plus clustering before A3–A8 is what makes the economics work (80–90% LLM-cost reduction). Focused Pydantic models give per-step validation and calibration the monolith can't, and the "null over hallucination / partial-failure tolerance" principle keeps a single bad step from killing a run.

### Trade-offs Accepted

- More orchestration complexity and context plumbing; mitigated by clustering + a per-run budget cap (`2N + 10C + 50`).

### Reversibility

Hard — the agent boundaries, Pydantic models, and DB tables (`item_pain_extractions`, `niche_analyses`) are built around this decomposition.

### Review Trigger

Re-evaluate if model context windows and pricing make a single calibrated call cheaper than the chain at equal quality.

## Consequences

### Enables
- Independent tuning per agent; graceful partial failure; clear cost controls.

### Constrains
- Agent I/O contracts (Pydantic models) are load-bearing; changes ripple downstream.

### Follow-up Actions
- [x] A1–A8 implemented under `niche_radar/agents/`.
- [ ] Keep design philosophy current in `docs/agent-pipeline.md`.

## References
- `docs/agent-pipeline.md` · `niche_radar/agents/` (pipeline, orchestrator, models, clustering) · `docs/ARCHITECTURE.md` (Clustering Strategy)
