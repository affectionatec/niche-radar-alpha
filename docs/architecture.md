# Architecture

## Current system

Niche Radar is a single-operator, self-hosted batch pipeline. Python 3.11+
collects public content and runs structured LLM analysis. FastAPI/Uvicorn serves
the API on port 8000; Next.js 15 serves the dashboard on port 3000. SWR fetches
through the same-origin Next API proxy. Docker Compose runs both services.

```text
Public APIs / scrapers / opt-in relays
  → Collectors → raw_items → A1 signal filter → A2 pain extraction
  → Jaccard + optional LLM clustering → A3–A8 analysis
  → niche_candidates + niche_analyses → API / dashboard / Markdown reports
```

The scheduler embeds APScheduler and Uvicorn in one process. Defaults are
collection every four hours, analysis plus report every six hours, and daily
cleanup. It also schedules weekly digests, entity extraction, and entity velocity
updates. Settings are defined in `niche_radar/config.py`; they load environment
variables and optional `.env`. Runtime LLM/source settings live in SQLite.

## Collector boundaries

`BaseCollector` and `CollectorResult` live in `collectors/base.py`. Register a
new source in `collectors/__init__.py` through `ALL_SOURCES` and its dispatch,
and declare its `CREDENTIAL_SCHEMA` for the settings UI.

`CollectorResult` carries source, normalized items, run ID, status, item count,
error message, duration, and optional diagnostics. Raw Items carry stable
`source_id`, title/body, URL, `posted_at`, and optional source-specific metadata.
The unique `(source, source_id)` index makes repeated ingestion an upsert.
Use deterministic IDs, never time/random IDs for the same upstream item.

`MultiBackendCollector` walks ordered `SourceBackend` instances. Unavailable,
empty, or errored paths fall through; the first nonempty result wins. Exceptions
are logged and backend outcomes are exposed in `metadata["backends"]` with `active_backend`. Availability checks must not raise or
perform network work. Construct backends cheaply and bound request timeouts.
One source failing should not abort collection of the others.

Current implementation details matter: multi-backend `dry_run=True` returns an
empty completed result without fetching. Exhausting available paths yields
`partial` with zero items; having no available path yields `failed`. Successful
fallback can return `completed` with earlier errors in `error_message`.

Important capture paths:

- YouTube: `yt_dlp` before `youtube_api_scrape`; transcript enrichment is bounded
  and best-effort, with full descriptions/transcripts folded into body text.
- Reddit: `praw` → `public_json` → opt-in `jina_reader`. A relay can change the
  egress IP; another CLI on the same blocked host cannot.
- G2 and Indie Hackers: direct scraping followed by opt-in Jina Reader.
- LinkedIn: public search followed by opt-in Jina Reader; public HTML may be thin.
- Xiaohongshu and Xiaoyuzhou: opt-in Jina Reader. Xiaoyuzhou collects titles,
  descriptions, and show notes; no audio download or Whisper infrastructure.

Jina is enabled through `JINA_READER_ENABLED` or per-source Jina credentials.
Optional integrations also include Exa, ScrapeCreators, source API keys, and
cookie-based backends. Keep account/cookie paths explicit and last-resort.

## Analysis and cost

`analysis/analyzer.py` selects clients and invokes `agents/pipeline.py`.
`llm/base.py` defines `LLMClient.complete`, `complete_json`, and
`complete_structured`; OpenAI-compatible and Anthropic clients implement it.
Prompt overrides live in `prompt_packs/`. Agent schemas are in `agents/models.py`.

| Phase | Behavior |
|---|---|
| A, per item | A1 classifies signal/noise; accepted items go to A2 structured pain extraction. |
| B | Jaccard keyword pre-grouping, then optional LLM refinement of larger groups. |
| C, per cluster | A3 market research, A4 opportunity scoring, A5 feasibility, A6 GO/NO-GO/PIVOT, A7 PRD only for GO, A8 brief. |
| D | Persist Niche Candidates, links to Raw Items, and full analysis outputs. |

Structured JSON is validated with Pydantic. Missing upstream results remain
explicit rather than invented; agent failures are recorded in `failed_agents`.
The current implementation still aggregates A2 cluster members field by field
in `agents/aggregate.py`. Item count does not establish independent demand.

Clustering uses Union-Find on stemmed keyword sets. Defaults, with environment
overrides, are Jaccard threshold 0.5 (`NR_JACCARD_THRESHOLD`), minimum LLM group
size 4 (`NR_CLUSTER_LLM_MIN_SIZE`), 40 items per refinement call
(`NR_CLUSTER_LLM_MAX_ITEMS`), and temperature 0.2 (`NR_CLUSTER_LLM_TEMP`).
Failed refinement falls back to the original group; omitted items become leftovers.

`BudgetTracker.for_run(N, C)` computes `2*N + 10*max(C, 1) + 50`, where N is
input item count. It limits calls, not tokens or currency. Budget handling has
exceptions in the current pipeline (including clustering accounting and the
dry-run replay path), so this is not a strict guarantee on every LLM call.
Usage and cache-token accounting are recorded separately in `llm_usage`.

## Persistence and API

`storage/database.py` creates SQLite tables and applies additive/versioned
migrations. Connections enable WAL, foreign keys, and NORMAL synchronous mode.
The default file is `data/niche_radar.db`. The Compose `postgres` profile only
provisions PostgreSQL; `get_db()` uses `sqlite3` and has no PostgreSQL adapter.
Setting a PostgreSQL URL does not switch the application storage engine.

| Tables | Purpose |
|---|---|
| `collection_runs`, `raw_items` | Capture diagnostics, normalized content, provenance, timestamps. |
| `item_pain_extractions` | A1 decisions and A2 JSON, including rejected items so they are not reprocessed. |
| `niche_candidates`, `niche_item_links`, `niche_analyses` | Opportunity summaries, original evidence links, full per-run A3–A8 outputs. |
| `niche_shortlist` | Starred candidates and operator notes. |
| `app_settings` | LLM/source credentials and runtime configuration. |
| `pipeline_jobs`, `pipeline_runs`, `llm_usage` | Persistent job state/logs, run metadata/prompt hash, token usage. |
| `entities`, `entity_mentions`, `entity_velocity` | Tracked companies/products/technologies/people/categories and weekly activity. |

Analysis normally uses a seven-day freshness window and excludes Raw Items with
null `posted_at`; successful collection counts do not prove analysis coverage.
Retention defaults are 90 days for raw content, 180 days for archived candidates,
and 30 days for collection runs. Raw content also has a stricter freshness cutoff
at twice the analysis window. Cleanup does not currently implement a separate
shortlist-preservation rule; consult `storage/cleanup.py` before changing it.

`api/server.py` assembles routes for status, niches, shortlist, pipeline/jobs,
settings/sources, costs, reports, and entities. `api/jobs.py` persists jobs in
SQLite and buffers active logs in memory; a recorded job is not an automatically
resumable task. Route handlers and Pydantic models define exact HTTP schemas.
Settings reads expose `llm_api_key_set`, not the key; LLM connection tests return
HTTP 200 with `{ok, message}` for connection failures.

## Authentication and deployment

Production uses `APP_ENVIRONMENT=production` and fixed read-only Docker secrets:

- `/run/secrets/apps_login_credentials`: one `username:password` record.
- `/run/secrets/apps_session_secret`: signing key of at least 32 bytes.

There is no production default or environment credential fallback. Invalid or
missing secrets produce safe 503 responses. Only `GET /api/status` and
`POST /api/auth/login` are public; other operations require authentication.
Development bypasses the gate and should only be exposed on trusted local hosts.

Sessions use HMAC-SHA256 with subject, issued/expiry timestamps, and nonce, with
an eight-hour lifetime. `__Host-niche_radar_session` is Secure, HttpOnly,
SameSite=Lax, Path=/, and has no Domain. Logout clears it; signing-key rotation
invalidates all sessions. Keep credentials/tokens out of Web Storage and logs.
Credential comparison is constant-time; failed attempts use a bounded limiter.

Production request path is Cloudflare → Traefik → Next → FastAPI. Traefik trusts
only Cloudflare forwarded headers; Radar resolves client identity right to left
through trusted proxy hops. Never enable unrestricted forwarded-header trust.
The Next proxy validates paths, strips hop-by-hop headers, preserves query
strings and Cookie/Set-Cookie, and exports GET/POST/PUT/DELETE.

Production Compose removes published app/database ports and exposes only the
frontend to the external proxy network. Successful trusted `main` push CI
deploys that exact SHA. Markdown-only changes skip CI and deployment.
Operational commands and rollback are in [deployment.md](deployment.md).

## Intended product behavior (not implemented)

The owner agreed to evidence-first discovery and two assessment tracks. These
are product goals, not claims about the current automatic full pipeline.
The reason is to put original demand evidence ahead of speculative market
judgment and spend deep-analysis cost only where the operator wants it.

Automatic discovery would run A1 → A2 → clustering and present Evidence Clusters
without automatic verdicts or composite opportunity scores. Each member retains
its original quote, URL, source, author identity when available, timestamp, and
separate A2 extraction. No longest-string/max field merge should replace members.
Display names derive from a representative member's pain statement.

An Evidence Cluster would have stable identity, distinct-author/source counts,
first/last seen, recurrence across seven-day windows, and evidence ranking.
Count only non-null author identities; one author's repeated posts are not
independent demand. Ranking uses provenance, recurrence, recency, and potentially
mean/median per-item pain intensity; never A3 market estimates, A4 scores, A6
verdicts, or other deep-dive output. Exact weights require calibration. Per-item
intensity is itself an LLM extraction and should be labeled accordingly.

A1 would independently distinguish real signal from software deliverability:
can one developer address the problem with a web/mobile app? Hardware purchase
advice, account/billing support, regulated government processes, geo-locked
service comparisons, and terms-of-service circumvention fail that second gate.
The proposed `form_factor_verdict` is separately evaluable from signal rejection.

Operator-selected deep dives would run A3–A8 on the full member list and label
all generated market claims as assessment, visibly separate from evidence.
A4 would measure shared dimensions neutrally, with two deterministic weight
vectors and separate A6 recommendations shown side by side:

- **Quick Win:** roughly two weeks to ship and reach 100 users; emphasizes clear
  pain, feasibility, distribution, and time to first user, with little TAM weight.
- **Scalable Product:** potential for $50k MRR; emphasizes market size,
  willingness to pay, competition gap, defensibility, and retention.

Build duration is context, never an automatic rejection reason in either track.
Show estimated weeks separately from technical difficulty. Both tracks use one
consistent tier vocabulary with thresholds calibrated to observed distributions.
Author capture, stable cross-run cluster identity, evidence weights, and track
calibration remain design details to resolve when implementing this direction.

## Validation limits

The fixture eval exercises the real A1/A2 orchestration and validates A1 decisions;
it does not evaluate cluster scores, tiers, or verdict quality. Mocked regression
tests do not establish live collector health. The optional weekly canary probes
keyless sources without invoking a paid analysis run. Historical measurements
and product-quality findings remain in `reviews/` and `sample-reports/`.
