# LLM-Powered Niche Analysis Refactor

**Date:** 2026-05-17  
**Status:** Approved

## Problem

The pipeline uses local NLP (KeyBERT + sentence-transformers) which requires downloading ~400MB models from HuggingFace at startup. This fails without internet access, is slow, and adds heavy dependencies. The 4-dimension scoring engine is also tightly coupled to this local NLP output.

## Solution

Replace the entire NLP + scoring layer with a single LLM analysis step. Raw collected items are sent in batches to a configurable LLM API (OpenAI-compatible or Anthropic). The LLM identifies niche opportunities, scores them, and writes reasoning. The frontend exposes a settings page to configure the LLM provider without redeploying.

## Pipeline

```
collect (unchanged) → analyze (LLM) → report
```

1. **Collect** — 5 sources, writes to `raw_items` (unchanged)
2. **Analyze** — reads unprocessed items in batches, calls LLM, persists niches with scores
3. **Report** — reads top niches, LLM writes prose summary, outputs markdown + JSON

## LLM Providers

- **openai_compat** — covers DeepSeek, Groq, OpenAI, Ollama, any OpenAI-format API
- **anthropic** — native Anthropic SDK

Config via `.env` or frontend Settings page (stored in `app_settings` DB table):
`LLM_PROVIDER`, `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`, `LLM_BATCH_SIZE`

## DB Schema Changes

| Table | Change |
|---|---|
| `niche_candidates` | Drop `embedding BLOB`; add `llm_score REAL`, `llm_reasoning TEXT` |
| `niche_scores` | Unused (cleanup removes references) |
| `trend_snapshots` | Unused (cleanup removes references) |
| `app_settings` | **New** — `key TEXT PRIMARY KEY, value TEXT` |

Dedup niches by lowercase keyword string match (Python-side, not UNIQUE constraint).

## Modules

**New:**
- `niche_radar/llm/base.py` — `LLMClient` protocol
- `niche_radar/llm/openai_compat.py` — OpenAI-compatible client
- `niche_radar/llm/anthropic_client.py` — Anthropic client
- `niche_radar/analysis/analyzer.py` — `run_analysis(db, settings)`
- `niche_radar/reports/generator.py` — `generate_report(db, settings, fmt)`

**Deleted:**
- `niche_radar/nlp/` (extractor, clusterer, preprocessor)
- `niche_radar/scoring/` (4 scorers + composite)

## API Changes

| Before | After |
|---|---|
| `POST /api/pipeline/extract` | Removed |
| `POST /api/pipeline/score` | Removed |
| — | `POST /api/pipeline/analyze` |
| — | `GET /api/settings` |
| — | `POST /api/settings` |
| run-all: collect→extract→score→report | run-all: collect→analyze→report |

## Frontend Changes

- Settings page (`/settings`) — configure LLM provider, API key, model, base URL
- NicheCard — replace 4 score bars with `llm_reasoning` text
- Niche detail — replace score breakdown with AI analysis section
- Niches list — `llm_score` column instead of `composite_score`
- Pipeline page — ANALYZE button replaces EXTRACT + SCORE
- Navigation — add SETTINGS link
