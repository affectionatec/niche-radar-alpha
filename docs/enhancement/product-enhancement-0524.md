# Niche Radar Alpha — Product Enhancement Plan

> Detailed enhancement roadmap for `affectionatec/niche-radar-alpha`
> Assessment date: 2026-05-24
> Current assessment: 7.5 / 10 (above average for alpha stage)

---

## Table of Contents

1. [Priority Overview](#priority-overview)
2. [P0 — Trust & Credibility Issues](#p0--trust--credibility-issues)
3. [P1 — Engineering Robustness](#p1--engineering-robustness)
4. [P2 — Growth & Differentiation Opportunities](#p2--growth--differentiation-opportunities)
5. [Recommended Execution Order](#recommended-execution-order)

---

## Priority Overview

| Priority | Issue | Impact Area | Effort Estimate |
|----------|-------|-------------|-----------------|
| **P0** | Scoring dimensions are a black box (7 dimensions, 0–100) | User trust | 1–2 days |
| **P0** | No dashboard demo / screenshots | User conversion | Half day |
| **P0** | Agent prompts are opaque | Product differentiation | 2–3 days |
| **P1** | HTML scraping fragility not disclosed | Expectation management | Half day |
| **P1** | Jaccard + LLM clustering decisions unexplained | Technical credibility | 1 day |
| **P1** | No cost estimation tool | Operational cost awareness | 1–2 days |
| **P2** | No hosted version / monetization path | Long-term growth | 2–4 weeks |
| **P2** | Pipeline output hard to compare / A/B test | Product iteration speed | 1 week |
| **P2** | No prompt override mechanism | Power-user retention | 3–5 days |

---

## P0 — Trust & Credibility Issues

These issues share a common trait: **they cause potential users to churn on first contact, or lose trust after a few uses.**

### P0.1 Scoring Dimensions Are a Black Box

#### Problem

The README states "Opportunity Scorer · 7 dimensions · 0–100" but never explains what those 7 dimensions are. When a user sees a niche scored at 78, they cannot determine:

- What does this score represent?
- Why is this 78 higher than another niche's 65?
- Can I adjust the weights based on my preferences?

#### Impact

- **Trust gap**: Users cannot verify whether scores are reasonable — they suspect the LLM is hallucinating
- **Decision paralysis**: Two niches with similar scores — no way to differentiate
- **No feedback loop**: Users can't say "I think this dimension is scored too high"

#### Proposed Changes

**1. Add a scoring dimensions table to the README:**

```markdown
### Opportunity Scoring Dimensions

| Dimension | Weight | What It Measures |
|-----------|--------|------------------|
| Market Size | 20% | TAM/SAM estimation from market signals |
| Pain Intensity | 18% | How acute the user pain is (verbatim quote analysis) |
| Willingness to Pay | 15% | Evidence of users paying for similar solutions |
| Competition Gap | 15% | How underserved the niche currently is |
| Build Feasibility | 12% | Technical complexity to MVP |
| Distribution Difficulty | 10% | How hard it is to reach this audience |
| Defensibility | 10% | Moat potential (network effects, data, IP) |
```

**2. Break down the total score into a dimension bar chart on the Niche Detail page:**

```
Total: 78/100

  Market Size       ████████░░ 82
  Pain Intensity    █████████░ 91
  Willingness Pay   ██████░░░░ 65
  Competition Gap   ████████░░ 80
  Build Feasibility █████████░ 90
  Distribution      ████░░░░░░ 45  ← dragging the score down — clearly labeled
  Defensibility     ███████░░░ 72
```

**3. Allow users to customize scoring weights in Settings:**

```yaml
# scoring_weights.yaml
market_size: 0.20
pain_intensity: 0.18
willingness_to_pay: 0.15
competition_gap: 0.15
build_feasibility: 0.12
distribution: 0.10
defensibility: 0.10
# Users can adjust based on preference — e.g., indie devs raise build_feasibility
```

#### Acceptance Criteria

- [ ] README lists all 7 dimensions with names, weights, and definitions
- [ ] Niche Detail page displays per-dimension sub-scores
- [ ] Settings provides weight customization (at minimum via YAML config)

---

### P0.2 No Dashboard Demo or Screenshots

#### Problem

The entire README has zero dashboard screenshots. For a tool whose core value proposition is "delivers scored niches through a web dashboard," this is a critical content gap.

#### Impact

- Most GitHub visitors won't clone and `docker compose up` just to see what it looks like
- The conversion funnel leaks at the very first step
- Even technical users default to seeing the visual result before investing time to deploy

#### Proposed Changes

**1. Add 3 screenshots to the README `## Dashboard` section:**

- Home page (system health overview)
- Niches list page (with scores and verdicts)
- Niche Detail page (score breakdown + PRD preview)

**2. Record a 30-second GIF or Loom video and place it at the top of the README:**

```markdown
# Niche Radar

![Demo](docs/images/demo.gif)

> 30-second walkthrough — from collection to scored niche
```

**3. Deploy a read-only public demo:**

Use fly.io free tier with a fixed demo database snapshot, allowing users to try `demo.niche-radar.com` without deploying.

**4. Prepare "Sample Niche Report" documents:**

Place real output samples from A7 (PRD Writer) and A8 (Brief Creator) in `docs/sample-reports/`. This lets users judge output quality without running the pipeline.

#### Acceptance Criteria

- [ ] README header has a GIF or video demo
- [ ] Dashboard section has at least 3 screenshots
- [ ] `docs/sample-reports/` contains at least 2 complete output samples

---

### P0.3 Agent Prompts Are Completely Opaque

#### Problem

The 8 agents' prompts can only be understood by reading source code (`niche_radar/agents/prompts.py`). For an LLM-heavy tool, prompt quality = product quality, but users cannot assess this core value from the README.

#### Impact

- Technical evaluators cannot quickly judge if this tool is "serious"
- Users cannot understand why a particular niche was judged NO-GO
- The opportunity to use prompt design itself as a differentiator is lost

#### Proposed Changes

**1. Publish each agent's design philosophy in `docs/AGENTS.md`:**

```markdown
## A1 · Signal Filter

### Design Goal
Cheaply and quickly filter out 99% of noise, keeping only genuine pain signals.
Placed first in the pipeline to save A2–A8 token costs.

### Prompt Design Principles
- Uses few-shot examples to distinguish "real pain" from "noise"
- Outputs binary classification + confidence score for downstream decisions
- Avoids hallucination: prefers missing a real signal over letting noise through

### Key Prompt Fragment
> "Real pain signals contain: specific frustration, time/money loss,
>  attempted workarounds. Noise contains: vague complaints,
>  marketing language, hypothetical scenarios."

### Known Failure Cases
- "Buried" pain points in long posts (mitigation: summarize before A1)
- Sarcastic pseudo-pain signals (e.g., ironic Twitter/X rants)
```

**2. Add a "Why this verdict?" button on the dashboard:**

When clicked, it shows the full agent chain:

```
A1 Signal Filter: PASS (confidence 0.89)
  → "User mentioned 'I've been struggling with X for 6 months' multiple times"

A2 Pain Extractor:
  WHO: ME/CFS patients
  WHAT: Cannot plan daily routines with existing scheduling tools
  WHY: Brain fog causes excessive cognitive load

A6 Go/No-Go Judge: NO-GO
  → Primary reason: A4 gave Distribution a score of only 23
  → Triggered rule: Distribution < 30 forces NO-GO or PIVOT
```

**3. Allow users to override default prompts (advanced feature):**

```python
# niche_radar/agents/prompts/custom/A6_judge.txt
# User-customized version — pipeline reads this first
# For users who want stricter / more lenient GO criteria
```

#### Acceptance Criteria

- [ ] `docs/AGENTS.md` documents the design logic of all 8 agents (full prompts not required)
- [ ] Dashboard has "Why this verdict" agent-chain visualization
- [ ] Settings provides a prompt override mechanism (at minimum file-level)

---

## P1 — Engineering Robustness

These issues won't cause immediate user churn, but will lead to frustration over long-term use.

### P1.1 HTML Scraping Fragility Not Disclosed

#### Problem

6 of the 12 data sources rely on HTML scraping:

- Product Hunt
- G2 Reviews
- Indie Hackers
- App Store
- Play Store
- GitHub Trending

Any of these sites could redesign at any time, breaking the scraper. Users running the tool for a while suddenly find "Why did G2 data stop?" — a terrible experience.

#### Impact

- Users perceive the tool as unstable
- No way to know which sources are reliable vs. which need caution
- No expectation of graceful degradation

#### Proposed Changes

**1. Add a reliability column to the README data sources table:**

```markdown
| Source | Method | Reliability | Notes |
|--------|--------|-------------|-------|
| Reddit | PRAW (official API) | 🟢 Stable | Official API, long-term reliable |
| Hacker News | Firebase + Algolia API | 🟢 Stable | Official API |
| Stack Overflow | Official API | 🟢 Stable | Official API |
| Twitter / X | GraphQL API | 🟡 Fragile | Relies on cookie auth; X changes frequently |
| YouTube | scrapetube | 🟡 Fragile | Unofficial library, may break |
| Google Trends | trendspyg | 🟡 Fragile | Unofficial library |
| GitHub Trending | HTML scraping | 🟠 Brittle | Static page; breaks when structure changes |
| Product Hunt | HTML scraping | 🟠 Brittle | Medium redesign risk |
| Indie Hackers | HTML scraping | 🟠 Brittle | Small site, infrequent redesigns |
| G2 Reviews | HTML scraping | 🔴 Very Brittle | Frequent anti-scraping measures |
| App Store | HTML scraping | 🔴 Very Brittle | Strong anti-scraping |
| Play Store | HTML scraping | 🔴 Very Brittle | Strong anti-scraping |
```

**2. Add a "Source Health" dashboard on the Home page:**

```
Source Health (last 24h)

  Reddit          ✅ 1,234 items collected
  HackerNews      ✅ 567 items collected
  Twitter         ⚠️  0 items — auth may have expired
  Product Hunt    ❌ Last success: 3 days ago — scraper likely broken
  G2 Reviews      ❌ Last success: 7 days ago — needs maintenance
```

**3. Build scraper health monitoring + auto-alerting:**

```python
# niche_radar/collectors/health_check.py
class CollectorHealthMonitor:
    def check_collector(self, name: str) -> HealthStatus:
        last_success = self.repo.get_last_success(name)
        expected_interval = self.config.collection_interval_hours

        if last_success > expected_interval * 3:
            return HealthStatus.BROKEN
        elif last_success > expected_interval * 2:
            return HealthStatus.DEGRADED
        return HealthStatus.HEALTHY
```

#### Acceptance Criteria

- [ ] README data sources table includes a reliability column
- [ ] Dashboard has a Source Health view
- [ ] Dashboard highlights broken scrapers (failures exceed N threshold) in red

---

### P1.2 Jaccard + LLM Clustering Decisions Unexplained

#### Problem

The `Clustering · Jaccard + LLM refinement` step is one of the most technically sophisticated design choices in the entire pipeline, yet the README says nothing about it. Technical evaluators will ask:

- Why not sentence embedding + cosine similarity?
- Why not HDBSCAN?
- What's the Jaccard threshold? How do I tune it?
- What exactly does LLM refinement do?

#### Impact

- Technical credibility is undermined
- The opportunity to showcase engineering depth is lost
- Users don't know how to tune the system

#### Proposed Changes

**1. Add a clustering design section to `docs/ARCHITECTURE.md`:**

```markdown
## Clustering Strategy

### Why Jaccard + LLM Instead of Embeddings?

We evaluated three alternative approaches:

| Approach | Pros | Cons | Adopted? |
|----------|------|------|----------|
| Pure embedding (cosine sim) | Semantically sensitive | Requires embedding API calls, higher cost | ❌ |
| Pure Jaccard on keywords | Extremely fast, zero cost | Insensitive to synonyms | ❌ |
| HDBSCAN on embeddings | No need to specify k | Unstable on small datasets | ❌ |
| **Jaccard + LLM refinement** | Cheap fast filtering + semantic calibration | Higher implementation complexity | ✅ |

### Two-Phase Process

Phase 1: Jaccard fast bucketing
- Extract keyword sets from each pain point
- Compute pairwise Jaccard similarity
- threshold = 0.3 to form initial clusters

Phase 2: LLM refinement
- Call LLM on each cluster asking:
  "Are these pain points really the same problem?"
- LLM can split over-merged clusters
- LLM can merge semantic siblings that Jaccard missed

### Cost Comparison (1,000 items)

| Approach | LLM Tokens | Time |
|----------|-----------|------|
| Pure embedding | ~50K (embedding) + 0 | ~2 min |
| Pure LLM clustering | ~500K | ~15 min + $$$ |
| **Jaccard + LLM** | ~80K (only on clusters) | ~4 min |
```

**2. Expose Jaccard threshold as a configurable parameter:**

```python
# .env
CLUSTERING_JACCARD_THRESHOLD=0.3
CLUSTERING_LLM_REFINEMENT_ENABLED=true
CLUSTERING_MIN_CLUSTER_SIZE=2
```

#### Acceptance Criteria

- [ ] `docs/ARCHITECTURE.md` includes a complete clustering design explanation
- [ ] Key parameters are exposed as environment variables / Settings config

---

### P1.3 No Cost Estimation Tool

#### Problem

After configuring an LLM provider, users have no way to estimate daily or monthly costs. For a self-hosted tool, this is critical operational information.

#### Impact

- Users are afraid to run the tool long-term after initial setup
- No guidance on whether `deepseek-v4-flash` or `gpt-5.2` is more cost-effective
- Unexpected bills get blamed on the tool

#### Proposed Changes

**1. Add a cost estimator to the Settings page:**

```
LLM Cost Estimator (based on last 7 days)

Current setup: deepseek-v4-flash
  Avg tokens per analysis run: 245,000
  Cost per run: $0.12
  Runs per day: 4 (every 6h)
  Estimated monthly cost: $14.40

What if you switched to gpt-5.2?
  Estimated monthly cost: $187.50 (13x more expensive)

What if you switched to claude-opus-4-7?
  Estimated monthly cost: $342.00 (24x more expensive)

What if you used Ollama locally?
  Estimated monthly cost: $0 (but ~3x slower)
```

**2. Record token usage for every LLM call in the database:**

```python
# niche_radar/storage/models.py
class LLMUsage(Base):
    __tablename__ = "llm_usage"

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_name: Mapped[str]  # A1, A2, ...
    model: Mapped[str]
    prompt_tokens: Mapped[int]
    completion_tokens: Mapped[int]
    cost_usd: Mapped[float]
    timestamp: Mapped[datetime]
    pipeline_run_id: Mapped[int]
```

**3. Add a "Cost Insights" page to the dashboard:**

Shows which agent burns the most tokens and where optimization opportunities exist:

```
Cost Breakdown (last 30 days, $14.40 total)

  A2 Pain Extractor    ████████░░  42%  $6.05
  A3 Market Researcher ██████░░░░  28%  $4.03
  A7 PRD Writer        ████░░░░░░  18%  $2.59
  A4 Opportunity Score ██░░░░░░░░   8%  $1.15
  Others               █░░░░░░░░░   4%  $0.58

💡 Optimization tip: A2 Pain Extractor accounts for 42% of total cost.
   Consider strengthening A1 filtering to reduce the number of items reaching A2.
```

#### Acceptance Criteria

- [ ] LLM usage is recorded in the database
- [ ] Settings page has a cost estimator
- [ ] Dashboard has a Cost Insights view

---

## P2 — Growth & Differentiation Opportunities

These issues don't affect the core product experience, but they determine whether the product can evolve from alpha to a commercial offering.

### P2.1 No Hosted Version / Monetization Path

#### Problem

The tool is currently 100% self-hosted. This means:

- Users must have Docker knowledge
- Users must have a server or always-on machine
- Users must manage their own LLM API keys

For users who "want to see niches but don't want to self-host," the tool is inaccessible.

#### Monetization Path Proposals

**Path A: Hosted SaaS (Recommended)**

```
Free tier:
  - 3 data sources
  - 1 analysis run per week
  - BYOK (Bring Your Own Key)

Pro ($29/mo):
  - All 12 data sources
  - 1 analysis run per day
  - LLM costs included
  - Email / Slack notifications

Team ($99/mo):
  - Shared shortlist across team members
  - API access
  - Custom scoring weights
  - Custom prompts
```

**Path B: Data Subscription (Low-Ops)**

Sell the output, not the tool — a weekly digest:

- $19/mo — weekly email with top 10 niches
- $49/mo — includes PRD-level detail
- $99/mo — includes raw data source links + raw items

**Path C: Open Source + Paid Plugins**

Keep the open-source core as-is; monetize with paid extensions:

- Premium data sources (LinkedIn, TikTok, Discord)
- Premium agents (industry-expert prompt packs)
- Integrations (push to Notion, Linear, Asana)

#### Recommendation: Start with Path B to Validate PMF

Rationale:

- No architecture rewrite needed
- Leverages existing pipeline — just add a mailing layer
- Early stage can use manual curation to boost quality
- Validates whether users will pay for niche intelligence

---

### P2.2 Pipeline Output Hard to Compare / A/B Test

#### Problem

If you modify A4 (Opportunity Scorer)'s prompt, how do you know the new version is better? Currently there is no mechanism for comparison.

#### Impact

- Prompt iteration is based on gut feel, not data
- Output quality across different LLM providers can't be quantitatively compared
- Long-term, pipeline quality cannot be systematically improved

#### Proposed Changes

**1. Introduce pipeline run versioning:**

```python
class PipelineRun(Base):
    id: Mapped[int]
    started_at: Mapped[datetime]
    pipeline_version: Mapped[str]  # "v1.3.2"
    prompt_hash: Mapped[str]  # Combined hash of all 8 agent prompts
    model: Mapped[str]
    input_item_ids: Mapped[list[int]]  # JSON
    output_niches: Mapped[list[int]]  # JSON
```

**2. Provide a "Re-analyze with new config" feature:**

Allow users to select a set of historical items and re-run them with new prompts / models, comparing results side by side.

**3. Build an evaluation set:**

```python
# niche_radar/eval/golden_set.py
# Maintain 50–100 manually annotated items
# Run eval after every prompt change to track accuracy

GOLDEN_SET = [
    {
        "item_id": "reddit_xyz_123",
        "expected_a1_pass": True,
        "expected_a6_verdict": "GO",
        "expected_a4_score_range": (70, 85),
    },
    # ...
]
```

---

### P2.3 No Prompt Override Mechanism

#### Problem

Different industries and users have different definitions of a "good niche":

- Indie developers want high build feasibility
- VCs want large market size
- Service-industry practitioners want easy distribution

But the current prompts are hardcoded with no way to customize per scenario.

#### Proposed Changes

**1. Provide a "prompt pack" mechanism:**

```yaml
# prompt_packs/indie_hacker.yaml
description: "Niche evaluation tuned for indie developers"
overrides:
  A4_opportunity_scorer:
    weight_overrides:
      build_feasibility: 0.25  # Significantly raised
      market_size: 0.10  # Lowered (don't need a large market)
  A6_judge:
    rules:
      - "If monthly revenue potential > $5,000 but < $50,000, lean GO"
      - "If external funding is required to start, lean NO-GO"

# prompt_packs/vc_scout.yaml
description: "Niche evaluation tuned for VC scouts"
overrides:
  A4_opportunity_scorer:
    weight_overrides:
      market_size: 0.30
      defensibility: 0.20
  A6_judge:
    rules:
      - "TAM < $100M → automatic NO-GO"
```

**2. Let the dashboard switch between prompt packs:**

Allow users to view the same data set through different evaluation lenses. This is a differentiation feature in itself.

---

## Recommended Execution Order

Ordered by ROI (return on investment):

### Week 1: Credibility Emergency Kit

- [x] **P0.2** — Add dashboard screenshots + GIF (half day — immediate conversion uplift)
- [x] **P0.1** — Publish 7 scoring dimensions (1 day — immediate trust boost)
- [x] **P1.1** — Add reliability labels to README data sources (half day — manage expectations)

**Expected outcome**: Noticeable increase in GitHub stars; higher-quality issues filed.

### Weeks 2–3: Product Depth

- [ ] **P0.3** — Publish agent design + agent-chain visualization on dashboard (2–3 days)
- [ ] **P1.2** — Clustering design documentation (1 day)
- [ ] **P1.3** — Cost estimation tool (1–2 days)

**Expected outcome**: Upgrade from "looks like a nice tool" to "this is a serious tool." PR contributions and partnership inquiries begin.

### Weeks 4–6: Monetization Exploration

- [ ] **P2.1** — Launch weekly digest email (Path B monetization)
- [ ] **P2.3** — Ship 2–3 prompt packs
- [ ] **P2.2** — Build golden set + eval pipeline

**Expected outcome**: First paying user acquired; PMF validated.

---

## Summary

> The engineering foundation of this project is solid. **What determines how far it goes is not technology, but the degree to which users can trust it.**
> The three P0 issues are fundamentally transparency problems — letting users see your reasoning process matters more than making the pipeline score more accurately.

---

*Document version: v1.0*
*Based on: [github.com/affectionatec/niche-radar-alpha](https://github.com/affectionatec/niche-radar-alpha) (commit at 2026-05-24)*