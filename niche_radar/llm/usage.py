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


def record_usage(agent: str, model: str, usage: Any) -> None:
    """Record a single LLM call's usage. `usage` is the OpenAI-style usage object."""
    if usage is None:
        return
    prompt = getattr(usage, "prompt_tokens", 0) or 0
    completion = getattr(usage, "completion_tokens", 0) or 0
    total = getattr(usage, "total_tokens", 0) or (prompt + completion)

    if not hasattr(_local, "records"):
        _local.records = []
    _local.records.append(UsageRecord(
        agent=agent, model=model,
        prompt_tokens=prompt, completion_tokens=completion, total_tokens=total,
    ))


def flush_usage(db_path: str, pipeline_run: str) -> int:
    """Write accumulated usage records to the database. Returns count flushed."""
    records: list[UsageRecord] = getattr(_local, "records", [])
    if not records:
        return 0
    try:
        conn = sqlite3.connect(db_path)
        conn.executemany(
            "INSERT INTO llm_usage (pipeline_run, agent, model, prompt_tokens, completion_tokens, total_tokens) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [(pipeline_run, r.agent, r.model, r.prompt_tokens, r.completion_tokens, r.total_tokens) for r in records],
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
    }
