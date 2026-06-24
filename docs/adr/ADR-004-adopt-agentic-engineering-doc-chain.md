# ADR-004: Should the project standardize on the agentic-engineering documentation chain?

> **Status:** Accepted
> **Date:** 2026-06-24
> **Deciders:** Project maintainer

## Context

The repo accumulated several overlapping documentation/workflow systems: a domain glossary (`CONTEXT.md`), product/architecture docs (`docs/PRODUCT.md`, `docs/ARCHITECTURE.md`), a monolithic MVP spec (`docs/spec.md`), an agent-design doc confusingly named `docs/AGENTS.md`, Superpowers plans/specs (`docs/superpowers/`), and a Ralph autonomous-loop PRD (`.ralph/prd.json`). There was **no root `AGENTS.md` single source of truth, no ADR log, no live status/crash-recovery tracker, and no independent verification record** — the distinctive pieces of the agentic-engineering chain. `copilot-instructions.md` even referenced `docs/adr/` "if present," but it never existed.

## Decision Drivers

- One unambiguous entry point every tool (Claude, Copilot, Cursor, Codex) reads first.
- Persistent memory across sessions + crash recovery for long, loop-driven work.
- "Done" as an independently verified verdict, not a producer's claim.
- A git contract: one task → one branch → one draft PR carrying its done condition.
- Preserve, not discard, the existing useful docs.

## Options Considered

### Option A: Keep the ad-hoc mix (Superpowers + Ralph + scattered docs)

- ✅ No migration work.
- ❌ No single door; tool configs drift.
- ❌ No ADRs, no status memory, no verification gate — the gaps that bite long sessions.

### Option B: Adopt the agentic-engineering chain as canonical; absorb existing docs

- ✅ Root `AGENTS.md` door + PRD → SPEC → ADR → IMPL PLAN → STATUS → VERIFICATION LOG.
- ✅ Existing docs absorbed as PRD/spec/reference inputs rather than thrown away.
- ✅ Independent-verification gate + git-workflow contract.
- ❌ Up-front migration effort; two doc systems coexist briefly during transition.
- ⚠️ Risk: drift if the chain isn't actually used after setup.

## Decision

**Chosen: Option B — agentic-engineering chain is the canonical workflow; legacy docs are absorbed and referenced.**

### Rationale

The missing pieces (single door, ADRs, status/crash-recovery, independent verification) are exactly what makes multi-session, loop-driven work on this codebase sustainable. The existing docs are good *content* but not a *workflow*; the chain provides the workflow and consumes the content. Superpowers/Ralph remain on disk as historical record.

### Trade-offs Accepted

- Temporary duplication: `docs/spec.md` (monolith) coexists with `docs/spec/` (bounded contexts) until decomposition completes; `.ralph/` and `docs/superpowers/` stay as legacy.

### Reversibility

Easy — the chain is additive Markdown; nothing in the code depends on it.

### Review Trigger

Re-evaluate if the chain documents go stale (status not updated across sessions) — that signals the workflow isn't being followed and should be fixed or abandoned, not left to rot.

## Consequences

### Enables
- Consistent agent onboarding; auditable decisions; resumable sessions; verifier-gated merges.

### Constrains
- Every session must read/update `docs/status.md`; every architectural choice needs an ADR; `main` is read-only for agents.

### Follow-up Actions
- [x] Create root `AGENTS.md`; point `CLAUDE.md` + `.github/copilot-instructions.md` at it.
- [x] Rename `docs/AGENTS.md` → `docs/agent-pipeline.md` (name collision with the door).
- [x] Seed `docs/prd.md`, `docs/spec/`, `docs/adr/`, `docs/plans/implementation-plan.md`, `docs/status.md`, `docs/verification-log.md`.
- [ ] Decompose `docs/spec.md` into `docs/spec/*` incrementally.
- [ ] Retire `.ralph/` and `docs/superpowers/` once their open items are absorbed (defer; non-blocking).

## References
- `AGENTS.md` · `docs/status.md` · the agentic-engineering skill suite (agents-md-template, technical-specification, architecture-decision-record, implementation-plan, status-tracker, independent-verification, git-workflow)
