# ADR-005: How should YouTube be captured — Data API, or yt-dlp?

> **Status:** Accepted
> **Date:** 2026-06-24
> **Deciders:** Project maintainer
> **Relates to:** ADR-002 (multi-backend fallback)

## Context

The YouTube collector ran on the Data API v3 (with a scrapetube fallback). Two limits hurt signal quality: the Data API has a hard daily **quota** (and needs a key), and it returns only a **truncated description snippet** — no transcript. Video transcripts are the richest pain signal YouTube offers (creators narrate the exact problem), and they were being left on the floor. This is the first capability ported from Agent-Reach (`docs/plans/implementation-plan.md`, M1-T3), which recommends `yt-dlp` for YouTube.

## Decision Drivers

- Capture full descriptions + transcripts, not just a snippet.
- Remove the Data-API quota/key as a hard dependency (keyless capture).
- Keep the existing API/scrape path working where the new tool is unavailable (ADR-002).
- Hermetic tests — no live network/CLI in CI.

## Options Considered

### Option A: Keep Data API v3 (+ scrapetube) only

- ✅ No new dependency.
- ❌ Daily quota; needs a key for the reliable path.
- ❌ Snippet only — no transcript, the highest-value signal.

### Option B: Add `yt-dlp` as a backend, preferred when present; keep API/scrape as fallback

- ✅ Keyless; no Data-API quota.
- ✅ Full description + auto-caption transcripts folded into the item body.
- ✅ Slots cleanly behind `MultiBackendCollector` (ADR-002): `yt_dlp → youtube_api_scrape`.
- ✅ Installed via `pip` (`requirements.txt`/`pyproject.toml`) — the console script lands on PATH, so the existing Dockerfile `pip install` already provisions it; no apt step.
- ❌ New runtime dependency; AGENTS.md §5 requires recording it (this ADR).
- ⚠️ Per-video transcript fetch is a subprocess — cost is bounded (`max_transcripts` cap, `is_available()` gate, best-effort fail-soft to "").

### Option C: youtube-transcript-api / direct caption scraping

- ✅ Lighter for transcripts specifically.
- ❌ A second tool alongside yt-dlp; less robust as YouTube changes; not the Agent-Reach recipe.

## Decision

**Chosen: Option B — add `yt-dlp` as the preferred YouTube backend; Data API/scrapetube remains the fallback.**

### Rationale

Transcripts + keyless capture (Drivers 1–2) are exactly what the Data API can't give. Expressing it as a `SourceBackend` keeps the resilience contract (Driver 3): when the `yt-dlp` binary is absent, `is_available()` is False and the chain falls through to the unchanged API/scrape path. The subprocess seams are module-level so tests mock them and stay offline (Driver 4).

### Trade-offs Accepted

- One new dependency (`yt-dlp`) and per-video transcript subprocess cost — bounded by a transcript cap and the availability gate.

### Reversibility

Easy — drop `YtDlpBackend` from `build_backends()` and the collector reverts to the prior path; remove the dependency line.

### Review Trigger

Re-evaluate if `yt-dlp` becomes unreliable/blocked at scale, or if a lighter transcript path is needed.

## Consequences

### Enables
- Transcript-bearing, keyless YouTube capture; richer A1/A2 input.

### Constrains
- `yt-dlp` is now a runtime dependency; transcript fetching must stay bounded and fail-soft.

### Follow-up Actions
- [x] Add `yt-dlp` to `requirements.txt` + `pyproject.toml` (Dockerfile installs it via pip).
- [x] `YtDlpBackend` + `youtube.py` multi-backend refactor + offline tests.
- [ ] Consider surfacing `has_transcript` in the dashboard.

## References
- `niche_radar/collectors/backends/ytdlp.py` · `niche_radar/collectors/youtube.py` · `docs/spec/collectors.md` §3.2, §6 · `docs/plans/implementation-plan.md` M1-T3
