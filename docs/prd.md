# PRD: Niche Radar Alpha

> Status: Approved (baseline — describes the shipped alpha)
> Last updated: 2026-06-24 · **Amended 2026-08-04 — see §9**
> Absorbs: `docs/PRODUCT.md`, `README.md` overview, `.ralph/prd.json` (Docker-runtime epic)
>
> ⚠️ **§3 P0 and §7 are amended by ADR-011 and ADR-012** (2026-08-04). The delivery model
> changed from "every cluster is automatically scored and given a verdict" to
> "evidence automatically, assessment on demand, across two tracks." Read §9 before
> treating §3 as current.

## 1. Problem & Vision

Entrepreneurs and indie hackers spend hours manually scanning Reddit, Hacker News, Twitter/X, and YouTube for emerging product ideas and unmet user needs. By the time a trend is obvious, the market is crowded. There is no automated, cross-platform system that continuously monitors public signals, extracts pain points, scores opportunity quality, and delivers actionable daily reports of high-potential niches.

**Vision:** A self-hosted radar that watches the public web for *validated pain*, clusters it into candidate niches, scores each on opportunity quality, and hands the operator a ranked shortlist with a build-ready brief — so the decision becomes "which of these 10 do I build," not "where do I even look."

## 2. Users

- **Solo founders / indie hackers** — validated product ideas with low build complexity.
- **Side-project builders** — quick signal on trending topics before committing weekends.
- **Micro-SaaS operators** — monitoring adjacent opportunities in their space.
- **Content creators** — trending topics for articles, videos, courses.

Single-user, self-hosted. No auth, no multi-tenancy.

## 3. Features & Priority Triage

### P0 — Product fails without it
- **Multi-source ingestion** through a resilient collector layer. Each source normalizes to `CollectorResult` / `raw_items`. Fragile or blockable sources run an ordered **multi-backend fallback chain** (ADR-002) so one backend breaking does not take the source down.
- **8-agent LLM pipeline** (A1–A8): signal filter → pain extractor → (clustering) → market researcher → opportunity scorer → feasibility analyst → go/no-go judge → PRD writer (GO only) → brief creator. Zero-shot, structured-JSON, partial-failure tolerant (ADR-003).
- **Scored niche candidates** — 7-dimension 0–100 composite score, GO/NO-GO/PIVOT verdict, build-complexity estimate; persisted to SQLite (ADR-001).
- **Web dashboard** — opportunity table, niche detail, shortlist, pipeline control, report viewer. Reaches the backend at runtime via the Next.js `/api` proxy.
- **Background automation** — APScheduler: collection every 4h, analysis every 6h, cleanup daily.
- **Pluggable LLM** — OpenAI-compatible (OpenAI/DeepSeek/Groq/Ollama) + Anthropic, configured from the web UI; connection testable before a run.

### P1 — Ship shortly after
- Source expansion beyond the launch set (Stack Overflow, Product Hunt, G2, Indie Hackers, App/Play Store, Bluesky, ScrapeCreators trio).
- Cost observability — per-niche cost attribution, cache-hit tracking, A1 filter-rate.
- First-run onboarding (settings redirect when no LLM key configured).

### P2 — Defer
- Entity-intelligence layer (tracking specific products/companies over time).
- Score-transparency UI (per-dimension breakdown).
- Server decomposition (`server.py` split by concern).

## 4. Boundaries / Non-Goals

- **Not** a market-research platform with paid data providers — sources are free/public (a key may unlock a more stable path, but no source is gated behind a mandatory paid API).
- **Not** a CRM or project-management tool — stops at idea validation + PRD/brief.
- **No** user authentication or multi-tenancy — single-user self-hosted.
- **No** real-time streaming — batch collection/analysis cycles.

## 5. Technical Direction

- Python 3.11+ pipeline; FastAPI + Uvicorn API; SQLite default with PostgreSQL opt-in; Next.js 14 dashboard; Docker Compose deployment. Pluggable LLM behind `niche_radar/llm/`.
- Resilience over breadth: a source is only as good as its most reliable backend. Capture paths are interchangeable `SourceBackend`s behind `MultiBackendCollector` (→ `docs/spec/collectors.md`).
- Cost control is architectural: clustering before per-cluster analysis; bounded per-run LLM budget.

## 6. Extensibility

- **New source:** implement `BaseCollector` (or `MultiBackendCollector` + `SourceBackend`s), register in `niche_radar/collectors/__init__.py::ALL_SOURCES`, add a `CREDENTIAL_SCHEMA`. Credential-gated sources stay silent (`is_available()`) until configured.
- **New backend for an existing source:** add a `SourceBackend` to that collector's chain — no rewrite. This is the seam the Agent-Reach capability port targets (→ `docs/plans/implementation-plan.md`).
- **New LLM provider:** add a client under `niche_radar/llm/` implementing the shared `chat()` interface.

## 7. Success Metrics

- Operator can go from "nothing configured" to a scored shortlist with zero paid API keys.
- A single fragile source backend failing degrades that source gracefully (fallback or skip), never the run.
- Daily report surfaces a ranked, deduplicated set of niche candidates with verdict + build complexity.

## 8. Status

Active alpha — core pipeline functional; 16 collectors implemented; dashboard operational; LLM analysis producing scored results. No stable release yet.

## 9. Amendment 2026-08-04 — evidence-first delivery, dual-track assessment

> Source: `docs/reviews/2026-08-04-opportunity-quality-review.md`, ADR-011, ADR-012.
> Nothing below is implemented yet; this records the agreed product direction so §3 does not
> stand in contradiction to the accepted ADRs.

### What changed and why

After 1,530 production cycles the pipeline had produced 207 niche candidates and
**0 GO verdicts** — it had never once told the operator to build something. Diagnosis: the
product automates judgment (which the operator does well, given evidence) and
under-invests in reading volume (which they cannot do at all). Each card also rested on
roughly one sentence of real quoted text beneath six layers of LLM invention.

### Amendments to §3 P0

- **"8-agent LLM pipeline (A1–A8)"** — the decomposition stands (ADR-003), but the
  *invocation model* changes. A1 → A2 → clustering run automatically every cycle. **A3–A8
  run on demand**, on a single cluster the operator selects (ADR-011).
- **"Scored niche candidates — 7-dimension 0–100 composite score, GO/NO-GO/PIVOT verdict"**
  — replaced. The automatic path produces **Evidence Clusters** carrying verbatim quotes
  with source links, distinct-author and distinct-source counts, recurrence, and recency —
  no verdict and no composite score. On-demand deep dives produce **two independent
  assessments** (Quick Win / Scalable Product) rather than one blended verdict (ADR-012).
- **"Web dashboard — opportunity table…"** — the primary object becomes the Evidence
  Cluster, with a visual split between collected evidence and LLM assessment.
- **A1 gains a form-factor gate**: a signal only passes if it could plausibly be solved by a
  web or mobile application one developer can ship. Hardware, purchase advice,
  account/billing support, government processes, and geo-locked services are rejected (Q5).

### Amendment to §7 Success Metrics

The third metric — *"Daily report surfaces a ranked, deduplicated set of niche candidates
with verdict + build complexity"* — is replaced by:

> Every cycle surfaces evidence clusters **ranked only by counted quantities** (distinct
> authors, distinct sources, recurrence, recency). No ranking dimension is an LLM opinion.
> Verdicts and build estimates appear only in on-demand deep dives, labeled as assessment.

### Unchanged

Non-goals (§4), the free/public-sources constraint, single-operator self-hosting, batch
(not real-time) operation, cost discipline, and the extensibility seams (§6) all stand.
