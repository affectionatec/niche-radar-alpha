# Opportunity-Quality First-Principles Review — 2026-08-04

> Status: **Review document. Nothing implemented yet.** This records diagnosis and a
> change list only, to be split into tasks and executed later.
> **Update 2026-08-04:** the operator has answered all four open questions (§6). Two
> required architectural decisions, now recorded as **ADR-011** (evidence-first pipeline)
> and **ADR-012** (dual-track assessment). **The roadmap has been re-derived in §7; §4 is
> superseded.** Still no code changed — documentation-first by the operator's request.
> Trigger: the operator reported that pipeline output "isn't reasonable — very few are
> things you could actually build as an app or a website."
> Method: read the full chain, then cross-check every conclusion against the **live
> production instance** (`radar.originbase.org`) rather than against documentation.
> Predecessors: `docs/reviews/2026-07-03-first-principles-review.md` (engineering quality),
> `docs/sample-reports/2026-07-04-run-metrics.md` (runtime defects F1–F11).
> This review numbers findings **Q#** — no collision with F#; overlaps are marked explicitly.

---

## 1. Conclusion (TL;DR)

**The machine is well built. It is aimed at the wrong target.**

The July review concluded this was "a finely engineered engine that had never been
ignited." It has since been ignited: 1,530 collection cycles, 3,650 raw items, 207 niche
candidates. **The problem is now that all of that thrust points the wrong way.**

The single most damning number from production:

> **207 niches: 0 GO, 10 PIVOT, 197 NO-GO. GO rate = 0.0%.**

An opportunity-discovery system that has run 1,530 cycles and has never once said "build
this" **has zero decision value**. The operator cannot act on it; they receive 207
rejections.

The root cause is not prompt wording. It is four structural decisions:

1. **The judging rubric answers a different question than the operator's** (Q1/Q2) — A6
   hardcodes "if it doesn't fit in 3 weeks, NO-GO"; A4 measures indie projects with a VC's
   TAM ruler.
2. **Aggregation is a stitched-together artifact, and `occurrence_count` is misleading**
   (Q3/Q4) — newly discovered here, and it destroys the product's core value proposition.
3. **Nothing anywhere in the chain asks whether the thing can be a website or an app**
   (Q5) — hardware shopping, account support, and government paperwork all pass through.
4. **The corpus is dominated by the wrong source** (Q6) — the best-designed collector (HN)
   yields 2 items live.

### What was decided (2026-08-04)

The operator resolved all four open questions the same day (§6). The two structural answers:

- **Evidence-first is adopted (ADR-011).** The pipeline splits at the evidence/judgment
  boundary: Phase 1 (automatic, every cycle) collects, gates, extracts, and clusters, then
  presents **measured evidence only** — verbatim quotes with links, distinct-author counts,
  recurrence. Phase 2 (A3–A8) runs **on demand** on a cluster the operator selects. The
  machine does the reading; the operator does the judging.
- **Assessment becomes dual-track (ADR-012).** "Quick Win" and "Scalable Product" are scored
  independently over shared dimensions, because the two rubrics disagree about the same
  opportunity and *that disagreement is the signal* the current single score averages away.

Consequently **§4's roadmap is superseded by §7** — evidence-first dissolves several
findings rather than fixing them (notably Q3, whose aggregation bug is retired rather than
repaired).

---

## 2. Live Evidence (2026-08-04, production instance)

Pulled via `/api/auth/login` → `/api/status` + `/api/niches`.

### 2.1 Scale

| Metric | Value |
|---|---|
| raw_items | 3,650 |
| active_niches | 207 |
| collection_cycle | 1,530 |
| last_collection | 2026-08-04 01:21:07 |

### 2.2 Verdict distribution ← core evidence

| verdict | count | share |
|---|---:|---:|
| NO-GO | 197 | 95.2% |
| PIVOT | 10 | 4.8% |
| **GO** | **0** | **0.0%** |

### 2.3 Scores and tiers

- llm_score: max **72.63** · mean **50.0** · min 22.63; only 3 are ≥70, 29 are ≥60.
- tier: `archive` **196** · `watchlist` **11** · `high_priority` **0**.

> The UI files 95% of its own output under "archive", and its top tier `high_priority`
> (threshold ≥80) **has never been reached by anything** (all-time max 72.63).

### 2.4 Aggregation distribution

| occurrence_count | 1 | 2 | 3 | 4 | 5 | 6 | 7+ |
|---|---:|---:|---:|---:|---:|---:|---:|
| niches | 111 | 33 | 21 | 15 | 6 | 13 | 8 |

Singletons are 53.6%. **Note: the 96 with ≥2 do not represent "96 needs validated by
multiple people" — see Q3.**

### 2.5 Source health (live, current)

| Status | Sources |
|---|---|
| OK, producing | youtube 80 · v2ex 49 · github 16 · google_trends 10 · linkedin 7 · hn **2** |
| OK, zero items | stack_overflow |
| PARTIAL / zero | reddit (`required_missing: client_id, client_secret`) · g2_reviews · indie_hackers · bilibili |
| FAILED | product_hunt · app_store · play_store · xueqiu |
| MISSING (unconfigured) | twitter · bluesky · tiktok · instagram · threads · exa · xiaohongshu · xiaoyuzhou |

**23 sources, 6 producing, 2 (v2ex/hn) yielding genuine pain signal — unchanged since July.**

---

## 3. Findings

### 🔴 Fatal (destroys product value directly)

---

#### Q1 — The judge is a rejection machine: 0% GO rate

**Evidence:** 0/207 GO live. `agents/prompts.py`, A6 system prompt, hardcoded:

> *"Your threshold: if you wouldn't bet 3 weeks of your own time on this, it's a NO-GO."*

A5 separately emits `estimated_weeks_to_mvp` (1–12). Across the sample reports, NO-GO
rationales are overwhelmingly dominated by one sentence: *"MVP takes 5/6/8/10 weeks,
exceeding the 2-4 week window."*

**Problem:** the system is not filtering out *bad opportunities* — it filters out *things
that don't fit in three weeks*. Those are not the same thing. And the 2-4 week window is
**baked into the prompt**, so the operator cannot change it.

**Direction:** separate the time budget from the **verdict**; surface it as its own field
and make the window configurable. The verdict should answer "is this worth building",
not "does this fit in three weeks".

---

#### Q2 — A4 is a VC scorecard applied to an indie-builder goal

**Evidence:** `agents/scorer.py:16-24` weights include `market_size: 1.5`; the A4 prompt
carries an `estimated_tam` dimension. A real judgment from the output:

> *"the total addressable market is estimated at **$10-100M, which is small for a
> standalone product**"*

**Problem:** for a VC, $10-100M TAM is too small. **For the actual user — a solo developer
who wants to ship apps and websites — that is enormous**; 500 users at $10/month is a
success. The system is systematically rejecting exactly the class of opportunity the
operator wants.

**Direction:** downweight or replace `market_size`/TAM with **reachability** ("can 1,000 of
these users be found in one place?"). Architectural → needs an ADR.

---

#### Q3 — Cluster aggregation is a Frankenstein merge; `occurrence_count` is misleading ⚠️ NEW

**This is the most important finding in this review and is not covered by F1–F11.**

**Evidence:** `agents/aggregate.py:89-98`, `aggregate_cluster_a2()` merges N members
field by field:

```python
who=_longest_str(a2.get("who") for a2 in a2s),          # longest wins
what=_longest_str(a2.get("what") for a2 in a2s),        # longest wins
desired_outcome=_longest_str(...),                       # longest wins
emotional_intensity=max(intensities),                    # max wins
```

`who` comes from member A, `what` from member B, `desired_outcome` from member C — **these
are different people's different problems, stitched into one synthetic pain that no real
user actually has.**

**Live proof** (cluster name vs. what the concept actually describes):

| occurrence | keyword (cluster name) | tool_concept (the problem actually described) |
|---:|---|---|
| **13** | `bypass-forum-posting-delays` | Codex losing the ability to organize feature points |
| 3 | `one-click-tiktok-transcripts` | cleaning up meeting-recording transcripts |
| 3 | `bank-account-freeze-prevention` | detecting AI-generated images |
| 2 | `unified-open-source-downloader-library` | incomplete Deepseek tool support in coding assistants |
| 4 | `ai-code-error-post-mortems` | pirated Cursor plugins being broken |

**Impact:** this corrupts precisely the signal that separates *real demand* from *one
person's complaint* — **the core value proposition itself**. The operator reads "13
mentions" as validation. It isn't: 13 items merely shared enough keywords to merge, and
the product being described comes from one of them.

**Secondary bias:** `emotional_intensity = max` makes every multi-member cluster inherit
the most upset person in it — a systematic upward bias that then feeds A4's scoring.

**Direction:**
- Either analyze one representative item and show the rest as corroboration,
- or hand A3–A8 the full member list and let the LLM synthesize honestly.
- **Never merge field-by-field by longest string again.**
- Recompute `occurrence_count` as **distinct authors** or **distinct sources**.

---

#### Q5 — No form-factor gate: hardware, shopping, support tickets all pass through

**Evidence:** grepped all 8 prompts — **no form-factor constraint exists anywhere**. A1's
pass criteria only require *"related to software, workflow, or information"*, which a
tech-support question satisfies perfectly.

**Real cases that leaked through:** OpenWRT router selection · BGP router hardware · Apple
ID unbinding · China's 等保 certification · China Unicom phone plans · SuperGrok payment
proxying · "legally split a $2000 subscription". Each was assigned a `$19/mo` pricing
hypothesis; one had "Amazon affiliate links" as its monetization model.

**Direction:** add an explicit criterion to A1 (or a cheap new A1.5 gate): *must be
solvable by a web or mobile application one developer can ship*. Reject hardware, purchase
advice, account/billing support, government processes, and geographically locked services.
Encode these as reject archetypes in the golden set.

> Rough estimate: this one criterion alone would have eliminated ~12 of the 31 items in
> the second sample run.

---

### 🟠 Serious (materially distorts output)

---

#### Q4 — Cluster name is decoupled from cluster content

**Evidence:** `agents/clustering.py:147 _name_small_cluster()` names a cluster by its
**most frequent keyword**; large clusters are named by the LLM. Meanwhile the concept comes
from the Frankenstein A2 of Q3. Different provenance, so they routinely describe different
things (examples in the Q3 table).

**Direction:** derive the display name from the A8 `title` or A2 `what`, not keyword
frequency.

---

#### Q6 — The corpus is dominated by the wrong kind of forum

**Evidence:** `collectors/v2ex.py:30`

```python
DEFAULT_NODES = ["startup", "qna", "python", "share"]
```

`qna` is a tech-support board. In the July metrics it contributed 87 of 110 analyzed items;
live it is still the main producer at 49.

**The contrast:** the best-designed collector in the entire repo is HN
(`collectors/hackernews.py:26`):

```python
"I wish there was", "we do this manually", "still using spreadsheets",
"pricing is crazy", "looking for a tool", ...
```

That is exactly the right way to mine product demand. **It yields 2 items live.** Reddit —
the highest-density source anywhere for "I wish there was a tool that…" — is at 0 because
PRAW credentials are unset.

**Direction (highest input-side ROI):**
1. Drop `qna` from V2EX default nodes; keep `startup`/`create`.
2. Expand HN — add the `story` tag, more queries, a wider time window (currently only 9
   queries against `ask_hn`).
3. **Configure Reddit PRAW credentials** (F6, pending user decision) — the single largest
   available input-side win.

---

#### Q7 — A3's market intelligence is unverified model recall presented as research

**Evidence:** the A3 system prompt states *"analyze the existing market landscape **based on
your knowledge**"*, and emits `existing_solutions`, `price_range`, `estimated_tam`,
`saturation_score` — none of it measured.

**Compounded by F7 (worse):** the DDG web-validation step hits a 202 bot challenge → 0 hits
→ recorded as `validated_gap`. **A network failure is being read as a validated market
opportunity.** That is worse than no validation at all.

**Direction:** fix F7 first (0 hits *with errors* ⇒ `unknown`, never `gap`). Then decide
between wiring a real search API or labeling A3 output as "unverified" in the UI.

---

#### Q11 — The analysis window is 7 days; recurrence over time is not modeled

**Evidence:** `config.py` `analysis_window_days: 7`; clustering happens only within a
batch; `archive_stale_niches` archives on the same 7-day window.

**Problem:** the same pain recurring in March, April, and May is the **strongest signal
obtainable** — and it is architecturally invisible. `momentum_label` (122 "growing" live)
appears to cover this, but it is a week-over-week mention count resting on the
already-corrupted `occurrence_count` from Q3.

**Direction:** persist pain fingerprints across runs and cluster over the longitudinal
corpus rather than the batch. Architectural → needs an ADR.

---

### 🟡 Moderate (correctness and trust)

---

#### Q8 — Two contradicting tier vocabularies, and the top tier is unreachable ⚠️ NEW

**Evidence:**

| Location | Definition | Basis |
|---|---|---|
| `agents/scorer.py:29` | hot(>50) / warm(35-50) / cold(<35) | A4 raw score 0–70 |
| `api/routes/_common.py:13` | high_priority(≥80) / watchlist(≥65) / archive(<65) | weighted score 0–100 |

The API definition drives the UI. All-time max score is 72.63 ⇒ **`high_priority` has never
been reached (0/207)**, and 196/207 render as "archive".

**Direction:** collapse to one tier definition; recalibrate thresholds against the observed
distribution (mean 50 / max 72.6).

---

#### Q9 — `build_complexity` conflates technical difficulty with time-to-build ⚠️ NEW

**Evidence:** `agents/scorer.py:78 build_complexity_from_feasibility()` maps A5's
`feasibility_score` (technical tractability) to a 1–5 complexity, rendered in the UI as
**"Build: 2-3 days"**. But A6 rejects using A5's `estimated_weeks_to_mvp` — a different
number entirely.

**Self-contradicting instance** (`2026-07-03-first-real-run.md` #1):

> Header: **Build `2-3 days` (2/5)** ｜ Body: *"estimated at **10 weeks** for MVP"*

Live, 102/207 carry build_complexity = 2 — most cards are displaying a fake duration
derived from a difficulty score.

**Note:** F9 classified this as a report-formatting problem. **The root cause is semantic
conflation** and must be fixed in `scorer.py`, not the report layer.

**Direction:** display `estimated_weeks_to_mvp` directly; drop the difficulty→time
derivation.

---

#### Q10 — A1 precision 26.1%; ~74% of Phase-C spend polishes junk

Carried forward from `2026-07-04-run-metrics.md` §3 (n=48: recall 85.7% / precision 26.1%).

**Added here:** the form-factor archetypes from Q5 (hardware, purchase advice, account
support, government process, geo-locked services) should join the eight known false-pass
archetypes and be encoded in the golden set before the next iteration.

---

#### Q12 — Architectural inversion (strategic, for discussion)

**Observation:** the current shape **automates the part humans are good at (judgment) and
under-invests in the part humans are bad at (reading ten thousand posts).**

Six LLM agents stack confident speculation on top of one sentence of real quoted text.
After 207 attempts, the entire output of the judgment layer is "no". The
evidence-to-speculation ratio is badly inverted.

**Alternative shape for discussion ("evidence-first" mode):**
collect aggressively → filter on **form-factor gate + recurrence only** → present clustered
raw quotes with links → the operator judges → run A3–A8 **on demand** for the few they
select.

This flips the evidence/speculation ratio, cuts cost sharply, and restores trust.
**This is an ADR-level proposal, not a task** — it needs the operator's decision first.

---

### ℹ️ To verify

- **F4 status is now ambiguous:** `status.md` records F4 (youtube `posted_at` NULL, 114
  items invisible to analysis) as unfixed, but the live instance shows youtube collecting
  80 items. Confirm whether those 80 actually reach A1 or are still silently dropped.
- 4 sources FAILED (product_hunt / app_store / play_store / xueqiu), 7 MISSING. Decide
  which are worth repairing and which should be removed — **6 of 23 sources producing** is
  itself evidence that the breadth strategy has passed negative marginal return.

---

## 4. Roadmap (ordered by leverage) — ⚠️ SUPERSEDED BY §7

> **This section is retained for provenance only.** It was written before the operator
> answered §6. Adopting ADR-011 (evidence-first) dissolves several items below rather than
> fixing them — building them as scoped here would be wasted effort. **Use §7.**

> One task branch and one draft PR per item, per AGENTS.md §7. ⚠️ marks items needing an
> ADR first.

### P0 — Change the character of the output (small changes, large effect)

| # | Task | Covers | Expected effect |
|---|---|---|---|
| P0-1 | Add a **form-factor gate** to A1 (web/app deliverability) + encode archetypes in the golden set | Q5 | Removes roughly a third of unbuildable entries outright |
| P0-2 | Drop the `qna` node from V2EX; expand HN queries/tags/window | Q6 | Changes the corpus's character at near-zero cost |
| P0-3 | Configure Reddit PRAW credentials (needs user) | Q6/F6 | Largest single input-side win |
| P0-4 | Fix F7: 0 hits *with errors* ⇒ `unknown`, never `validated_gap` | Q7 | Stops a failure from masquerading as an opportunity |

### P1 — Make verdicts and display trustworthy

| # | Task | Covers | Note |
|---|---|---|---|
| P1-1 | Rework cluster aggregation: abolish field-wise longest-string merge; recompute `occurrence_count` as distinct authors/sources | **Q3** | ⚠️ ADR |
| P1-2 | Derive cluster display name from A8 title / A2.what | Q4 | Depends on P1-1 |
| P1-3 | Separate the time budget from the verdict; make the window configurable | Q1 | ⚠️ ADR |
| P1-4 | Rework A4 weights: downweight TAM/market_size, introduce reachability | Q2 | ⚠️ ADR |
| P1-5 | Unify the tier definition; recalibrate thresholds to the observed distribution | Q8 | Small |
| P1-6 | Display `estimated_weeks_to_mvp` directly; retire `build_complexity_from_feasibility` | Q9 | Small |

### P2 — Structural

| # | Task | Covers | Note |
|---|---|---|---|
| P2-1 | Iterate the A1 prompt to precision ≥60% (recall not below ~80%) | Q10 | Must come **after** P0-1/P0-2, or it tunes against the old corpus |
| P2-2 | Persist pain fingerprints across runs; cluster longitudinally | Q11 | ⚠️ ADR |
| P2-3 | Wire A3 to a real search API, or label its output "unverified" in the UI | Q7 | ⚠️ ADR |
| P2-4 | Source health cleanup: repair or remove the 11 FAILED/MISSING sources | §3 To verify | Removal likely beats repair |
| P2-5 | Evidence-first mode | Q12 | ⚠️ ADR, needs a decision first |

---

## 5. Explicitly not recommended

- **Do not iterate the A1 prompt before fixing the corpus (Q6).** That is tuning against
  the wrong input; the next source change would zero out the gains.
- **Do not add new collectors.** 6 of 23 produce — breadth has passed negative marginal
  return. The July collector freeze still applies.
- **Do not fix Q3 as a formatting problem.** It is an aggregation-semantics error; patching
  the report layer only buries it deeper.
- **Do not lower thresholds just to make the GO rate non-zero.** Fix the corpus and the
  aggregation first so the scores mean something, then recalibrate.

---

## 6. Operator decisions — ANSWERED 2026-08-04

All four open questions were resolved by the operator on the day of the review. The answers
are recorded here; two of them were consequential enough to require ADRs, and both are now
written. **§4's roadmap has been re-derived accordingly — see §7.**

| # | Question | Answer | Consequence |
|---|---|---|---|
| 1 | Reddit credentials | **Deferred.** "Not urgent — I'll configure it once things work. What needs fixing now is the project's overall usability, from first principles." | P0-3 leaves P0. The other two parts of Q6 (V2EX `qna`, HN expansion) are independent of Reddit and stay. |
| 2 | Target scale | **Both.** "I can do either — can we have both? Two analyses?" | → **ADR-012**: two independent assessment tracks over shared dimensions. |
| 3 | 2-4 week window | **Reference value, not a constraint.** | Build duration is never a rejection reason in either track; `estimated_weeks_to_mvp` is displayed as a fact (Q9). |
| 4 | Evidence-first mode | **Adopted.** | → **ADR-011**: split the pipeline at the evidence/judgment boundary. |

### Why answer 2 mattered more than it looks

"Both" is not a scope dodge — it is the question the current design structurally cannot
answer. A single composite score blending both goals is optimal for neither, and the
production numbers are exactly that failure mode: mean 50.0, max 72.63, nothing ever clears
the top tier, GO rate 0.0%.

The decisive point is that **the two rubrics disagree about the same opportunity, and the
disagreement is the signal** — see the worked table in ADR-012 §Context, where the macOS
Finder utility, the AI-search-with-citations product, and the zero-config share link sort
into completely different ranks under the two lenses, yet all three collapse to ~42–64 and
NO-GO today. The distinction the operator most needs is precisely the one being averaged
away.

---

## 7. Revised roadmap (supersedes §4)

Adopting ADR-011 changes the shape of the work materially: **several §4 items are dissolved
rather than fixed.** Building them as originally scoped would be wasted effort.

### What ADR-011 dissolves

| §4 item | Original plan | Status under ADR-011 |
|---|---|---|
| P1-1 (Q3 cluster aggregation) | Rework the field-wise merge | **Retired, not repaired.** Phase 1 shows members individually; Phase 2 hands A3–A8 the full member list. `aggregate_cluster_a2()`'s longest-string merge is deleted. |
| P1-2 (Q4 cluster naming) | Derive name from A8 title | **Simplified.** Phase 1 clusters need a name from evidence, not from an agent that no longer runs automatically. |
| P1-3 (Q1 time gate) | Decouple from verdict | **Absorbed** into ADR-012 item 3. |
| P1-4 (Q2 A4 weights) | Single reweight | **Replaced** by ADR-012's two-track design. |
| P0-4 / P2-3 (Q7 A3 grounding) | Fix + ground A3 | **Blast radius shrinks** to deep dives only. F7 still needs fixing; the "wire a real search API" question becomes much less urgent. |

### Revised sequence

**Stage 1 — Input quality (unchanged, still first).** These are independent of the
architecture change and remain the cheapest wins.

| # | Task | Covers |
|---|---|---|
| S1-1 | Add the **form-factor gate** to A1 + encode archetypes in the golden set | Q5 |
| S1-2 | Drop the `qna` node from V2EX; expand HN queries/tags/window | Q6 |
| S1-3 | Fix F7: 0 hits *with errors* ⇒ `unknown`, never `validated_gap` | Q7 |

**Stage 2 — Phase 1 / evidence path (ADR-011).**

| # | Task | Covers |
|---|---|---|
| S2-1 | Persist Evidence Clusters as first-class records (members, provenance, distinct-author/source counts) | Q3 |
| S2-2 | Evidence score from counted quantities only (authors, sources, recurrence, recency) | Q3, Q11 |
| S2-3 | Cut A3–A8 out of the automatic cycle; retire `aggregate_cluster_a2()`'s merge | Q3, Q1 |
| S2-4 | Frontend: primary object becomes the Evidence Cluster; evidence vs. assessment split | Q4, Q8 |

**Stage 3 — Phase 2 / on-demand deep dive (ADR-011 + ADR-012).**

| # | Task | Covers |
|---|---|---|
| S3-1 | Operator-triggered deep dive on one cluster; A3–A8 receive the full member list | Q3 |
| S3-2 | A4 → neutral measurer; dimension set grows (defensibility, retention) | Q2 |
| S3-3 | A6 → dual-track judge; per-track recommendations | Q1, Q2 |
| S3-4 | Retire `build_complexity_from_feasibility()`; display `estimated_weeks_to_mvp` | Q9 |
| S3-5 | Collapse the two tier vocabularies to one definition, applied per track, recalibrated | Q8 |

**Stage 4 — Deferred / later.**

| # | Task | Covers | Note |
|---|---|---|---|
| S4-1 | A1 precision ≥60% (recall ≥~80%) | Q10 | **Only after S1-1/S1-2** — tuning before the corpus is fixed is tuning on the wrong input |
| S4-2 | Reddit PRAW credentials | Q6/F6 | Operator-deferred; configure when the rest works |
| S4-3 | Longitudinal pain fingerprints across runs | Q11 | Natural extension of S2-2's evidence score |
| S4-4 | Source health cleanup (11 FAILED/MISSING) | §3 | Removal likely beats repair |
| S4-5 | Ground A3 in real search, or keep it labeled "unverified" | Q7 | Much less urgent post-ADR-011 |

### Unchanged from §5

The "explicitly not recommended" list still holds in full — in particular **do not tune the
A1 prompt before the corpus is fixed** (now S4-1 after S1-1/S1-2), and **do not add new
collectors**.
