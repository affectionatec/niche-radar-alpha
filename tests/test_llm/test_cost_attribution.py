"""Tests for P4: Cost & Token Observability — per-niche attribution + cache tracking."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from niche_radar.llm.usage import (
    UsageRecord,
    flush_usage,
    get_usage_summary,
    record_usage,
)


def _create_usage_table(db_path: str) -> None:
    """Create the llm_usage table with new P4 columns."""
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS llm_usage (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            pipeline_run        TEXT,
            agent               TEXT NOT NULL,
            model               TEXT NOT NULL,
            prompt_tokens       INTEGER NOT NULL DEFAULT 0,
            completion_tokens   INTEGER NOT NULL DEFAULT 0,
            total_tokens        INTEGER NOT NULL DEFAULT 0,
            cached_tokens       INTEGER NOT NULL DEFAULT 0,
            cache_write_tokens  INTEGER NOT NULL DEFAULT 0,
            niche_candidate_id  TEXT,
            created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


class FakeUsage:
    def __init__(self, prompt_tokens=100, completion_tokens=50, total_tokens=150,
                 cached_tokens=0, cache_write_tokens=0):
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens
        self.cached_tokens = cached_tokens
        self.cache_write_tokens = cache_write_tokens


# ── P4.1: Per-niche cost attribution ────────────────────────────────────


def test_record_usage_with_niche_id():
    """record_usage accepts optional niche_id parameter."""
    record_usage("a4", "gpt-4", FakeUsage(), niche_id="niche-001")
    from niche_radar.llm.usage import _local
    r = _local.records[-1]
    assert r.niche_candidate_id == "niche-001"
    _local.records = []


def test_record_usage_without_niche_id_defaults_to_none():
    record_usage("a1", "gpt-4", FakeUsage())
    from niche_radar.llm.usage import _local
    r = _local.records[-1]
    assert r.niche_candidate_id is None
    _local.records = []


def test_flush_usage_persists_niche_id(tmp_path: Path):
    db_path = str(tmp_path / "test.db")
    _create_usage_table(db_path)

    record_usage("a4", "gpt-4", FakeUsage(100, 50, 150), niche_id="niche-001")
    record_usage("a1", "gpt-4", FakeUsage(80, 30, 110))

    flush_usage(db_path, "run-001")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT agent, niche_candidate_id FROM llm_usage ORDER BY agent").fetchall()
    assert rows[0]["agent"] == "a1"
    assert rows[0]["niche_candidate_id"] is None
    assert rows[1]["agent"] == "a4"
    assert rows[1]["niche_candidate_id"] == "niche-001"
    conn.close()


def test_get_usage_summary_includes_per_niche(tmp_path: Path):
    db_path = str(tmp_path / "test.db")
    _create_usage_table(db_path)

    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO llm_usage (pipeline_run, agent, model, prompt_tokens, completion_tokens, total_tokens, niche_candidate_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("run-a", "a4", "gpt-4", 100, 50, 150, "niche-001"),
    )
    conn.execute(
        "INSERT INTO llm_usage (pipeline_run, agent, model, prompt_tokens, completion_tokens, total_tokens, niche_candidate_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("run-a", "a5", "gpt-4", 200, 100, 300, "niche-001"),
    )
    conn.execute(
        "INSERT INTO llm_usage (pipeline_run, agent, model, prompt_tokens, completion_tokens, total_tokens) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("run-a", "a1", "gpt-4", 50, 20, 70),
    )
    conn.commit()
    conn.close()

    summary = get_usage_summary(db_path, days=365)
    assert "per_niche" in summary
    assert len(summary["per_niche"]) == 1
    niche_cost = summary["per_niche"][0]
    assert niche_cost["niche_candidate_id"] == "niche-001"
    assert niche_cost["total_tokens"] == 450
    assert niche_cost["call_count"] == 2


# ── P4.2: Prompt cache tracking ─────────────────────────────────────────


def test_record_usage_captures_cache_tokens():
    record_usage("a1", "gpt-4", FakeUsage(100, 50, 150, cached_tokens=40, cache_write_tokens=60))
    from niche_radar.llm.usage import _local
    r = _local.records[-1]
    assert r.cached_tokens == 40
    assert r.cache_write_tokens == 60
    _local.records = []


def test_flush_usage_persists_cache_tokens(tmp_path: Path):
    db_path = str(tmp_path / "test.db")
    _create_usage_table(db_path)

    record_usage("a1", "gpt-4", FakeUsage(100, 50, 150, cached_tokens=40, cache_write_tokens=60))
    flush_usage(db_path, "run-001")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT cached_tokens, cache_write_tokens FROM llm_usage").fetchone()
    assert row["cached_tokens"] == 40
    assert row["cache_write_tokens"] == 60
    conn.close()


def test_get_usage_summary_includes_cache_hit_ratio(tmp_path: Path):
    db_path = str(tmp_path / "test.db")
    _create_usage_table(db_path)

    conn = sqlite3.connect(db_path)
    # 2 calls: first has 40 cached of 100 prompt, second has 0 cached of 100 prompt
    conn.execute(
        "INSERT INTO llm_usage (pipeline_run, agent, model, prompt_tokens, completion_tokens, total_tokens, cached_tokens, cache_write_tokens) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("run-a", "a1", "gpt-4", 100, 50, 150, 40, 60),
    )
    conn.execute(
        "INSERT INTO llm_usage (pipeline_run, agent, model, prompt_tokens, completion_tokens, total_tokens, cached_tokens, cache_write_tokens) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("run-a", "a2", "gpt-4", 100, 50, 150, 0, 0),
    )
    conn.commit()
    conn.close()

    summary = get_usage_summary(db_path, days=365)
    assert "cache_hit_ratio" in summary
    # 40 cached out of 200 total prompt tokens = 0.2
    assert abs(summary["cache_hit_ratio"] - 0.2) < 0.01


# ── P4.3: A1 filter rate ────────────────────────────────────────────────


def test_get_usage_summary_includes_a1_filter_rate(tmp_path: Path):
    """Summary should include what % of items A1 filters out."""
    db_path = str(tmp_path / "test.db")
    _create_usage_table(db_path)

    # Also need item_pain_extractions table for A1 filter rate
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS item_pain_extractions (
            raw_item_id TEXT PRIMARY KEY,
            pipeline_run TEXT,
            a1_is_valid INTEGER,
            a1_confidence REAL,
            a1_signal_type TEXT,
            a1_result JSON,
            a2_result JSON,
            error TEXT,
            extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # 3 items: 2 passed A1, 1 rejected
    conn.execute("INSERT INTO item_pain_extractions (raw_item_id, pipeline_run, a1_is_valid) VALUES (?, ?, ?)",
                 ("item-1", "run-a", 1))
    conn.execute("INSERT INTO item_pain_extractions (raw_item_id, pipeline_run, a1_is_valid) VALUES (?, ?, ?)",
                 ("item-2", "run-a", 1))
    conn.execute("INSERT INTO item_pain_extractions (raw_item_id, pipeline_run, a1_is_valid) VALUES (?, ?, ?)",
                 ("item-3", "run-a", 0))
    conn.commit()
    conn.close()

    summary = get_usage_summary(db_path, days=365)
    assert "a1_filter_rate" in summary
    # 1 out of 3 rejected = 33.3%
    assert abs(summary["a1_filter_rate"] - 0.333) < 0.01
