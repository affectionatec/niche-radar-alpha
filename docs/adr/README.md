# Architecture Decision Records

Append-only log of consequential decisions. **Never edit an accepted ADR** — supersede it with a new one and update the status line. One decision per ADR.

| ADR | Decision | Status |
|-----|----------|--------|
| [ADR-001](ADR-001-sqlite-default-store.md) | SQLite default store, PostgreSQL opt-in | Accepted |
| [ADR-002](ADR-002-multi-backend-collector-fallback.md) | Ordered multi-backend fallback chain per source | Accepted |
| [ADR-003](ADR-003-eight-agent-pipeline.md) | Eight focused LLM agents over a monolithic prompt | Accepted |
| [ADR-004](ADR-004-adopt-agentic-engineering-doc-chain.md) | Adopt the agentic-engineering documentation chain | Accepted |

> Adding an ADR: copy the template from the `architecture-decision-record` skill, number sequentially (numbers are never reused), frame the title as a question, and record it at the moment of decision.
