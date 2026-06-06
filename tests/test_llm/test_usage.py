"""Tests for LLM usage tracking — record_usage, flush_usage, get_usage_summary."""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

import pytest
from niche_radar.llm.usage import (
    UsageRecord,
    flush_usage,
    get_usage_summary,
    record_usage,
)


class FakeUsage:
    """Mock OpenAI-style usage object."""
    def __init__(self, prompt_tokens=100, completion_tokens=50, total_tokens=150):
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens


# ── record_usage ─────────────────────────────────────────────────────────


def test_record_usage_stores_on_thread_local():
    record_usage("a1", "gpt-4", FakeUsage(100, 50, 150))
    from niche_radar.llm.usage import _local
    assert len(_local.records) == 1
    r = _local.records[0]
    assert r.agent == "a1"
    assert r.model == "gpt-4"
    assert r.prompt_tokens == 100
    assert r.completion_tokens == 50
    assert r.total_tokens == 150
    _local.records = []


def test_record_usage_noop_on_none_usage():
    record_usage("a1", "gpt-4", None)
    from niche_radar.llm.usage import _local
    assert not hasattr(_local, "records") or _local.records == []


def test_record_usage_computes_total_if_missing():
    record_usage("a1", "gpt-4", FakeUsage(30, 20, 0))
    from niche_radar.llm.usage import _local
    r = _local.records[0]
    assert r.total_tokens == 50  # 30 + 20
    _local.records = []


# ── flush_usage ──────────────────────────────────────────────────────────


def test_flush_usage_persists_to_db(tmp_path: Path):
    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS llm_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pipeline_run TEXT,
            agent TEXT,
            model TEXT,
            prompt_tokens INTEGER DEFAULT 0,
            completion_tokens INTEGER DEFAULT 0,
            total_tokens INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    conn.close()

    record_usage("a1", "gpt-4", FakeUsage(100, 50, 150))
    record_usage("a2", "gpt-4", FakeUsage(200, 100, 300))

    count = flush_usage(db_path, "run-001")
    assert count == 2

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM llm_usage ORDER BY agent").fetchall()
    assert len(rows) == 2
    assert rows[0]["agent"] == "a1"
    assert rows[0]["pipeline_run"] == "run-001"
    assert rows[0]["prompt_tokens"] == 100
    assert rows[1]["agent"] == "a2"
    assert rows[1]["completion_tokens"] == 100
    conn.close()


def test_flush_usage_clears_records_after_flush():
    record_usage("a1", "model", FakeUsage())
    from niche_radar.llm.usage import _local

    db_path = str(Path("/tmp") / "test_flush_clear.db")
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS llm_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pipeline_run TEXT, agent TEXT, model TEXT,
            prompt_tokens INTEGER DEFAULT 0, completion_tokens INTEGER DEFAULT 0,
            total_tokens INTEGER DEFAULT 0, created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    conn.close()

    flush_usage(db_path, "run-002")
    assert _local.records == []


def test_flush_usage_no_records_returns_zero(tmp_path: Path):
    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS llm_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pipeline_run TEXT, agent TEXT, model TEXT,
            prompt_tokens INTEGER DEFAULT 0, completion_tokens INTEGER DEFAULT 0,
            total_tokens INTEGER DEFAULT 0, created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    conn.close()

    from niche_radar.llm.usage import _local
    _local.records = []
    count = flush_usage(db_path, "run-003")
    assert count == 0


# ── get_usage_summary ────────────────────────────────────────────────────


def test_get_usage_summary_aggregates_correctly(tmp_path: Path):
    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS llm_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pipeline_run TEXT, agent TEXT, model TEXT,
            prompt_tokens INTEGER DEFAULT 0, completion_tokens INTEGER DEFAULT 0,
            total_tokens INTEGER DEFAULT 0, created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute(
        "INSERT INTO llm_usage (pipeline_run, agent, model, prompt_tokens, completion_tokens, total_tokens) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("run-a", "a1", "gpt-4", 100, 50, 150),
    )
    conn.execute(
        "INSERT INTO llm_usage (pipeline_run, agent, model, prompt_tokens, completion_tokens, total_tokens) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("run-a", "a4", "gpt-4", 200, 100, 300),
    )
    conn.commit()
    conn.close()

    summary = get_usage_summary(db_path, days=365)

    assert summary["period_days"] == 365
    assert summary["totals"]["total_tokens"] == 450
    assert summary["totals"]["call_count"] == 2
    assert len(summary["by_agent"]) == 2
    assert len(summary["by_run"]) == 1
    assert summary["by_run"][0]["pipeline_run"] == "run-a"
