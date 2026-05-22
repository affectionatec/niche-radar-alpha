<!-- generated: 2026-05-22 -->
# Domain Glossary

> Canonical terms for this codebase. Use these exact words in code,
> comments, and conversation. Last updated: 2026-05-22.

## Niche Candidate
**Definition**: An emerging topic or product opportunity discovered by clustering pain-point signals across multiple data sources.
**Lives in**: `niche_radar/storage/`, `niche_candidates` table
**Distinct from**: RawItem (which is a single ingested data point, not yet analysed)

## Raw Item
**Definition**: A single piece of content ingested from a data source — a Reddit post, HN story, GitHub repo, YouTube video, or trend data point.
**Lives in**: `niche_radar/collectors/`, `raw_items` table
**Distinct from**: Niche Candidate (which is the clustered, scored result of many raw items)

## Collector
**Definition**: A module that fetches raw items from one external platform, normalises them into `CollectorResult`, and stores them.
**Lives in**: `niche_radar/collectors/`
**Distinct from**: Agent (which performs LLM-powered analysis, not data fetching)

## CollectorResult
**Definition**: The standardised return type from every collector — contains source name, list of raw items, run ID, status, and timing metadata.
**Lives in**: `niche_radar/collectors/base.py`

## Agent (A1–A8)
**Definition**: One step in the 8-agent LLM pipeline that transforms raw items into scored niche candidates. Each agent has a structured input/output model.
**Lives in**: `niche_radar/agents/`
**Distinct from**: Collector (which fetches data; agents analyse it)

## Pipeline
**Definition**: The full analysis workflow — Phase A (per-item: A1 Signal Filter + A2 Pain Extractor), Phase B (clustering), Phase C (per-cluster: A3–A8), Phase D (persistence).
**Lives in**: `niche_radar/agents/pipeline.py`, `niche_radar/agents/orchestrator.py`

## Composite Score / LLM Score
**Definition**: A 0–100 weighted score across 7 dimensions (problem clarity, market size, willingness-to-pay, competition gap, feasibility, distribution, trend momentum) assigned by Agent A4.
**Lives in**: `niche_radar/agents/models.py` (A4Output), `niche_candidates.llm_score` column

## Verdict
**Definition**: The GO / NO-GO / PIVOT decision issued by Agent A6 for each niche candidate cluster.
**Lives in**: `niche_radar/agents/models.py` (A6Output)
**Distinct from**: Composite Score (numeric) — verdict is a categorical judgment

## Shortlist
**Definition**: User-curated subset of niche candidates starred for closer review.
**Lives in**: `niche_radar/api/server.py`, `shortlist_notes` table

## Momentum
**Definition**: Week-over-week change in mention count for a niche candidate — classified as growing, stable, or declining.
**Lives in**: `niche_radar/api/server.py` (momentum endpoint), `niche_candidates.momentum_label`

## Collection Run
**Definition**: A single execution of one collector, tracked for observability with status, item count, and timing.
**Lives in**: `niche_radar/storage/`, `collection_runs` table

## Pain Point
**Definition**: A user frustration or unmet need extracted from raw items by Agent A2, stored as a pain statement + verbatim quote.
**Lives in**: `niche_radar/agents/models.py` (A2Output), `item_pain_extractions` table

## Cluster
**Definition**: A group of related raw items with overlapping keywords, formed by Jaccard pre-grouping then optionally refined by LLM.
**Lives in**: `niche_radar/agents/clustering.py`
**Distinct from**: Niche Candidate (a cluster becomes a niche candidate after scoring)
