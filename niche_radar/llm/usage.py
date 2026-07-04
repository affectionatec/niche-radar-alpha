"""LLM usage tracking — records token counts per agent per pipeline run."""

from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger()

# Process-global accumulator — agents record usage from ThreadPoolExecutor
# worker threads (phases A and C run parallel), while flush_usage runs on the
# main thread. A thread-local store here silently loses every worker thread's
# records (found in the first real measured run, 2026-07-03: 203 LLM calls,
# zero llm_usage rows), so the accumulator must be shared and lock-guarded.
_lock = threading.Lock()
_records: list[UsageRecord] = []


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


def _cached_tokens(usage: Any) -> int:
    """Cache-hit prompt tokens across provider shapes: flat `cached_tokens`
    (Anthropic adapter / tests), OpenAI's `prompt_tokens_details.cached_tokens`,
    DeepSeek's top-level `prompt_cache_hit_tokens`."""
    cached = getattr(usage, "cached_tokens", 0) or 0
    if not cached:
        details = getattr(usage, "prompt_tokens_details", None)
        cached = (getattr(details, "cached_tokens", 0) or 0) if details is not None else 0
    if not cached:
        cached = getattr(usage, "prompt_cache_hit_tokens", 0) or 0
    return cached


def record_usage(agent: str, model: str, usage: Any, *, niche_id: str | None = None) -> None:
    """Record a single LLM call's usage. `usage` is the OpenAI-style usage object."""
    if usage is None:
        return
    prompt = getattr(usage, "prompt_tokens", 0) or 0
    completion = getattr(usage, "completion_tokens", 0) or 0
    total = getattr(usage, "total_tokens", 0) or (prompt + completion)
    cached = _cached_tokens(usage)
    cache_write = getattr(usage, "cache_write_tokens", 0) or 0

    record = UsageRecord(
        agent=agent, model=model,
        prompt_tokens=prompt, completion_tokens=completion, total_tokens=total,
        cached_tokens=cached, cache_write_tokens=cache_write,
        niche_candidate_id=niche_id,
    )
    with _lock:
        _records.append(record)


def flush_usage(db_path: str, pipeline_run: str) -> int:
    """Write accumulated usage records to the database. Returns count flushed.

    Drains records logged by any thread since the last flush.
    """
    with _lock:
        records: list[UsageRecord] = list(_records)
        _records.clear()
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
    return len(records)


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
