# Niche Radar — Intelligence Platform Roadmap

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Evolve Niche Radar from a niche-product-opportunity finder into a strategic intelligence platform for indie makers and small product teams — adding entity tracking, custom monitors, cross-source correlation, relationship mapping, prediction market signals, and AI-powered research chat.

**Architecture:** The existing 16-source → 8-agent pipeline stays intact as the "Niche Discovery Engine." New capabilities are added as peer subsystems that feed into and draw from the same data lake. A new "Radar" (custom monitor) subsystem scans all ingested content for user-defined topics. An entity extraction layer runs across all raw items. A relationship graph connects entities over time. All new subsystems expose results through the existing Next.js dashboard.

**Tech Stack:** Python 3.11+ (FastAPI, SQLAlchemy), Next.js 14 (React 18, SWR), SQLite/PostgreSQL, LLM provider-agnostic (OpenAI-compatible + Anthropic)

---

## Introduction: Where We Are and Where We're Going

### Current State

Niche Radar v0 (alpha) monitors 16 public platforms on a 4-hour cycle, runs an 8-agent LLM pipeline to extract pain points, clusters them, scores opportunities across 7 dimensions, and delivers GO/NO-GO/PIVOT verdicts through a web dashboard. It works well for its intended purpose: finding product ideas in public complaints.

### The Limitation

The current system treats every piece of ingested content as potential kindling for a niche discovery fire. But raw items contain rich metadata — people, companies, technologies, products, markets, and trend signals — that the pipeline discards. The system knows "people are complaining about X" but doesn't know "company Y just raised $50M to solve X" or "technology Z is mentioned 3x more this week." It finds niches but doesn't track the ecosystem around them.

### The Vision

Niche Radar becomes a **strategic intelligence platform** — still centered on product opportunity discovery, but enriched with entity intelligence, custom topic monitoring, competitive landscaping, and AI-powered research. The user doesn't just get a list of niches. They get a live map of what's happening in their areas of interest: who's building what, which technologies are gaining traction, where funding is flowing, and which problems are underserved.

This roadmap draws inspiration from FinceptTerminal's multi-agent intelligence architecture — particularly its entity extraction, custom monitors, news clustering with velocity, relationship mapping, and MCP integration — adapted to the indie-maker use case.

### What We're NOT Building

- Real-time streaming or WebSocket feeds — batch-oriented remains fine for this audience
- Multi-tenancy or user auth — stays single-user self-hosted
- Financial trading or market data — different domain entirely
- Native desktop app — web dashboard remains the interface

---

## Phase 1: Entity Intelligence (Weeks 1–2)

**Goal:** Extract and track named entities (companies, products, technologies, people) from all ingested content, making them first-class objects in the system.

### Why This First

Entity extraction is foundational. Every subsequent feature — monitors, relationship graphs, cross-source correlation — depends on knowing WHAT is being discussed, not just that people are complaining about something. Entity tracking turns raw text into structured intelligence.

### Features

| Feature | Description |
|---------|-------------|
| **Entity Extraction (E1)** | LLM-powered NER across all raw items — extracts companies, products, technologies, people, and categories |
| **Entity Store** | New `entities` table with type, name, aliases, first/last seen, mention count, source diversity |
| **Entity Detail Page** | Dashboard page showing entity profile, mention timeline, related entities, source breakdown |
| **Entity Mentions** | Join table linking raw items to extracted entities with sentiment and relevance score |
| **Weekly Entity Digest** | "Trending this week" — entities with the highest velocity growth, surfaced on Home and a dedicated page |

### Key Insight from FinceptTerminal

FinceptTerminal's `NewsNlpService` extracts entities (countries, organizations, people, tickers) from every news article and aggregates them into `TopEntity` leaderboards. We adapt this pattern but extract entities relevant to product builders: startups, technologies, tools, frameworks, investors, and product categories.

### Data Model Sketch

```
entities
  id, type (company|product|technology|person|category),
  canonical_name, aliases (JSON), first_seen, last_seen,
  mention_count, source_diversity, velocity_score

entity_mentions
  entity_id, raw_item_id, sentiment (positive|negative|neutral),
  relevance (0.0-1.0), extracted_at

entity_velocity
  entity_id, week_start, mention_count, source_count,
  velocity (growing|stable|declining), score (0-100)
```

---

## Phase 2: Custom Radars (Weeks 3–4)

**Goal:** Let users define persistent topic monitors ("Radars") that scan all incoming content for specific keywords, entities, or themes — separate from the niche discovery pipeline.

### Why This Second

Entity extraction gives us structured data. Custom Radars give users a reason to care — they can now track what matters to them specifically. A user researching "AI code editors" creates a Radar for it, and every collection cycle surfaces relevant signals. This is the feature that transforms the tool from "interesting reports I might check" to "something I use daily."

### Features

| Feature | Description |
|---------|-------------|
| **Radar CRUD** | Create/edit/delete Radars with name, keywords, entity filters, source filters |
| **Radar Scanner** | After each collection cycle, scan all new raw items against active Radars |
| **Radar Feed** | Dashboard page showing Radar hits — grouped by Radar, sorted by recency |
| **Radar Velocity** | Per-Radar mention velocity with sparkline chart |
| **Radar Alerts** | Optional notification when a Radar spikes (configurable threshold) |
| **Radar-to-Niche** | Button to feed a Radar's accumulated signals into the niche pipeline as a targeted analysis run |

### Key Insight from FinceptTerminal

FinceptTerminal's `NewsMonitorService` allows users to define keyword-based monitors with custom colors that scan all incoming news articles. Each monitor shows matching articles with source and category context. We adapt this to the product/tech domain, adding entity-based filtering (not just keywords) and the ability to promote a Radar into a full niche analysis.

### Data Model Sketch

```
radars
  id, name, description, keywords (JSON), entity_ids (JSON),
  source_filter (JSON), active (bool), created_at, updated_at

radar_hits
  radar_id, raw_item_id, matched_keywords (JSON),
  matched_entities (JSON), relevance_score, hit_at

radar_velocity
  radar_id, day, hit_count, unique_sources
```

---

## Phase 3: Cross-Source Correlation (Weeks 5–6)

**Goal:** Detect when the same entity, topic, or narrative surfaces across multiple independent sources simultaneously — a stronger signal than any single source.

### Why This Third

With entities and Radars in place, the next leap in signal quality is correlation. When "local-first databases" trend on Reddit, HN, AND GitHub in the same 24-hour window, that's a much stronger signal than appearing on any single platform. Cross-source corroboration reduces false positives and surfaces emerging trends earlier.

### Features

| Feature | Description |
|---------|-------------|
| **Correlation Engine** | After each collection cycle, compute entity co-occurrence across sources within time windows |
| **Correlation Score** | 0–100 score based on source diversity, entity velocity, and temporal proximity |
| **Correlated Signals Feed** | Dashboard page showing top correlated signals in the last 24h/7d/30d |
| **Correlation → Niche Promotion** | When a correlated signal crosses a threshold, auto-suggest it as a niche candidate for pipeline analysis |
| **Breaking Signal Detection** | Flag entities with sudden multi-source spikes ("breaking" — 3+ sources, velocity > 2σ above baseline) |

### Key Insight from FinceptTerminal

FinceptTerminal's `NewsCorrelationService` computes `CorrelationSignal` objects with types like `velocity_spike`, `keyword_spike`, and `triangulation` — each with a severity level and contributing sources. The `InstabilityScore` aggregates these into a country-level stability index. We adapt this pattern to product/tech topics: instead of "instability," we compute "emergence" — how strongly a topic is bubbling up across sources.

### Data Model Sketch

```
correlated_signals
  id, entity_ids (JSON), source_ids (JSON), time_window_start,
  time_window_end, correlation_score, signal_type
  (velocity_spike|triangulation|sustained_growth),
  promoted_to_niche (bool), niche_candidate_id
```

---

## Phase 4: Relationship Graph (Weeks 7–8)

**Goal:** Map and visualize connections between entities — companies, products, technologies, people — to reveal the ecosystem around any topic.

### Why This Fourth

Entities, Radars, and correlations tell you WHAT is happening. The relationship graph tells you WHY it matters and WHO is involved. A user looking at a niche for "privacy-first analytics" can see: which companies are building in this space, what tools they use, who funds them, and what adjacent problems exist. This is the feature that makes Niche Radar a genuine research tool rather than a report generator.

### Features

| Feature | Description |
|---------|-------------|
| **Relationship Extraction** | LLM-powered extraction of relationships from raw items: "X competes with Y," "X uses Z," "X is funded by W," "X is an alternative to Y" |
| **Graph Store** | `relationships` table with source entity, target entity, relationship type, strength, and provenance |
| **Graph Visualization** | Force-directed graph on the Entity Detail page showing 1- and 2-hop connections |
| **Ecosystem View** | For any entity, show: competitors, complements, dependencies, investors, key people |
| **Graph API** | REST endpoints for entity neighbors, paths between entities, and subgraph export |

### Key Insight from FinceptTerminal

FinceptTerminal's `RelationshipMapScreen` renders an interactive network graph of conflicts, crises, and organizations — each node is clickable for details. The `RelationshipPanel` shows entity-level connections extracted from news. We adapt this to product/tech relationships with a force-directed graph rendered in the Next.js dashboard (using D3.js or vis-network).

### Data Model Sketch

```
relationships
  id, source_entity_id, target_entity_id, relationship_type
  (competes_with|uses|funded_by|alternative_to|depends_on|acquired_by|partners_with),
  strength (0.0-1.0), extracted_from_item_ids (JSON),
  first_seen, last_seen, mention_count
```

---

## Phase 5: Expanded Data Sources (Weeks 9–10)

**Goal:** Add high-signal data sources that provide leading indicators for product/tech trends — going beyond social platforms to structured data.

### Why This Fifth

The first four phases make the analysis layer dramatically smarter. But the analysis is only as good as the data. Adding structured sources — funding data, academic papers, patent filings, job postings — provides objective leading indicators that complement the subjective signals from social media.

### New Sources

| Source | Signal Type | Why It Matters |
|--------|-------------|----------------|
| **arXiv** | Research papers | Earliest indicator of technology direction |
| **Crunchbase / YC** | Funding rounds | Where capital is flowing |
| **Hacker News "Who Is Hiring"** | Job postings | Which technologies companies are hiring for |
| **GitHub Topics** | Repository metadata | What developers are actually building |
| **Patent filings (Google Patents)** | IP activity | Commercial intent behind technologies |
| **G2 / Capterra** (enhanced) | Review velocity + sentiment | Product-market fit signals |
| **Substack / Medium** | Long-form analysis | Deep trend analysis from domain experts |

### Design

Each new source follows the existing collector pattern (`collectors/base.py` → `CollectorResult`). No architectural changes needed. Sources are configured from Settings → Data Sources (same as existing sources).

---

## Phase 6: AI Research Chat (Weeks 11–12)

**Goal:** An AI chat interface with full context of the intelligence graph — the user can ask questions about entities, trends, niches, and relationships and get grounded answers.

### Why This Last

The chat is most valuable when it has rich context to draw from. Building it last means it can answer questions like "What are the top 3 underserved niches in developer tools this month?" or "Show me the competitive landscape around Notion alternatives" with data from entities, Radars, correlations, and the relationship graph — not just LLM knowledge.

### Features

| Feature | Description |
|---------|-------------|
| **Research Chat UI** | AI chat panel (slide-out or dedicated page) with streaming responses |
| **Context Injection** | Chat automatically includes relevant entities, trends, niches, and Radar hits in the LLM context |
| **Structured Queries** | Pre-built query templates: "Analyze this niche," "Compare these entities," "What's trending in X?" |
| **Citation Linking** | Chat responses link back to source items and entity pages in the dashboard |
| **Chat History** | Persistent chat sessions stored locally |

### Key Insight from FinceptTerminal

FinceptTerminal has both a full `AiChatScreen` tab and a floating `AiChatBubble` for quick questions. Both have access to the full data context (market data, news, portfolio). We adapt this pattern with a Research Chat that has access to the entity graph, Radar hits, niche candidates, and raw item corpus — making it a genuine research assistant, not a generic chatbot.

---

## Phase 7: MCP Integration & Extensibility (Week 13+)

**Goal:** Expose Niche Radar's intelligence as MCP (Model Context Protocol) tools, allowing users to plug it into their own AI workflows, and support community-built extensions.

### Features

| Feature | Description |
|---------|-------------|
| **MCP Server** | Expose key capabilities as MCP tools: search entities, query Radars, fetch niche candidates, get trending topics |
| **MCP Tools** | `search_entities(query)`, `get_niche_detail(id)`, `query_radars()`, `get_trending(period)`, `get_entity_graph(entity_id)` |
| **Webhook Outbound** | POST niche candidates or Radar alerts to user-configured webhook URLs |
| **Plugin/Prompt Pack Marketplace** | Community-contributed prompt packs, collector plugins, and analysis templates |

### Key Insight from FinceptTerminal

FinceptTerminal has a full MCP implementation (`McpManager`, `McpClient`, `McpProvider`, `McpMarketplace`) that allows external AI tools to interact with the terminal's data and capabilities. We implement a lightweight subset focused on read-access to the intelligence graph, with tool definitions following the MCP specification.

---

## Implementation Order & Dependencies

```
Phase 1: Entity Intelligence ─────────────────────┐
   │                                               │
   ▼                                               │
Phase 2: Custom Radars ──────┐                    │
   │                          │                    │
   ▼                          ▼                    │
Phase 3: Cross-Source Correlation                  │
   │                                               │
   ▼                                               │
Phase 4: Relationship Graph ───────────────────────┘
   │                    (All prior phases feed into
   ▼                     the relationship graph)
Phase 5: Expanded Data Sources
   │
   ▼
Phase 6: AI Research Chat ──── (depends on all above for rich context)
   │
   ▼
Phase 7: MCP Integration ──── (exposes all above as tools)
```

Each phase produces a working, testable increment. Phases 1–4 are tightly coupled (entities → radars → correlation → graph). Phases 5–7 are more independent and can be reordered.

---

## Dashboard Pages Added

| Phase | New Page(s) |
|-------|-------------|
| P1 | **Entities** (list + trending), **Entity Detail** (profile, timeline, mentions) |
| P2 | **Radars** (CRUD list), **Radar Feed** (hits by Radar), **Radar Detail** (velocity chart, settings) |
| P3 | **Signals** (correlated signals feed, breaking detection) |
| P4 | **Graph** (embedded in Entity Detail, full-screen graph explorer) |
| P5 | (No new pages — sources managed in existing Settings) |
| P6 | **Research Chat** (dedicated page or slide-out panel) |
| P7 | **Integrations** (MCP config, webhooks, marketplace) |

---

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| LLM cost scaling with entity extraction per item | Entity extraction runs on a sampling basis (e.g., 20% of items) with full extraction only for Radar-matched or high-velocity items |
| Graph visualization performance with many nodes | Server-side graph pruning — only return 1-hop neighborhood + top N connections by strength |
| Scope creep — trying to build a Bloomberg terminal | Strict adherence to "for indie makers and small teams" — no financial data, no real-time trading, no multi-tenancy |
| Data source reliability (new sources in Phase 5) | Follow existing collector resilience patterns — graceful degradation, stale-data tolerance, fallback chains |
