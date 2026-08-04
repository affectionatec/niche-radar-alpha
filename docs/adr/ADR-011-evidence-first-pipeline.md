# ADR-011: Should A3–A8 run automatically on every cluster, or on demand?

> **Status:** Accepted
> **Date:** 2026-08-04
> **Deciders:** Project maintainer
> **Relates to:** ADR-003 (eight-agent pipeline — amended, not superseded), ADR-012 (dual-track assessment)
> **Evidence:** `docs/reviews/2026-08-04-opportunity-quality-review.md` (Q1, Q3, Q7, Q10, Q12)

## Context

The pipeline has been running in production for 1,530 collection cycles. Measured state
on 2026-08-04:

- 3,650 raw items → 207 niche candidates.
- **0 GO / 10 PIVOT / 197 NO-GO. GO rate 0.0%.**
- Score distribution: mean 50.0, max 72.63. The UI's top tier (≥80) has never been reached.
- A1 precision 26.1% (n=48) — roughly three of four items entering Phase C are junk.

The operator's report that triggered this review: *"the opportunities aren't reasonable —
very few are things you could actually build as an app or a website."*

Two structural facts explain the outcome:

1. **The judgment layer's entire output is "no."** Six LLM agents (A3–A8) run on every
   cluster, and after 207 attempts have never produced an actionable "build this." A
   system that only ever says no carries no decision value — the operator cannot act on
   197 rejections, so in practice they ignore the verdicts entirely.

2. **The evidence-to-speculation ratio is inverted.** Each niche card rests on roughly one
   sentence of real quoted text, on top of which six agents stack confident invention. A3's
   own system prompt says *"analyze the existing market landscape **based on your
   knowledge**"* — its competitors, TAM, pricing, and saturation scores are unverified
   model recall presented as research. Compounding this, F7 shows a bot-challenge network
   failure being recorded as `validated_gap`.

The first-principles observation: **the current design automates the part the operator is
good at (judging a well-evidenced opportunity) and under-invests in the part they cannot do
at all (reading 3,650 posts to find the ones that repeat).** The operator's real bottleneck
was never "I can't tell if this idea is good." It is "I can't read the whole web."

## Decision Drivers

- The operator must receive something they can act on, not a wall of rejections.
- Real evidence must outweigh generated speculation in what gets presented.
- LLM speculation, when present, must be clearly marked as such and deliberately requested.
- Cost should scale with the operator's attention, not with corpus size.
- Do not discard A3–A8 — the agents are well built; the problem is *when* they run.

## Options Considered

### Option A: Keep the current design, fix the rubrics

- ✅ Smallest change; A1/A2/clustering and the UI's object model stay as they are.
- ✅ Addresses Q1/Q2 directly (retune A6's gate and A4's weights).
- ❌ Leaves the evidence/speculation inversion untouched — every card still carries six
  layers of invention over one quote.
- ❌ Still spends ~74% of Phase-C tokens polishing A1 false-passes.
- ❌ Retuning a rubric that has said "no" 207 times is very likely to produce a rubric that
  says "yes" to the wrong things, because the underlying evidence is still thin.

### Option B: Delete A3–A8; ship raw clusters only

- ✅ Maximum honesty — nothing is presented that wasn't collected.
- ✅ Cheapest possible pipeline.
- ❌ Throws away genuinely useful work. When the operator *has* chosen a direction, a
  competitor sketch and a lean PRD are valuable.
- ❌ Wastes the eight-agent investment ADR-003 justified.

### Option C: Split at the evidence/judgment boundary — automatic discovery, on-demand deep dive

- ✅ The automatic path presents only measured facts; no verdict can be wrong because none
  is issued.
- ✅ A3–A8 survive intact, invoked deliberately on a cluster the operator has already
  judged interesting.
- ✅ Phase-C cost leaves the per-cycle path entirely — it scales with operator attention
  (a few deep dives per week) rather than corpus size (16–31 clusters per cycle).
- ✅ Dissolves rather than patches several findings (see Consequences).
- ❌ The operator now does the judging. If they wanted a magic ranked shortlist, this is
  strictly more work for them.
- ❌ Requires a frontend change: the primary object becomes an Evidence Cluster, not a
  scored opportunity.

## Decision

**Chosen: Option C — split the pipeline at the evidence/judgment boundary.**

### Phase 1 — Discovery (automatic, every cycle)

```
collect → A1 (signal + form-factor gate) → A2 (pain extraction) → clustering → Evidence Cluster
```

No verdict. No composite score. No market analysis. No PRD. Phase 1 persists and presents:

- the cluster's member quotes, verbatim, each with its source link and timestamp;
- **distinct author count** and **distinct source count** (not raw item count — see Q3);
- first-seen / last-seen dates and cross-window recurrence;
- A2's per-item structured pain (which is extraction, not invention).

### Phase 2 — Deep dive (on demand, operator-triggered, one cluster at a time)

```
A3 → A4 → A5 → A6 → A7 → A8, dual-track per ADR-012
```

Runs only when the operator selects a cluster. Its output is labeled in the UI as LLM
assessment, visually distinct from Phase 1 evidence.

### Ranking in Phase 1

Phase 1 output is ranked by an **evidence score built only from counted quantities** —
distinct authors, distinct sources, recurrence across time windows, recency, and A2's
per-item pain intensity. No dimension of this ranking is an LLM opinion. This is what makes
the ordering defensible: every component can be traced to something that was actually
collected.

## Consequences

### Findings this dissolves rather than patches

- **Q1 (0% GO rate / rejection machine)** — no automatic verdict exists, so there is nothing
  to be systematically wrong. The operator is the verdict.
- **Q3 (Frankenstein cluster merge)** — Phase 1 displays members individually, so no
  field-wise merge is needed for presentation at all. When Phase 2 runs, A3–A8 receive the
  **full member list** rather than a longest-string chimera. `aggregate_cluster_a2()`'s
  merge-by-longest-string is retired, not repaired.
- **Q7 (unverified market intel)** — contained to Phase 2, requested deliberately, labeled
  as speculation. F7's `validated_gap` bug must still be fixed, but its blast radius shrinks
  from every card to only deep dives.
- **Q12** — this ADR *is* the resolution of Q12.

### Cost

Per-cycle LLM budget drops from `2N + 10C + 50` to approximately `2N + clustering`. Phase C
was 6 of the 8 agents and the bulk of per-cluster spend; it leaves the automatic path.
Measured baseline for comparison: $0.0358/cycle with Phase C running on 16 clusters.

### Costs and risks accepted

- **The operator does the judging.** Mitigated by ranking on measured evidence strength, so
  the top of the list is where real recurrence is, not where an LLM was most enthusiastic.
- **Frontend rework.** The dashboard's primary object changes from scored opportunity to
  Evidence Cluster. Niche detail gains a "run deep dive" action and a clear
  evidence-vs-assessment visual split.
- **Storage/schema change.** Clusters must persist as first-class records with their
  members and provenance, independent of whether a deep dive has run.
- **ADR-003 is amended, not superseded.** The eight-agent decomposition, structured Pydantic
  I/O, and partial-failure tolerance all stand. What changes is the *invocation model* for
  A3–A8: automatic-on-every-cluster becomes on-demand-per-cluster. ADR-003's cost argument
  (A1 as cheap gatekeeper, clustering before A3–A8) is strengthened, not weakened.

### Follow-on work this implies

Sequencing and task breakdown live in
`docs/reviews/2026-08-04-opportunity-quality-review.md` §4. This ADR does not schedule them.
