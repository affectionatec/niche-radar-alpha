# Technical Specification: Analysis Pipeline (A1–A8 + Clustering)

> Source PRD: `docs/prd.md` §3 (P0 8-agent pipeline), **§9 amendment (2026-08-04)**
> Related ADRs: ADR-003 (eight-agent pipeline), **ADR-011 (evidence-first pipeline)**, **ADR-012 (dual-track assessment)**
> Status: Draft — consolidating. **Amended 2026-08-04** for ADR-011/012.
> Last updated: 2026-08-04
>
> ⚠️ **This spec now describes two states.** §2–§5 are **current, shipped behavior**.
> §6–§10 are the **target contracts** introduced by ADR-011 and ADR-012, none of which is
> implemented yet. Where they conflict, the ADRs are authoritative and the target sections
> win — but do not assume target behavior exists in code.

## 1. Overview

### 1.1 Current (shipped)

Transforms `raw_items` into scored `niche_candidates`. Four phases: **A** (per item: A1 Signal Filter → A2 Pain Extractor), **B** (clustering: Jaccard + LLM refinement), **C** (per cluster: A3 Market Researcher → A4 Opportunity Scorer → A5 Feasibility Analyst → A6 Go/No-Go Judge → A7 PRD Writer [GO only] → A8 Brief Creator), **D** (persist). Entry: `niche_radar/agents/pipeline.py::run_analysis`.

### 1.2 Target (ADR-011)

The pipeline splits at the **evidence/judgment boundary**:

| | Phase 1 — Discovery | Phase 2 — Deep dive |
|---|---|---|
| Trigger | automatic, every cycle | operator-selected, one cluster |
| Agents | A1 (incl. form-factor gate) → A2 → clustering | A3 → A4 → A5 → A6 → A7 → A8 |
| Output | **Evidence Cluster** — measured facts only | dual-track assessment (ADR-012) |
| Verdict | **none** | per-track recommendation |
| Ranking | counted quantities only, no LLM opinion | n/a |

## 2. Agent I/O Contracts (current)

Each agent has a Pydantic input/output model in `niche_radar/agents/models.py` (A1Output … A8Output). Contracts (full field lists in `docs/agent-pipeline.md`):

- **A1** → binary classification + confidence (0.0–1.0) + signal type ∈ {pain_point, feature_request, competitor_complaint, noise}. Biased to precision; drops ~90% of noise before A2.
- **A2** → structured pain profile (who/what/when/current_workaround/why_current_sucks/desired_outcome) + emotional_intensity (1–10) + 3–5 clustering keywords.
- **A3** → competitor list, market leader, gap, TAM (with uncertainty), saturation (1–10).
- **A4** → 7 calibrated dimensions (1–10) → weighted 0–100 composite; strengths/risks/comparables. Weights per `docs/agent-pipeline.md` (willingness-to-pay highest at 2.0).
- **A5** → feasibility_score (1–10), solo_buildable bool, MVP scope + explicit out-of-scope, build_complexity (1–5).
- **A6** → verdict ∈ {GO, NO-GO, PIVOT} + killer risk + conditions_to_reconsider. Controls flow: A7 runs only on GO.
- **A7** (GO only) → lean PRD. **A8** (always) → 60-second brief.

**Design invariants (must hold):** structured JSON only; null over hallucination; calibrated scoring (9–10 rare); partial-failure tolerance (missing upstream → "unknown" substituted, downstream still runs).

## 3. Clustering (Phase B, current)

Per `docs/ARCHITECTURE.md` (Clustering Strategy):
- Step 1 — Jaccard pre-grouping (deterministic, no LLM): keyword sets from A2 (fallback A1 tokens) → trivial stemmer → Union-Find merge where Jaccard ≥ `JACCARD_THRESHOLD` (default 0.5).
- Step 2 — LLM refinement only for pre-clusters ≥ `LLM_REFINE_MIN_SIZE` (default 4), chunked at `LLM_MAX_ITEMS_PER_CALL` (default 40), temperature `LLM_TEMPERATURE` (default 0.2). Orphans → "leftover" cluster (never lose items).
- Failure modes: refinement failure / bad JSON / no keywords → documented fallbacks (single cluster or token extraction).

## 4. Cost Control (must hold)

- A1 filters before A2–A8; clustering collapses items before A3–A8.
- Per-run LLM budget bounded by `2N + 10C + 50` (N = items passing A1, C = clusters). The pipeline MUST NOT exceed the cap; overflow is truncated/deferred, not silently spent.
- **Target (ADR-011):** with A3–A8 leaving the automatic path, the per-cycle bound becomes
  `2N + clustering`. The `10C` term moves to Phase 2 and is paid per operator-triggered deep
  dive, not per cycle.

## 5. Acceptance Criteria (current)

| # | Criterion | Verify via | Evidence |
|---|-----------|------------|----------|
| 1 | Agent contracts validate (A1–A8 models) | `pytest tests/test_agents -v` | exit 0 |
| 2 | Clustering groups/leftover behavior holds | `pytest tests/ -k cluster` | exit 0 |
| 3 | Golden-set eval passes (calibration regression gate) | `python -m niche_radar.eval.runner` | exit 0 |
| 4 | Partial-failure tolerance: a failing upstream agent does not abort downstream | `pytest tests/ -k "partial or failure"` | exit 0 |

---

# TARGET CONTRACTS (ADR-011 / ADR-012 — not implemented)

## 6. A1 form-factor gate

A1 gains a second, independent pass condition. Both must hold:

1. **Signal condition** (existing): a real person describes a specific, unsolved,
   product-shaped frustration.
2. **Form-factor condition** (new): the problem could plausibly be addressed by a **web or
   mobile application one developer can ship**.

**MUST reject** under condition 2, regardless of how strong the pain is:

| Reject class | Example seen in production |
|---|---|
| Hardware selection / purchase advice | "reliable OpenWRT router under 1000 CNY"; BGP full-table router |
| Account / billing support | Apple ID permanently bound to a ChatGPT subscription |
| Government or regulated process | domain registration 公安 approval; 等保 certification |
| Geo-locked service comparison | China Unicom Shenzhen bundled plans |
| Terms-of-service circumvention | paying for SuperGrok without a foreign card; splitting a paid seat |

A1's output model gains a `form_factor_verdict` field so the two conditions are separable
in evaluation — a signal rejected for form factor MUST be distinguishable from one rejected
as noise, otherwise precision cannot be attributed.

**Golden-set impact:** the 61-item set gains form-factor labels. Items currently labeled
PASS that fail condition 2 must be relabeled, and the eval runner must report signal
precision and form-factor precision separately.

## 7. Evidence Cluster (Phase 1 output)

The primary persisted object of the automatic path. Replaces `niche_candidates` as what the
operator sees per cycle.

### 7.1 Required fields

| Field | Type | Source | Notes |
|---|---|---|---|
| `cluster_id` | uuid | clustering | stable across cycles once assigned |
| `members` | list | clustering | **full member list, never merged** |
| `members[].raw_item_id` | str | collector | |
| `members[].quote` | str | raw item | **verbatim**, never LLM-rewritten |
| `members[].url` | str | collector | must resolve to the original post |
| `members[].source` | str | collector | |
| `members[].author_id` | str \| null | collector | **new** — required for distinct-author counting |
| `members[].posted_at` | datetime | collector | **non-null required** (see F4) |
| `members[].a2` | A2Output | A2 | per-item, kept separate |
| `distinct_authors` | int | derived | count of unique non-null `author_id` |
| `distinct_sources` | int | derived | |
| `first_seen` / `last_seen` | datetime | derived | |
| `recurrence_windows` | int | derived | number of distinct 7-day windows with ≥1 member |
| `evidence_score` | float | derived | §8 |
| `display_name` | str | derived | from A2 `what` of the highest-intensity member — **not** keyword frequency |

### 7.2 Invariants (must hold)

- **No field-wise merge.** `aggregate_cluster_a2()`'s longest-string/max merge is **deleted**,
  not repaired. A cluster has no single `who`/`what`; it has members.
- **No LLM-authored text in Phase 1 output** except A2's per-item extraction, which is
  extraction from a quote, not invention about a market.
- **Quotes are verbatim.** Any rendering that paraphrases a member quote is a defect.
- **`occurrence_count` is retired** in favor of `distinct_authors` / `distinct_sources`.
  Item count is not a demand signal — 13 posts by one author is not 13 people.

## 8. Evidence score (Phase 1 ranking)

Ranks Phase 1 output. **Every input MUST be a counted or timestamped quantity.** No LLM
opinion may enter this score — that property is what makes the ordering defensible.

Permitted inputs:

| Input | Rationale |
|---|---|
| `distinct_authors` | independent people ≠ repeated posting |
| `distinct_sources` | cross-platform corroboration is stronger than single-forum volume |
| `recurrence_windows` | a pain recurring across weeks beats a burst |
| recency of `last_seen` | decay for stale clusters |
| A2 `emotional_intensity` | per-item, **aggregated as median or mean — never `max`** (see Q3) |

**Forbidden inputs:** A3 TAM, A4 dimension scores, A6 verdict, or any other Phase 2 output.
Phase 2 has not run for most clusters, and where it has, including it would let speculation
re-enter the ranking.

**Open:** exact weighting. It must be calibrated against real distributions once
`distinct_authors` exists — the current data cannot inform it, because author identity is
not captured today. Ship with a documented, simple starting formula and record the
calibration as a follow-up, rather than guessing weights now.

## 9. Dual-track assessment (Phase 2, ADR-012)

### 9.1 Structure

A4 becomes a **neutral measurer**: its venture-analyst persona is removed, it scores
dimensions factually, and its per-dimension rationales must read correctly under either
track. Its dimension set grows to cover Track B (defensibility, retention).

Two weight vectors are applied to that single A4 output. **This is deterministic arithmetic,
not extra inference** — added LLM cost is limited to A4's larger dimension set and A6
emitting two recommendations.

| | Track A — Quick Win | Track B — Scalable Product |
|---|---|---|
| Question | "Can I ship this in ~2 weeks and reach 100 users?" | "Could this plausibly reach $50k MRR?" |
| Weighted up | problem clarity, technical feasibility, distribution clarity, time to first user | market size, willingness to pay, competition gap, defensibility, retention |
| TAM | **near-zero weight** — $1–10M is acceptable | heavily weighted |
| Build duration | central input | weak input |

A6 emits **one recommendation per track**. A cluster may qualify for A only, B only, both,
or neither. Both is rare and is the signal worth surfacing.

### 9.2 Hard rules

- **Build duration MUST NOT be a rejection reason in either track.** The 2-4 week window is
  a reference value (operator decision, 2026-08-04), not a gate.
- `estimated_weeks_to_mvp` is displayed **as a fact**.
  `build_complexity_from_feasibility()` is **retired** — deriving a time label from a
  difficulty score is the root cause of the contradictory quick-win in F9/Q9.
- **One tier definition, applied per track.** The two contradicting vocabularies in
  `agents/scorer.py:29` (hot/warm/cold on 0–70) and `api/routes/_common.py:13`
  (high_priority/watchlist/archive on 0–100) collapse to one, with thresholds recalibrated
  against the observed distribution — the current ≥80 top tier has never been reached
  (all-time max 72.63).
- Phase 2 output MUST be visually distinguishable from Phase 1 evidence in the UI, and MUST
  be labeled as assessment.

## 10. Target acceptance criteria

| # | Criterion | Verify via |
|---|---|---|
| T1 | A1 rejects all five form-factor classes in §6 | golden set with form-factor labels; eval reports the two precisions separately |
| T2 | An Evidence Cluster exposes every member with a verbatim quote and resolvable URL | unit + fixture replay |
| T3 | No Phase 2 field appears in `evidence_score`'s inputs | static check / unit test asserting the input set |
| T4 | `aggregate_cluster_a2()` field-wise merge is gone and no caller depends on it | grep + tests |
| T5 | Neither track rejects on build duration | fixture with a 12-week MVP scoring well on Track B |
| T6 | A cluster with N members by one author reports `distinct_authors == 1` | unit |
| T7 | Automatic cycle issues zero A3–A8 calls | budget counter assertion on a full cycle |

## 11. Open Questions

- Decompose remaining `docs/spec.md` §4 detail (validation/scoring rubric tables) into this spec. (Tracked under ADR-004 follow-ups.)
- **Author identity is not currently captured by any collector.** `distinct_authors` (§7,
  §8) cannot be computed until collectors persist an author field. This is a prerequisite
  for the evidence score and must be sequenced before Stage 2 completes.
- **Evidence-score weights** (§8) require calibration against data that does not yet exist.
- **Cluster identity across cycles.** `cluster_id` is specified as stable, but the current
  clustering is batch-local and regenerates UUIDs each run. Longitudinal stability is a
  prerequisite for `recurrence_windows` and is tracked as Stage 4 (longitudinal pain
  fingerprints).
