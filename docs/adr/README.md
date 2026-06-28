# Architecture Decision Records

Append-only log of consequential decisions. **Never edit an accepted ADR** — supersede it with a new one and update the status line. One decision per ADR.

| ADR | Decision | Status |
|-----|----------|--------|
| [ADR-001](ADR-001-sqlite-default-store.md) | SQLite default store, PostgreSQL opt-in | Accepted |
| [ADR-002](ADR-002-multi-backend-collector-fallback.md) | Ordered multi-backend fallback chain per source | Accepted |
| [ADR-003](ADR-003-eight-agent-pipeline.md) | Eight focused LLM agents over a monolithic prompt | Accepted |
| [ADR-004](ADR-004-adopt-agentic-engineering-doc-chain.md) | Adopt the agentic-engineering documentation chain | Accepted |
| [ADR-005](ADR-005-yt-dlp-youtube-transcripts.md) | yt-dlp as the preferred YouTube backend (transcripts, keyless) | Accepted |
| [ADR-006](ADR-006-reddit-multi-backend-jina-tier.md) | Reddit multi-backend with a Jina relay tier (not rdt-cli/OpenCLI) | Accepted |
| [ADR-007](ADR-007-xiaohongshu-jina-tier.md) | 小红书 Jina Reader relay (not OpenCLI/xhs-cli) | Accepted |
| [ADR-008](ADR-008-linkedin-public-jina-tier.md) | LinkedIn public search → Jina relay (not linkedin-mcp) | Accepted |
| [ADR-009](ADR-009-xiaoyuzhou-jina-no-whisper.md) | 小宇宙 Jina Reader relay (defer Whisper) | Accepted |

> Adding an ADR: copy the template from the `architecture-decision-record` skill, number sequentially (numbers are never reused), frame the title as a question, and record it at the moment of decision.
