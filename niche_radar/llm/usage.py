"""LLM usage tracking — records token counts per agent per pipeline run."""

from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger()

# Thread-local accumulator — agents log usage here, flushed at end of run
_local = threading.local()


@dataclass
class UsageRecord:
    agent: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cached_tokens: int = 0
    cache_write_tokens: int = 0
    niche_candidate_id: str | None = None


def record_usage(agent: str, model: str, usage: Any, *, niche_id: str | None = None) -> None:
    """Record a single LLM call's usage. `usage` is the OpenAI-style usage object."""
    if usage is None:
        return
    prompt = getattr(usage, "prompt_tokens", 0) or 0
    completion = getattr(usage, "completion_tokens", 0) or 0
    total = getattr(usage, "total_tokens", 0) or (prompt + completion)
    cached = getattr(usage, "cached_tokens", 0) or 0
    cache_write = getattr(usage, "cache_write_tokens", 0) or 0

    if not hasattr(_local, "records"):
        _local.records = []
    _local.records.append(UsageRecord(
        agent=agent, model=model,
        prompt_tokens=prompt, completion_tokens=completion, total_tokens=total,
        cached_tokens=cached, cache_write_tokens=cache_write,
        niche_candidate_id=niche_id,
    ))


def flush_usage(db_path: str, pipeline_run: str) -> int:
    """Write accumulated usage records to the database. Returns count flushed."""
    records: list[UsageRecord] = getattr(_local, "records", [])
    if not records:
        return 0
    try:
        conn = sqlite3.connect(db_path)
        conn.executemany(
            "INSERT INTO llm_usage (pipeline_run, agent, model, prompt_tokens, completion_tokens, total_tokens, cached_tokens, cache_write_tokens, niche_candidate_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [(pipeline_run, r.agent, r.model, r.prompt_tokens, r.completion_tokens, r.total_tokens,
              r.cached_tokens, r.cache_write_tokens, r.niche_candidate_id) for r in records],
        )
        conn.commit()
        conn.close()
    except Exception as exc:
        logger.warning("flush_usage_failed", error=str(exc))
    count = len(records)
    _local.records = []
    return count


def get_usage_summary(db_path: str, days: int = 30) -> dict:
    """Get aggregated usage stats for the Cost Insights dashboard."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Per-agent totals
    by_agent = conn.execute(
        "SELECT agent, SUM(prompt_tokens) as prompt_total, SUM(completion_tokens) as completion_total, "
        "SUM(total_tokens) as token_total, COUNT(*) as call_count "
        "FROM llm_usage WHERE created_at >= datetime('now', ?) GROUP BY agent ORDER BY token_total DESC",
        (f"-{days} days",),
    ).fetchall()

    # Per-run totals
    by_run = conn.execute(
        "SELECT pipeline_run, SUM(total_tokens) as token_total, COUNT(*) as call_count, "
        "MIN(created_at) as started_at "
        "FROM llm_usage WHERE created_at >= datetime('now', ?) GROUP BY pipeline_run ORDER BY started_at DESC LIMIT 20",
        (f"-{days} days",),
    ).fetchall()

    # Daily totals
    daily = conn.execute(
        "SELECT date(created_at) as day, SUM(total_tokens) as token_total, COUNT(*) as call_count "
        "FROM llm_usage WHERE created_at >= datetime('now', ?) GROUP BY date(created_at) ORDER BY day DESC",
        (f"-{days} days",),
    ).fetchall()

    # Grand totals
    grand = conn.execute(
        "SELECT SUM(prompt_tokens) as prompt_total, SUM(completion_tokens) as completion_total, "
        "SUM(total_tokens) as token_total, COUNT(*) as call_count "
        "FROM llm_usage WHERE created_at >= datetime('now', ?)",
        (f"-{days} days",),
    ).fetchone()

    # Per-niche cost attribution
    per_niche = []
    try:
        per_niche_rows = conn.execute(
            "SELECT niche_candidate_id, SUM(total_tokens) as total_tokens, COUNT(*) as call_count "
            "FROM llm_usage WHERE niche_candidate_id IS NOT NULL AND created_at >= datetime('now', ?) "
            "GROUP BY niche_candidate_id ORDER BY total_tokens DESC",
            (f"-{days} days",),
        ).fetchall()
        per_niche = [dict(r) for r in per_niche_rows]
    except Exception:
        pass  # column may not exist in older schemas

    # Cache hit ratio
    cache_hit_ratio = 0.0
    try:
        cache_row = conn.execute(
            "SELECT COALESCE(SUM(cached_tokens), 0) as cached, COALESCE(SUM(prompt_tokens), 0) as total_prompt "
            "FROM llm_usage WHERE created_at >= datetime('now', ?)",
            (f"-{days} days",),
        ).fetchone()
        if cache_row and cache_row["total_prompt"] > 0:
            cache_hit_ratio = cache_row["cached"] / cache_row["total_prompt"]
    except Exception:
        pass  # column may not exist in older schemas

    # A1 filter rate
    a1_filter_rate = 0.0
    try:
        a1_row = conn.execute(
            "SELECT COUNT(*) as total, SUM(CASE WHEN a1_is_valid = 0 THEN 1 ELSE 0 END) as rejected "
            "FROM item_pain_extractions"
        ).fetchone()
        if a1_row and a1_row["total"] > 0:
            a1_filter_rate = a1_row["rejected"] / a1_row["total"]
    except Exception:
        pass  # table may not exist

    conn.close()

    return {
        "period_days": days,
        "totals": {
            "prompt_tokens": grand["prompt_total"] or 0,
            "completion_tokens": grand["completion_total"] or 0,
            "total_tokens": grand["token_total"] or 0,
            "call_count": grand["call_count"] or 0,
        },
        "by_agent": [dict(r) for r in by_agent],
        "by_run": [dict(r) for r in by_run],
        "daily": [dict(r) for r in daily],
        "per_niche": per_niche,
        "cache_hit_ratio": round(cache_hit_ratio, 4),
        "a1_filter_rate": round(a1_filter_rate, 4),
    }
