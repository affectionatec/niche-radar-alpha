# First Measured Real Runs — Metrics & Findings (2026-07-03/04)

> Companion to the real report artifacts in this directory. Executes the P0 of
> `docs/reviews/2026-07-03-first-principles-review.md`: run the pipeline for real,
> measure everything, and let the numbers say where the product actually stands.
> Setup: Docker Compose (`radar` + `frontend`), default config, no source credentials,
> LLM = DeepSeek `deepseek-v4-flash` via `LLM_*` env (OpenAI-compatible).

## 1. Cycle summaries

| | Cycle 1 (2026-07-03 14:40Z) | Cycle 2 (2026-07-04 02:15Z) |
|---|---|---|
| Trigger | `POST /api/pipeline/run-all` | same, after HN + usage fixes |
| Wall clock (collect → analyze → report) | 9m42s (5m16s / 4m05s / 21s) | 7m48s (3m45s / 3m41s / 22s) |
| Items collected (run total) | 170 | 168 (mostly dedup re-sightings) |
| Items entering analysis (7-day window, new) | 91 | 70 |
| Passed A1 | 17 (18.7%) | 16 (22.9%) |
| Clusters | 17 (all singletons) | 16 (all singletons) |
| Niche analyses persisted | 17 | 16 |
| Verdicts | 1 GO / 16 NO-GO | 1 GO / 15 NO-GO |
| LLM calls (budget counter) | 203 | 170 |
| Measured tokens | ⚠️ not recorded (F2, fixed after cycle 1) | 118,744 in + 93,100 out |
| Prompt-cache hits | — | 49,920 / 118,744 (42%) |
| **Cost (DeepSeek list price)** | ≈ $0.04 (est. from cycle-2 per-call profile) | **$0.0358 measured** |

Pricing basis: v4-flash $0.14/M input (cache miss), $0.0028/M input (cache hit), $0.28/M output.
**A full pipeline cycle costs under $0.04.** Cost is a non-issue at this scale; quality is the issue.

Cycle-2 tokens by agent (from `llm_usage`, now actually populated):

| Agent | Calls | Prompt | Completion | Cached |
|---|---|---|---|---|
| a1 signal filter | 72 | 37,093 | 14,901 | 18,816 (51%) |
| a8 brief writer | 16 | 35,939 | 11,798 | 6,144 |
| a2 pain extractor | 16 | 11,118 | 12,065 | 4,096 |
| a5 feasibility | 17 | 8,825 | 12,681 | 6,144 |
| a4 scorer | 17 | 8,708 | 14,019 | 6,528 |
| a6 verdict | 16 | 8,696 | 9,840 | 4,096 |
| a3 market research | 16 | 7,490 | 16,380 | 4,096 |
| a7 PRD writer | 1 | 875 | 1,416 | 0 |

a1 calls = 72 for 70 items → 2 malformed-JSON retries (cycle 1: 99 calls / 91 items → 8 retries).
a7 fired once per cycle — exactly one GO verdict each time.

## 2. Per-source funnel (the "which sources matter" answer)

| Source | Collected (cumulative) | Analyzed | Passed A1 | Notes |
|---|---|---|---|---|
| youtube | 114 | **0** | — | ⚠️ F4: yt-dlp backend leaves `posted_at` NULL → permanently excluded from analysis |
| v2ex | 87 | 87 | 28 | The only high-volume live source; mix of real pains + launch posts |
| google_trends | 30 | 30 | 0 | News/sports/event queries; pure noise for this product |
| linkedin | 21 | 21 | 2 | ⚠️ F5: all bodies empty (query-echo shells); 2 still passed A1 |
| github | 20 | 20 | 1 | Repo descriptions; the 1 "pass" was a repo tagline (false pass) |
| hn | 3 | 3 | 2 | ⚠️ was 0 before the F1 fix; both passes match human labels |
| reddit | 0 | — | — | public JSON = HTTP 403 from this network too; PRAW creds or Jina tier needed |
| all other 16 | 0 | — | — | failed (product_hunt, app/play_store, xueqiu), empty (stack_overflow, g2, indie_hackers, bilibili), or key/opt-in gated (twitter, exa, bluesky, tiktok, instagram, threads, xiaohongshu, xiaoyuzhou) |

**Of 23 registered sources, 6 produced items, 3 produced any analyzable signal, and 2 (v2ex, hn) produced genuine pain-point signal.** The review's "signal quality > signal count" call is now a measured fact.

## 3. A1 calibration vs. human labels (n=48)

The golden set was expanded 5 → 61 using these runs' raw_items (see `eval/golden_set.json`;
each item's note records provenance and any model/label disagreement). Comparing the real
DeepSeek A1 decisions against the 48 human-labeled items that went through analysis:

|  | Human PASS | Human REJECT |
|---|---|---|
| **A1 passed** | 6 (TP) | 17 (FP) |
| **A1 rejected** | 1 (FN) | 24 (TN) |

- **Recall 85.7%** — A1 almost never loses a true pain signal.
- **Precision 26.1%** — three of four items A1 passes are junk. False-pass archetypes, each now encoded in the golden set: product launch posts (author already built it), shopping/purchase advice, service-outage complaints, rants/venting, how-to support questions, market commentary, repo taglines, and even empty query-echo shells.
- Direct consequence: ~74% of phase-C tokens polish junk, and junk reaches the report's top slots — cycle 1's sole "⚡ Quick Win" was a false-pass (college-application market commentary) whose own rationale text says the build is infeasible.
- The one false-reject was a deliberately borderline label (enterprise-grade LLM practice environments).

**Highest-leverage next step: harden the A1 prompt against the eight false-pass archetypes and re-measure against the golden set.** Recall has headroom to trade for precision.

## 4. Defects found by running for real (F#)

| # | Finding | Status |
|---|---|---|
| F1 | **HN collector dead**: Algolia's HN index stopped accepting `points`/`num_comments` in `numericFilters` → HTTP 400 on every query; CI green because all network is mocked. Exactly the "scraper rot" failure mode predicted by review §F3. | ✅ Fixed this branch (`created_at_i` server-side + client-side thresholds); hn now yields items |
| F2 | **Cost attribution never worked**: `llm_usage` accumulator was `threading.local()`, but agents record from ThreadPoolExecutor workers and the flush runs on the main thread → cycle 1 made 203 calls, flushed 0 rows. No mocked test could see it. | ✅ Fixed this branch (lock-guarded global + cross-thread regression test); cycle 2 flushed 171/171 |
| F3 | Cache-hit tokens were read from a flat `cached_tokens` attr that neither OpenAI nor DeepSeek usage objects have → cache ratio permanently 0. | ✅ Fixed with F2 (nested `prompt_tokens_details.cached_tokens` + DeepSeek `prompt_cache_hit_tokens`) |
| F4 | YouTube (yt-dlp backend) leaves `posted_at` NULL → 114 collected items can never enter analysis (`get_items_needing_a1` requires non-NULL). #2 volume source is invisible downstream. | ⬜ Follow-up |
| F5 | LinkedIn `public_search` returns title-only query-echo shells (21/21 empty bodies); they waste A1 calls and 2 even passed. Empty-body items should be dropped at collection. | ⬜ Follow-up |
| F6 | Reddit public JSON gets HTTP 403 from residential IP as well (not just CI datacenter IPs) — source is 0 with default config; needs PRAW creds or the opt-in Jina tier (user decision). | ⬜ User decision |
| F7 | DDG web-validation gets HTTP 202 (bot challenge) on every query, then reports `validated_gap` with 0 hits — a network failure masquerading as a positive market-gap signal. | ⬜ Follow-up (treat 0-hit-with-errors as "unknown", not "gap") |
| F8 | Clustering produced 33/33 singletons across both cycles — Jaccard threshold never merged anything, so phase-C cost scales 1:1 with passed items and repeated pains don't aggregate. | ⬜ Follow-up (tune/measure once A1 precision is fixed) |
| F9 | Report quality: niche "keywords" become paragraph-long A8 titles; a 74/100 "Quick Win" contradicts its own infeasibility rationale; verdict (GO/NO-GO) not shown per item; EN/中文 mixed output. | ⬜ Follow-up (report + prompt polish) |
| F10 | `pipeline_runs.started_at` = `completed_at` (row inserted only at completion) → run duration unrecoverable from the table. | ⬜ Follow-up (trivial) |
| F11 | Scheduler fired the missed 4h collect on laptop wake (APScheduler coalescing) — fine, but worth knowing: sleep/wake produces burst cycles on self-hosted laptops. | ℹ️ Behavior note |

## 5. What this means (recommendation)

1. **The engine runs end-to-end and costs pennies.** Ignition achieved; cost is not a constraint.
2. **The bottleneck is measured, not guessed: A1 precision (26%).** Iterate the A1 prompt against the 61-item golden set (`python -m niche_radar.eval.runner`) before touching anything else.
3. Then fix the two silent input-side losses (F4 youtube `posted_at`, F5 linkedin shells) — they're cheap and unlock the #2 volume source.
4. Keep the collector freeze until the above land (review §5 冻结项 still applies).
