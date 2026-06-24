# Agent Pipeline Design

> Design philosophy and key behaviors for each of the 8 agents in the Niche Radar analysis pipeline.

---

## Pipeline Overview

```
Phase A (per item):    A1 Signal Filter → A2 Pain Extractor
Phase B (batch):       Clustering (Jaccard + LLM refinement)
Phase C (per cluster): A3 Market Researcher → A4 Opportunity Scorer → A5 Feasibility Analyst
                       → A6 Go/No-Go Judge → [A7 PRD Writer if GO] → A8 Brief Creator
Phase D:               Persist scored niches to database
```

All agents receive structured JSON context from upstream agents and return structured JSON output. Every prompt is zero-shot with embedded JSON schema examples — no fine-tuning required.

---

## A1 · Signal Filter

**Role:** Gatekeeper — drops noise cheaply before expensive downstream processing.

**Design goal:** Quickly and cheaply filter out ~90% of raw items, keeping only genuine pain signals that could be the basis for a software product. Placed first in the pipeline to save A2–A8 token costs.

**Key prompt principles:**
- Uses explicit PASS/REJECT criteria with concrete examples
- Outputs binary classification + confidence score (0.0–1.0)
- Classifies signal type: `pain_point`, `feature_request`, `competitor_complaint`, or `noise`
- Biased toward precision over recall — prefers missing a real signal over letting noise through

**Key prompt fragment:**
> "REJECT criteria (any one is enough): General opinion, rant, or political statement. Vague complaint with no actionable core. Already solved perfectly (Google, Excel, Notion, etc.)."

**Known failure cases:**
- "Buried" pain points in long posts where the real frustration is in paragraph 4
- Sarcastic or ironic complaints (especially from Twitter/X)
- Feature requests phrased as positive suggestions rather than complaints

---

## A2 · Pain Extractor

**Role:** UX researcher — extracts structured understanding of validated pain signals.

**Design goal:** Transform raw text into a structured pain profile (WHO has this problem, WHAT exactly is the friction, WHY current solutions fail) that downstream agents can reason about consistently.

**Key prompt principles:**
- Acts as a "senior UX researcher" — specific and literal, never invents details
- Extracts: who, what, when, current_workaround, why_current_sucks, desired_outcome
- Captures emotional_intensity (1–10) and willingness-to-pay signals with evidence quotes
- Generates 3–5 core keywords for clustering

**Output structure:**
```
WHO:   "freelance designers managing client feedback"
WHAT:  "feedback arrives in 5 different channels, nothing consolidated"
WHEN:  "every client revision cycle (2-3x per project)"
WHY:   "current workaround is manual copy-paste between Slack, email, and Figma comments"
```

**Why this matters:** A2's keyword output directly feeds Phase B clustering. Poor keyword extraction → poor clusters → misaligned scoring downstream.

---

## A3 · Market Researcher

**Role:** Competitive intelligence analyst — maps the existing landscape.

**Design goal:** Provide honest competitive analysis so A4 can score the competition gap accurately. Evaluates existing solutions, market maturity, and pricing dynamics.

**Key prompt principles:**
- Evaluates existing solutions with name, type (SaaS/open-source/manual), price range, and main weakness
- Identifies the market leader and the specific gap no existing solution fills
- Estimates TAM with honest uncertainty markers
- Rates saturation (1–10) to feed directly into A4's competition_gap dimension

**Output feeds:** A4 (scoring), A5 (tech stack decisions), A6 (go/no-go reasoning)

---

## A4 · Opportunity Scorer

**Role:** Venture analyst — calibrated scoring across 7 dimensions.

**Design goal:** Score each opportunity consistently on a calibrated 1–10 scale across 7 dimensions, producing a weighted 0–100 composite score. A score above 7 on any dimension should be genuinely exceptional.

**Scoring rubric:**
| Range | Meaning |
|-------|---------|
| 1–3 | Weak / disqualifying |
| 4–6 | Average / needs work |
| 7–8 | Strong |
| 9–10 | Exceptional (rare) |

**7 Dimensions** (see [README](../README.md#opportunity-scoring-dimensions) for full table):
1. Problem Clarity (weight: 1.0)
2. Market Size (weight: 1.5)
3. Willingness to Pay (weight: 2.0) — highest weight
4. Competition Gap (weight: 1.5)
5. Technical Feasibility (weight: 1.0)
6. Distribution Clarity (weight: 1.5)
7. Trend Momentum (weight: 1.0)

**Also outputs:** top 3 strengths, top 3 risks, comparable successful products

---

## A5 · Feasibility Analyst

**Role:** Experienced indie developer — ruthlessly practical build assessment.

**Design goal:** Determine whether a solo developer can build and launch an MVP in 2–4 weeks. Outputs concrete tech stack, feature scope, and distribution strategy — not theoretical analysis.

**Key prompt principles:**
- Persona: "experienced indie developer who has shipped multiple solo SaaS products"
- Forces realism: "Most ideas take 2-3x longer than expected"
- Requires explicit MVP scope AND explicit out-of-scope list
- Outputs feasibility_score (1–10) and solo_buildable boolean
- Maps to build_complexity (1–5) displayed in the UI

**Build complexity mapping:**
| Feasibility (1–10) | Complexity Label |
|---------------------|-----------------|
| 9–10 | ⏱ Weekend Build |
| 7–8 | ⏱ 2–3 Day Build |
| 5–6 | ⏱ ~1 Week Build |
| 3–4 | ⏱ 1–2 Week Build |
| 1–2 | ⏱ 2+ Week Build |

---

## A6 · Go/No-Go Judge

**Role:** Decisive entrepreneur — the final filter.

**Design goal:** Make a binary decision: would you personally spend 3 weeks building this? Outputs GO, NO-GO, or PIVOT with clear rationale.

**Key prompt principles:**
- Persona: "decisive, experienced entrepreneur who has built and sold multiple software companies"
- Threshold: "if you wouldn't bet 3 weeks of your own time, it's a NO-GO"
- Must state the killer risk — the single thing most likely to cause failure
- PIVOT verdict requires a concrete repositioning suggestion
- Provides `conditions_to_reconsider` — what would flip the verdict

**Verdict definitions:**
| Verdict | Meaning |
|---------|---------|
| 🟢 GO | Build this now. Clear gap, reachable users, monetizable. |
| 🔴 NO-GO | Don't build this. Killer reason stated clearly. |
| 🟡 PIVOT | Core insight valid but needs repositioning. Pivot described. |

**A6 controls the pipeline flow:** A7 (PRD) only runs on GO verdicts. A8 (Brief) always runs.

---

## A7 · PRD Writer

**Role:** Product manager — generates a lean PRD for immediate building.

**Runs only when:** A6 verdict = GO

**Design goal:** Produce a concise, actionable PRD that a solo developer can start building from immediately. Not a Series A product spec — a 2–4 week build plan.

**Output includes:**
- Product name + one-liner elevator pitch
- Target user persona (specific, not generic)
- 3–5 MVP features with user stories and acceptance criteria (P0/P1 tagged)
- Explicit out-of-scope list (prevents scope creep)
- 3 success metrics with concrete numbers
- Monetization model with pricing
- 30-day launch plan (build → users → revenue milestones)

---

## A8 · Brief Creator

**Role:** Investment analyst — 60-second opportunity summary.

**Always runs** — for GO, NO-GO, and PIVOT verdicts.

**Design goal:** Synthesize all upstream analysis into a tight one-pager that an angel investor or solo founder can read in 60 seconds to decide if they want to dig deeper.

**Output includes:**
- Title + verdict badge
- TL;DR (2 sentences, "a 10-year-old could understand")
- The Pain / The Gap / The User / The Money (1 sentence each)
- Composite scores (pain intensity, opportunity score, feasibility, confidence)
- Top reason to do it / Top reason not to
- "If I were to start today" — concrete first step
- Similar successes for social proof

---

## Design Principles (All Agents)

1. **Structured JSON only** — every agent returns parseable JSON, no prose
2. **Null over hallucination** — if a field can't be determined, output null
3. **Calibrated scoring** — 9-10 is genuinely rare; most scores should be 4-7
4. **Upstream context** — each agent receives relevant upstream outputs as structured context
5. **Partial failure tolerance** — if an upstream agent fails, downstream agents still run with "unknown" substituted for missing values
