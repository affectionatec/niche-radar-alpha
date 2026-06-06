"""Tests for SQLite WAL mode and concurrent access."""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

import pytest
from niche_radar.storage.database import get_db


def test_wal_mode_enabled(tmp_path: Path):
    """get_db() should set journal_mode=WAL."""
    db_path = str(tmp_path / "test.db")
    conn = get_db(f"sqlite:///{db_path}")
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode == "wal"
    conn.close()


def test_synchronous_normal(tmp_path: Path):
    """get_db() should set synchronous=NORMAL for WAL performance."""
    db_path = str(tmp_path / "test.db")
    conn = get_db(f"sqlite:///{db_path}")
    sync = conn.execute("PRAGMA synchronous").fetchone()[0]
    # synchronous=NORMAL is value 1
    assert sync == 1
    conn.close()


def test_row_factory_is_set(tmp_path: Path):
    """get_db() should set row_factory=sqlite3.Row for named column access."""
    db_path = str(tmp_path / "test.db")
    conn = get_db(f"sqlite:///{db_path}")
    assert conn.row_factory == sqlite3.Row
    conn.close()


def test_concurrent_reads_under_wal(tmp_path: Path):
    """Two separate connections can read concurrently under WAL mode without SQLITE_BUSY."""
    db_path = str(tmp_path / "test.db")
    conn_setup = get_db(f"sqlite:///{db_path}")

    # Write some data (need valid collection_run for FK)
    conn_setup.execute(
        "INSERT INTO collection_runs (id, source, status) VALUES ('run-1', 'reddit', 'completed')"
    )
    conn_setup.execute(
        "INSERT INTO raw_items (id, collection_run, source, source_id, title, body) "
        "VALUES ('item-1', 'run-1', 'reddit', 'abc', 'test', 'body')"
    )
    conn_setup.commit()
    conn_setup.close()

    errors = []

    def reader(results):
        """Each thread opens its own connection — per-thread as SQLite requires."""
        try:
            conn = sqlite3.connect(db_path)
            conn.execute("PRAGMA journal_mode=WAL")
            row = conn.execute("SELECT COUNT(*) FROM raw_items").fetchone()
            results.append(row[0])
            conn.close()
        except Exception as e:
            errors.append(str(e))

    results1, results2 = [], []
    t1 = threading.Thread(target=reader, args=(results1,))
    t2 = threading.Thread(target=reader, args=(results2,))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert errors == [], f"Concurrent reads failed: {errors}"
    assert results1 == [1]
    assert results2 == [1]


def test_migration_adds_llm_usage_columns(tmp_path: Path):
    """Migration should add cached_tokens, cache_write_tokens, niche_candidate_id to llm_usage."""
    db_path = str(tmp_path / "test.db")
    conn = get_db(f"sqlite:///{db_path}")

    cols = {r[1] for r in conn.execute("PRAGMA table_info(llm_usage)").fetchall()}
    assert "cached_tokens" in cols
    assert "cache_write_tokens" in cols
    assert "niche_candidate_id" in cols
    conn.close()


def test_migration_idempotent(tmp_path: Path):
    """Calling get_db() twice on the same DB should not fail."""
    db_path = str(tmp_path / "test.db")
    conn1 = get_db(f"sqlite:///{db_path}")
    conn1.close()

    # Second call should succeed without errors
    conn2 = get_db(f"sqlite:///{db_path}")
    conn2.close()
