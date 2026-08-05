# ADR-012: One composite opportunity score, or two independent tracks?

> **Status:** Accepted
> **Date:** 2026-08-04
> **Deciders:** Project maintainer
> **Relates to:** ADR-011 (evidence-first pipeline — Phase 2 is where this runs), ADR-003 (agent decomposition)
> **Evidence:** `docs/reviews/2026-08-04-opportunity-quality-review.md` (Q1, Q2, Q8, Q9)

## Context

Asked whether "success" means a $1k/month utility or a product that could reach $50k MRR,
the operator answered: **both — can we have both, analyzed separately?**

That is not a scope dodge; it is the correct question, and the current design cannot answer
it. Today a single composite score blends every consideration into one number:

- `agents/scorer.py:16-24` weights seven dimensions, with `market_size` at 1.5 and
  `willingness_to_pay` at 2.0.
- A4's prompt carries an `estimated_tam` dimension and a venture-analyst persona.
- A6 issues one GO/NO-GO/PIVOT verdict against a hardcoded threshold: *"if you wouldn't bet
  3 weeks of your own time on this, it's a NO-GO."*

**A single score that serves both goals is optimal for neither, and the production numbers
show exactly that failure mode:** mean 50.0, max 72.63, nothing has ever cleared the top
tier, and the GO rate is 0.0%. Blending "trivial build, tiny market" with "large market,
hard build" produces mush in the middle of the range.

The decisive insight is that **the two rubrics disagree about the same opportunity, and the
disagreement is the signal.** Worked against real output from the sample runs:

| Opportunity | As a quick win | As a scalable product |
|---|---|---|
| macOS Finder "new .txt file" | **Strong** — weekend build, clear and common pain | **Dead** — no TAM, no willingness to pay |
| AI search with clickable citations | **Weak** — hard to build, crowded | **Strong** — large market, real gap |
| Zero-config HTML/Markdown share link | **Strong** — trivial, plausibly viral | **Moderate** — freemium ceiling |

Under the current single score these collapse to 42, 64, and 56 respectively — and all
three are NO-GO. The distinction the operator most needs is precisely the one being
averaged away.

A second input: the operator has clarified that **the 2-4 week build window is a reference
value, not a hard constraint.** The current design treats it as a gate, which Q1 identifies
as the direct cause of the 0% GO rate.

## Decision Drivers

- Surface both classes of opportunity without letting either dominate the other.
- Stop penalizing small TAM universally — for a solo builder a $10-100M TAM is enormous.
- Stop rejecting on build duration; report it as a fact instead (Q9).
- Add as little LLM cost as possible.
- Keep the disagreement between the two views visible rather than resolving it silently.

## Options Considered

### Option A: One score, reweighted toward indie-scale criteria

- ✅ Smallest change — a new weight vector in `scorer.py`.
- ❌ Answers only half the operator's question; larger opportunities get suppressed instead
  of small ones.
- ❌ Reproduces the current failure in mirror image.

### Option B: One score plus a user-selectable "mode" toggle

- ✅ Single scoring path; the operator picks a lens.
- ❌ The operator must know which lens to use *before* seeing the result — but which track
  an opportunity suits is exactly what they want the system to tell them.
- ❌ Hides the disagreement, which is the most valuable output.

### Option C: Two independent tracks scored over shared dimensions

- ✅ Directly answers "can we have both."
- ✅ An opportunity can qualify for A only, B only, both, or neither — and "both" is rare
  and genuinely interesting.
- ✅ Near-zero added LLM cost: both tracks are weight vectors over one A4 dimension output.
- ❌ Two scores and two recommendations per card is more UI surface.
- ❌ Requires A4's dimension set to grow slightly (defensibility, retention) and its persona
  to become neutral.

## Decision

**Chosen: Option C — two independent assessment tracks over a shared, neutrally-scored
dimension set.** Both run in ADR-011's Phase 2.

### Track A — Quick Win

> Question: *"Can I ship this in about two weeks and reach 100 users?"*

Weights favor problem clarity, technical feasibility, distribution clarity, and time to
first user. **TAM is nearly ignored** — a $1–10M TAM is perfectly acceptable here.
Willingness to pay may be weak when build cost is near zero.

### Track B — Scalable Product

> Question: *"Could this plausibly reach $50k MRR?"*

Weights favor market size, willingness to pay, competition gap, defensibility, and
retention. **Build duration is a weak input** — 10 weeks is fine if the ceiling is high.

### Structural changes this requires

1. **A4 becomes a neutral measurer.** Its venture-analyst persona is removed; it scores
   dimensions factually with per-dimension rationales that read correctly under either
   track. Its dimension set grows to cover what Track B needs (defensibility, retention).
2. **A6 becomes the dual-track judge**, emitting a recommendation per track rather than one
   global verdict.
3. **Build duration is never a rejection reason in either track.**
   `estimated_weeks_to_mvp` is displayed as a fact. `build_complexity_from_feasibility()`
   — which derives a *time* label from a *difficulty* score — is retired (Q9).
4. **Tiers become per-track and are recalibrated** against the observed score distribution
   rather than the current unreachable ≥80 threshold (Q8). The two contradicting tier
   vocabularies in `scorer.py:29` and `api/routes/_common.py:13` collapse to one definition,
   applied twice.

## Consequences

- **Q2 resolved.** TAM stops being a universal penalty; it is heavily weighted only in
  Track B, where it belongs.
- **Q1 resolved jointly with ADR-011.** No track rejects on duration, and under ADR-011 the
  automatic path issues no verdict at all.
- **Q8 and Q9 resolved** by items 3 and 4 above.
- **Cost is essentially unchanged.** Two weight vectors over a single A4 output is
  deterministic arithmetic, not extra inference. The only added LLM cost is A4's slightly
  larger dimension set and A6 emitting two recommendations instead of one.
- **A card can now be honestly empty.** An opportunity that is neither a quick win nor
  scalable gets a low score on both tracks and says so — which is a real answer, unlike the
  current undifferentiated ~50.
- **Calibration is now measurable per track.** Once the golden set carries track labels, each
  track's thresholds can be tuned independently against it.

### Risks accepted

- **Two scores invite score-shopping** — reading whichever number is higher and ignoring the
  other. Mitigated by presenting both tracks side by side always, never a single headline
  number, and by stating the track question verbatim on the card.
- **Dimension reuse across tracks is an approximation.** Some Track A considerations (time
  to first user) and Track B considerations (retention) are not perfectly captured by a
  shared dimension set. Accepted for now; revisit if per-track calibration shows systematic
  bias.
