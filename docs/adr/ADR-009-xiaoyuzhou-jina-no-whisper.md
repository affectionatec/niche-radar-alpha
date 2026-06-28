# ADR-009: How should we add 小宇宙 (Xiaoyuzhou) podcast discovery?

> **Status:** Accepted
> **Date:** 2026-06-28
> **Deciders:** Project maintainer
> **Relates to:** ADR-006 (Jina relay pattern), ADR-007 (XHS Jina relay)

## Context

The implementation plan (M3-T5) maps Agent-Reach's 小宇宙 recipe: download podcast audio and transcribe with Whisper. But:

1. Whisper is a heavy dependency (~2 GB model, `ffmpeg`, significant compute) — it violates the project's "no new deps without an ADR" and "keep the pipeline unattended" constraints.
2. 小宇宙 (xiaoyuzhoufm.com) is a JS-rendered SPA with no public API (verified: homepage returns a 27 KB JS shell; API endpoints return 404/500). Direct HTML scraping is useless.
3. The Jina Reader relay pattern (ADR-006, ADR-007) has been proven three times to extract content from JS-heavy sites without audio infrastructure: Jina renders JS and returns clean Markdown.
4. 小宇宙 episode pages contain show notes, episode descriptions, and titles — text content that is immediately useful for pain-point mining without audio transcription.

## Decision Drivers

- Add 小宇宙 to Niche Radar without introducing a heavyweight Whisper dependency.
- Reuse the proven Jina Reader relay pattern — consistent, testable, zero new deps.
- Capture podcast metadata (title, description, show notes) as raw items — sufficient for A1/A2 text mining.
- Keep the door open for audio transcription as a future optional enhancement.

## Options Considered

### Option A: Literal Agent-Reach recipe (download audio → Whisper transcription)

- ✅ Faithful to the plan.
- ❌ Heavy deps: `openai-whisper` (~2 GB model) + `ffmpeg` + audio storage.
- ❌ High per-episode cost (download + GPU/CPU inference minutes).
- ❌ Pipeline becomes stateful (audio files, transcription queues).
- ❌ Can't be verified offline with full fidelity.

### Option B: Hosted transcription API (Deepgram / AssemblyAI)

- ✅ No local model — API call only.
- ❌ Adds a paid external dependency (per-minute pricing).
- ❌ Still requires audio download + storage.
- ❌ Can't be verified offline (must call the API in tests or mock complex response shapes).
- ⚠️ Cost at pipeline scale: 20 episodes × 30 min each = 600 min / month ≈ $3–$15/month.

### Option C: Jina Reader relay — scrape episode pages (no audio)

- ✅ Reuses the `JinaReaderBackend` already shipped (M1) and independently verified (M1, M2, M4).
- ✅ Zero new dependencies; fully offline-testable.
- ✅ Captures show notes, episode titles, and descriptions — text content that A1/A2 can mine.
- ✅ `r.jina.ai` renders JS, solving the SPA problem (same as Reddit, XHS).
- ✅ Consistent with the ADR-002/ADR-006/ADR-007 resilience contract.
- ❌ Misses spoken content not in show notes (mitigated: Chinese podcast show notes are often detailed; pain-point phrases surface in titles/descriptions).

### Option D: Jina Reader primary, Whisper as optional future backend

- ✅ Inherits all Option C pros.
- ✅ Whisper can be added later as a `SourceBackend` (inserted above Jina in the chain).
- ❌ Requires someone to actually build the Whisper backend later (but we don't block current progress on it).

## Decision

**Chosen: Option D — Jina Reader now, Whisper deferred.** The collector is a `MultiBackendCollector` with a single composed `JinaReaderBackend` that reads 小宇宙 search result pages and podcast episode pages through r.jina.ai. Whisper transcription is explicitly deferred — it can be added as a `SourceBackend` later without refactoring the collector.

### Rationale

The Jina Reader pattern is this project's proven answer to "JS SPA with no public API." It has been independently verified across three milestones. Adding 小宇宙 with the same mechanism is low-risk, adds immediate signal, and costs nothing in new dependencies. Audio transcription is a separate concern — valuable, but not essential for the initial signal capture, and not worth blocking M3 completion.

## Consequences

- **Pros:** 小宇宙 podcast metadata becomes available with zero new deps, full offline testability, consistent with the established resilience pattern. The collector is built and verified today.
- **Cons:** Spoken audio content not captured. Show notes vary in quality — some episodes have minimal text. Jina renders one document item per URL visited.
- **Risk:** Low — the Jina relay pattern is mature (3 prior verified integrations). 小宇宙 anti-bot may escalate but the relay egress handles that (ADR-006).
- **Future:** Adding a Whisper or hosted-transcription backend is a separate task — insert a new `SourceBackend` above `JinaReaderBackend` in the chain, no collector refactoring needed.
