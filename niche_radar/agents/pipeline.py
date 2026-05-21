"""Top-level 4-phase pipeline driver.

run_pipeline orchestrates:
  Phase A — per raw_item, parallel: A1 → A2 (orchestrator.run_single)
  Phase B — cluster passed extractions by pain similarity (clustering.cluster_extractions)
  Phase C — per cluster, parallel: A3 → A4 → A5 → A6 → (A7 if GO) → A8 (orchestrator.run_cluster)
  Phase D — map cluster outputs to niche_candidates rows + insert niche_analyses

Concurrency: LLM calls parallelize across items (phase A) and clusters (phase C). DB writes
serialize through the main thread (SQLite single-writer).

Budget: A BudgetTracker caps total LLM calls per run. Pass `budget=None` to disable.

Dry-run: pass dry_run=True to run the whole pipeline without writing anything to DB.
Useful for --test mode and for safe development.
"""

from __future__ import annotations

import sqlite3
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Callable

import structlog

from niche_radar.agents.aggregate import aggregate_cluster_a2
from niche_radar.agents.clustering import Cluster, cluster_extractions
from niche_radar.agents.llm_config import resolve_agent_client
from niche_radar.agents.models import A1Output, A2Output, PipelineResult
from niche_radar.agents.orchestrator import (
    BudgetExceeded,
    ClientsResolver,
    LogFn,
    run_cluster,
    run_single,
)
from niche_radar.agents.scorer import (
    build_complexity_from_feasibility,
    tier,
    weighted_score,
)
from niche_radar.llm.base import LLMClient
from niche_radar.storage.repository import (
    attach_latest_analysis,
    get_items_needing_a1,
    get_unclustered_passed_extractions,
    insert_niche_analysis,
    link_niche_item,
    lookup_niche_by_alias_overlap,
    update_extraction_cluster,
    upsert_item_extraction,
    upsert_niche_candidate,
)

logger = structlog.get_logger()

_PHASE_MAX_WORKERS = 8


# ============================================================================
# Budget
# ============================================================================


class BudgetTracker:
    """Caps total LLM calls per pipeline run.

    Default formula (computed lazily once we know item / cluster counts):
        max_calls = 2 * num_items + 10 * num_clusters + 50
    """

    def __init__(self, max_calls: int | None) -> None:
        self.max_calls = max_calls if max_calls is not None and max_calls > 0 else None
        self.count = 0
        self.by_agent: dict[str, int] = {}

    def __call__(self, agent_id: str) -> None:
        """Invoke before each LLM call (used as orchestrator's budget_check)."""
        self.count += 1
        self.by_agent[agent_id] = self.by_agent.get(agent_id, 0) + 1
        if self.max_calls is not None and self.count > self.max_calls:
            raise BudgetExceeded(
                f"exceeded budget of {self.max_calls} LLM calls "
                f"(by_agent={self.by_agent})"
            )

    @staticmethod
    def for_run(num_items: int, num_clusters: int) -> int:
        return 2 * num_items + 10 * max(num_clusters, 1) + 50


# ============================================================================
# Resolver helpers
# ============================================================================


_ALL_AGENT_IDS = ("a1", "a2", "a3", "a4", "a5", "a6", "a7", "a8")


def _build_resolver(
    db: sqlite3.Connection,
    settings,
    overrides: dict[str, LLMClient] | None = None,
) -> ClientsResolver:
    """Return a clients_resolver suitable for orchestrator.run_single / run_cluster.

    Pre-resolves all 8 agent clients in the CALLING thread (main thread). The resolver
    closure then just returns from the dict, which is safe to invoke from worker threads
    — SQLite connections only live on their creation thread.
    """
    cache: dict[str, tuple[LLMClient, float]] = {}
    for aid in _ALL_AGENT_IDS:
        cache[aid] = resolve_agent_client(aid, db, settings, overrides=overrides)

    def resolve(agent_id: str) -> tuple[LLMClient, float]:
        if agent_id in cache:
            return cache[agent_id]
        # Unknown agent (e.g. clustering uses a3 client) — fall back to live lookup
        # which the caller must invoke from a thread with DB access.
        return resolve_agent_client(agent_id, db, settings, overrides=overrides)
    return resolve


# ============================================================================
# Phase A — per raw_item filter + extract (parallel)
# ============================================================================


def _phase_a_for_item(
    raw_item: dict,
    resolver: ClientsResolver,
    budget: BudgetTracker | None,
    log_fn: LogFn | None,
) -> tuple[str, PipelineResult]:
    """Run A1 + A2 on one raw_item. Returns (raw_item_id, PipelineResult)."""
    raw_signal = {
        "text": ((raw_item.get("title") or "") + "\n\n" + (raw_item.get("body") or "")).strip(),
        "source": raw_item.get("source"),
        "url": raw_item.get("url"),
        "scraped_at": raw_item.get("posted_at") or raw_item.get("collected_at"),
    }
    result = run_single(raw_signal, resolver, budget_check=budget, log_fn=log_fn)
    return raw_item["id"], result


def _persist_extraction(
    db: sqlite3.Connection,
    raw_item_id: str,
    pipeline_run: str,
    result: PipelineResult,
) -> None:
    """Write phase A result to item_pain_extractions in the main thread."""
    a1 = result.a1
    if a1 is None:
        # Terminal A1 failure — store row marking it as not-valid so we don't retry forever.
        upsert_item_extraction(
            db, raw_item_id=raw_item_id, pipeline_run=pipeline_run,
            a1_is_valid=False, a1_confidence=None, a1_signal_type=None,
            a1_result=None, a2_result=None,
            error=f"A1 failed: failed_agents={result.failed_agents}",
        )
        return
    upsert_item_extraction(
        db, raw_item_id=raw_item_id, pipeline_run=pipeline_run,
        a1_is_valid=bool(a1.is_valid_signal),
        a1_confidence=a1.confidence,
        a1_signal_type=a1.signal_type,
        a1_result=a1.model_dump(mode="json"),
        a2_result=result.a2.model_dump(mode="json") if result.a2 else None,
    )


def run_phase_a(
    db: sqlite3.Connection,
    settings,
    pipeline_run: str,
    items: list[dict],
    *,
    dry_run: bool = False,
    overrides: dict[str, LLMClient] | None = None,
    budget: BudgetTracker | None = None,
    log_fn: LogFn | None = None,
) -> int:
    """Filter + extract per item. Returns count of items that passed A1."""
    if not items:
        return 0
    resolver = _build_resolver(db, settings, overrides=overrides)
    if log_fn:
        log_fn(f"phase=A items={len(items)}")

    passed = 0
    workers = min(len(items), _PHASE_MAX_WORKERS)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [
            pool.submit(_phase_a_for_item, item, resolver, budget, log_fn)
            for item in items
        ]
        for f in futures:
            raw_item_id, result = f.result()
            if not dry_run:
                _persist_extraction(db, raw_item_id, pipeline_run, result)
            if result.a1 and result.a1.is_valid_signal:
                passed += 1

    if log_fn:
        log_fn(f"phase=A done passed={passed} rejected={len(items) - passed}")
    return passed


# ============================================================================
# Phase B — cluster
# ============================================================================


def run_phase_b(
    db: sqlite3.Connection,
    settings,
    pipeline_run: str,
    *,
    dry_run: bool = False,
    overrides: dict[str, LLMClient] | None = None,
    budget: BudgetTracker | None = None,
    log_fn: LogFn | None = None,
) -> list[Cluster]:
    """Read passed/unclustered extractions, run clustering, write cluster_ids back to DB."""
    extractions = get_unclustered_passed_extractions(db, pipeline_run)
    if not extractions:
        if log_fn:
            log_fn("phase=B skip empty")
        return []

    if log_fn:
        log_fn(f"phase=B extractions={len(extractions)}")

    # Use a "clustering" pseudo-agent for the refinement client. We piggyback on the a3
    # config since both are "strong" tier — same resolver, but charged under a separate
    # budget bucket via a clustering_check.
    try:
        client, temp = resolve_agent_client("a3", db, settings, overrides=overrides)
    except ValueError:
        client = None
        temp = 0.2

    # Wrap budget so clustering counts under "clustering" bucket
    def cluster_budget_check(_agent_id):
        if budget is not None:
            budget("clustering")

    # cluster_extractions doesn't take a budget_check param — but we can pre-check before
    # passing the client.  For now we just let the LLM call go through without a per-call
    # budget on clustering; clustering is at most a few calls per run.
    clusters = cluster_extractions(
        extractions,
        refinement_client=client,
        refinement_temperature=temp,
        log_fn=log_fn,
    )

    # Write cluster_id back so re-runs are idempotent.
    if not dry_run:
        for c in clusters:
            update_extraction_cluster(db, c.raw_item_ids, c.cluster_id)

    return clusters


# ============================================================================
# Phase C — per-cluster deep analysis (parallel)
# ============================================================================


def _phase_c_for_cluster(
    cluster: Cluster,
    resolver: ClientsResolver,
    budget: BudgetTracker | None,
    log_fn: LogFn | None,
) -> PipelineResult:
    """Build cluster_context (aggregated A2 + synthetic raw_signal) and run A3..A8."""
    a2_agg = aggregate_cluster_a2(cluster.extractions)
    # Synthetic raw_signal — used only for A8's source/timestamp fields.
    src = cluster.extractions[0].get("a1", {}).get("source") if cluster.extractions else None
    cluster_context = {
        "raw_signal": {
            "text": a2_agg.what or "",
            "source": src or "mixed",
            "url": None,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        },
        "a2": a2_agg,
    }
    return run_cluster(cluster_context, resolver, budget_check=budget, log_fn=log_fn)


def run_phase_c(
    db: sqlite3.Connection,
    settings,
    clusters: list[Cluster],
    *,
    overrides: dict[str, LLMClient] | None = None,
    budget: BudgetTracker | None = None,
    log_fn: LogFn | None = None,
) -> list[tuple[Cluster, PipelineResult]]:
    """Run A3-A8 on every cluster in parallel. Returns list of (cluster, result) pairs."""
    if not clusters:
        return []
    resolver = _build_resolver(db, settings, overrides=overrides)
    if log_fn:
        log_fn(f"phase=C clusters={len(clusters)}")

    workers = min(len(clusters), _PHASE_MAX_WORKERS)
    out: list[tuple[Cluster, PipelineResult]] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(_phase_c_for_cluster, c, resolver, budget, log_fn): c
            for c in clusters
        }
        for f in futures:
            cluster = futures[f]
            result = f.result()
            out.append((cluster, result))

    if log_fn:
        log_fn(f"phase=C done")
    return out


# ============================================================================
# Phase D — map cluster outputs to niche_candidates + insert niche_analyses
# ============================================================================


_RE_KEEP = "abcdefghijklmnopqrstuvwxyz0123456789- "


def _slug(s: str | None) -> str:
    if not s:
        return ""
    out = []
    for ch in str(s).lower():
        out.append(ch if ch in _RE_KEEP else " ")
    s = "".join(out).strip()
    return "-".join(s.split())[:60]


def _derive_keyword(cluster: Cluster, result: PipelineResult) -> str:
    """Fallback chain: A7.product_name (GO) → A8.title → A2 dominant keyword → cluster name."""
    if result.a7 and result.a7.product_name:
        slug = _slug(result.a7.product_name)
        if slug:
            return slug
    if result.a8 and result.a8.title:
        slug = _slug(result.a8.title)
        if slug:
            return slug
    if result.a2 and result.a2.keywords:
        slug = _slug(result.a2.keywords[0])
        if slug:
            return slug
    return cluster.name or "unnamed-niche"


def _derive_aliases(cluster: Cluster, result: PipelineResult) -> list[str]:
    aliases: list[str] = []
    if result.a2 and result.a2.keywords:
        for kw in result.a2.keywords[1:5]:
            s = _slug(kw)
            if s and s not in aliases:
                aliases.append(s)
    return aliases


def _derive_tool_concept(result: PipelineResult) -> str:
    if result.a7 and result.a7.one_liner:
        return result.a7.one_liner
    if result.a8 and result.a8.tldr:
        return result.a8.tldr
    return ""


def _derive_reasoning(result: PipelineResult) -> str:
    parts = []
    if result.a6 and result.a6.full_rationale:
        parts.append(result.a6.full_rationale)
    if result.a8 and result.a8.top_reason_to_do_it:
        parts.append(result.a8.top_reason_to_do_it)
    return " — ".join(parts)


def _derive_pain_points(cluster: Cluster) -> list[dict]:
    """Build a pain_points list with one entry per cluster item."""
    out: list[dict] = []
    for ex in cluster.extractions:
        a2 = ex.get("a2") or {}
        out.append({
            "pain": a2.get("what") or "",
            "quote": a2.get("pay_signal_evidence") or a2.get("what") or "",
            "item_id": ex["raw_item_id"],
        })
    return out


def _persist_cluster(
    db: sqlite3.Connection,
    pipeline_run: str,
    cluster: Cluster,
    result: PipelineResult,
    log_fn: LogFn | None,
) -> None:
    """Phase D persistence for one cluster."""
    keyword = _derive_keyword(cluster, result)
    aliases = _derive_aliases(cluster, result)

    a4_scores = result.a4.scores if result.a4 else None
    llm_score = weighted_score(a4_scores) if a4_scores else 0.0
    opp_total = result.a4.total_score if result.a4 else None
    cluster_tier = tier(opp_total) if opp_total is not None else "cold"
    feasibility = result.a5.feasibility_score if result.a5 else None
    build_complexity = build_complexity_from_feasibility(feasibility)

    # Cross-run merge: if another run produced a niche whose keyword or aliases overlap
    # ours, use THAT niche's keyword for the upsert (prevents fragmentation).
    candidate_aliases = [keyword] + aliases
    existing_keyword = lookup_niche_by_alias_overlap(db, candidate_aliases)
    effective_keyword = existing_keyword or keyword

    niche_id = upsert_niche_candidate(
        db,
        effective_keyword,
        aliases,
        llm_score,
        _derive_reasoning(result),
        tool_concept=_derive_tool_concept(result),
        target_audience=(result.a2.who if result.a2 else "") or "",
        build_complexity=build_complexity,
        monetization=(
            f"{result.a5.revenue_model or 'unknown'}: "
            f"{result.a5.price_hypothesis or 'unknown'}"
        ) if result.a5 else "",
        pain_points=_derive_pain_points(cluster),
    )

    for ex in cluster.extractions:
        link_niche_item(db, niche_id, ex["raw_item_id"], effective_keyword, 1.0)

    analysis_id = insert_niche_analysis(
        db,
        niche_id=niche_id,
        pipeline_run=pipeline_run,
        cluster_id=cluster.cluster_id,
        verdict=result.verdict,
        confidence=(result.a6.confidence if result.a6 else None),
        opportunity_score=opp_total,
        weighted_score=llm_score,
        tier=cluster_tier,
        feasibility_score=feasibility,
        a2_aggregate=(result.a2.model_dump(mode="json") if result.a2 else None),
        a3_result=(result.a3.model_dump(mode="json") if result.a3 else None),
        a4_result=(result.a4.model_dump(mode="json") if result.a4 else None),
        a5_result=(result.a5.model_dump(mode="json") if result.a5 else None),
        a6_result=(result.a6.model_dump(mode="json") if result.a6 else None),
        a7_result=(result.a7.model_dump(mode="json") if result.a7 else None),
        a8_result=(result.a8.model_dump(mode="json") if result.a8 else None),
        failed_agents=result.failed_agents,
    )
    attach_latest_analysis(db, niche_id, analysis_id, result.verdict)

    if log_fn:
        log_fn(
            f"cluster={cluster.cluster_id[:8]} verdict={result.verdict} "
            f"score={opp_total}/70 tier={cluster_tier} niche={effective_keyword}"
        )


def run_phase_d(
    db: sqlite3.Connection,
    pipeline_run: str,
    pairs: list[tuple[Cluster, PipelineResult]],
    *,
    dry_run: bool = False,
    log_fn: LogFn | None = None,
) -> int:
    """Upsert niche_candidates + write niche_analyses. Returns count of persisted clusters."""
    if dry_run:
        if log_fn:
            log_fn(f"phase=D dry_run skipping {len(pairs)} clusters")
        return 0
    if log_fn:
        log_fn(f"phase=D persisting {len(pairs)} clusters")
    persisted = 0
    for cluster, result in pairs:
        try:
            _persist_cluster(db, pipeline_run, cluster, result, log_fn)
            persisted += 1
        except Exception as exc:  # never let one bad cluster kill the whole run
            logger.error(
                "phase_d_persist_failed",
                cluster_id=cluster.cluster_id,
                error=str(exc),
            )
            if log_fn:
                log_fn(f"cluster={cluster.cluster_id[:8]} D=FAIL {exc}")
    return persisted


# ============================================================================
# Top-level
# ============================================================================


def run_pipeline(
    db: sqlite3.Connection,
    settings,
    *,
    dry_run: bool = False,
    log_fn: LogFn | None = None,
    overrides: dict[str, LLMClient] | None = None,
    items_override: list[dict] | None = None,
    max_calls: int | None = None,
) -> dict[str, Any]:
    """Run all four phases. Returns a summary dict.

    - items_override: bypass DB lookup of unprocessed items (used by --test and --signal-id).
    - overrides: per-agent LLM client overrides (test injection).
    - max_calls: hard cap on LLM calls per run. None = use BudgetTracker.for_run default.
    """
    pipeline_run = str(uuid.uuid4())

    # Determine items
    if items_override is not None:
        items = items_override
    else:
        items = get_items_needing_a1(
            db, limit=500, max_age_days=settings.analysis_window_days
        )

    if not items:
        if log_fn:
            log_fn("pipeline_skipped reason=no_items")
        return {
            "pipeline_run": pipeline_run, "items": 0, "passed": 0,
            "clusters": 0, "persisted": 0, "budget_used": 0,
        }

    # Budget — placeholder cluster count; will refine after phase B
    placeholder_clusters = max(1, len(items) // 5)
    budget_cap = max_calls if max_calls is not None else BudgetTracker.for_run(
        len(items), placeholder_clusters
    )
    budget = BudgetTracker(budget_cap)

    if log_fn:
        log_fn(f"pipeline_run={pipeline_run} items={len(items)} budget={budget_cap}")

    try:
        passed = run_phase_a(
            db, settings, pipeline_run, items,
            dry_run=dry_run, overrides=overrides, budget=budget, log_fn=log_fn,
        )

        # In dry_run we never wrote extractions, so phase B has nothing to read.
        # Build an in-memory passed-extractions list for the dry path so the cluster +
        # deep phases still execute.
        if dry_run:
            in_memory: list[dict] = []
            for item in items:
                # Re-run-or-skip is fine; for --test we ran only one item anyway.
                resolver = _build_resolver(db, settings, overrides=overrides)
                _id, res = _phase_a_for_item(item, resolver, budget=None, log_fn=None)
                if res.a1 and res.a1.is_valid_signal and res.a2:
                    in_memory.append({
                        "raw_item_id": _id,
                        "a1": res.a1.model_dump(mode="json"),
                        "a2": res.a2.model_dump(mode="json"),
                    })
            extractions = in_memory
            clusters = cluster_extractions(
                extractions, refinement_client=None, log_fn=log_fn,
            )
        else:
            clusters = run_phase_b(
                db, settings, pipeline_run,
                dry_run=dry_run, overrides=overrides, budget=budget, log_fn=log_fn,
            )

        pairs = run_phase_c(
            db, settings, clusters,
            overrides=overrides, budget=budget, log_fn=log_fn,
        )

        persisted = run_phase_d(
            db, pipeline_run, pairs, dry_run=dry_run, log_fn=log_fn,
        )

    except BudgetExceeded as exc:
        if log_fn:
            log_fn(f"pipeline_aborted reason=budget_exceeded {exc}")
        return {
            "pipeline_run": pipeline_run, "items": len(items), "passed": -1,
            "clusters": -1, "persisted": -1, "budget_used": budget.count,
            "aborted": "budget_exceeded",
        }

    summary = {
        "pipeline_run": pipeline_run,
        "items": len(items),
        "passed": passed,
        "clusters": len(clusters),
        "persisted": persisted,
        "budget_used": budget.count,
        "budget_by_agent": dict(budget.by_agent),
    }
    if log_fn:
        log_fn(f"pipeline_done {summary}")
    return summary


def run_pipeline_on_signal(
    db: sqlite3.Connection,
    settings,
    raw_signal: dict,
    *,
    log_fn: LogFn | None = None,
    overrides: dict[str, LLMClient] | None = None,
) -> PipelineResult:
    """Convenience: run the full 8-agent pipeline on a single in-memory signal.

    Used by `python -m niche_radar analyze --test` and unit tests. Always dry-run.
    """
    resolver = _build_resolver(db, settings, overrides=overrides)
    budget = BudgetTracker(BudgetTracker.for_run(1, 1))

    a_result = run_single(raw_signal, resolver, budget_check=budget, log_fn=log_fn)
    if a_result.short_circuited_at:
        return a_result
    if a_result.a1 is None or a_result.a2 is None:
        return a_result

    # Synthetic "cluster" of one item for phase C
    cluster_ctx = {
        "raw_signal": raw_signal,
        "a1": a_result.a1,
        "a2": a_result.a2,
    }
    c_result = run_cluster(cluster_ctx, resolver, budget_check=budget, log_fn=log_fn)
    # Stitch back A1/A2 into the cluster result so callers see one full PipelineResult
    c_result.a1 = a_result.a1
    c_result.failed_agents = list(set(a_result.failed_agents + c_result.failed_agents))
    return c_result
