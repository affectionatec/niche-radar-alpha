"""CRUD operations for the niche radar database."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone


def insert_collection_run(
    db: sqlite3.Connection, source: str, status: str = "running"
) -> str:
    run_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO collection_runs (id, source, status) VALUES (?, ?, ?)",
        (run_id, source, status),
    )
    db.commit()
    return run_id


def complete_collection_run(
    db: sqlite3.Connection,
    run_id: str,
    status: str,
    items_collected: int,
    error_message: str | None = None,
) -> None:
    db.execute(
        "UPDATE collection_runs SET status=?, items_collected=?, error_message=?, "
        "completed_at=CURRENT_TIMESTAMP WHERE id=?",
        (status, items_collected, error_message, run_id),
    )
    db.commit()


def upsert_raw_item(
    db: sqlite3.Connection,
    collection_run: str,
    source: str,
    source_id: str,
    title: str | None,
    body: str | None,
    url: str | None,
    score: int | None,
    comment_count: int | None,
    metadata: dict | None,
) -> str:
    item_id = str(uuid.uuid4())
    meta_json = json.dumps(metadata) if metadata else None
    try:
        db.execute(
            "INSERT INTO raw_items "
            "(id, collection_run, source, source_id, title, body, url, score, comment_count, metadata) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (item_id, collection_run, source, source_id, title, body, url, score, comment_count, meta_json),
        )
    except sqlite3.IntegrityError:
        db.execute(
            "UPDATE raw_items SET title=?, body=?, score=?, comment_count=?, metadata=?, "
            "collected_at=CURRENT_TIMESTAMP WHERE source=? AND source_id=?",
            (title, body, score, comment_count, meta_json, source, source_id),
        )
        row = db.execute(
            "SELECT id FROM raw_items WHERE source=? AND source_id=?",
            (source, source_id),
        ).fetchone()
        item_id = row[0] if row else item_id
    db.commit()
    return item_id


def get_unprocessed_items(db: sqlite3.Connection, limit: int = 500) -> list[dict]:
    """Get raw items not yet linked to any niche."""
    rows = db.execute(
        "SELECT ri.id, ri.source, ri.source_id, ri.title, ri.body, ri.url, ri.score, "
        "ri.comment_count, ri.metadata, ri.collected_at "
        "FROM raw_items ri "
        "LEFT JOIN niche_item_links nil ON ri.id = nil.raw_item_id "
        "WHERE nil.raw_item_id IS NULL "
        "ORDER BY ri.collected_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [
        {
            "id": r[0], "source": r[1], "source_id": r[2],
            "title": r[3], "body": r[4], "url": r[5],
            "score": r[6], "comment_count": r[7],
            "metadata": json.loads(r[8]) if r[8] else None,
            "collected_at": r[9],
        }
        for r in rows
    ]


def upsert_niche_candidate(
    db: sqlite3.Connection,
    keyword: str,
    aliases: list[str] | None,
    llm_score: float,
    llm_reasoning: str,
) -> str:
    """Insert or update niche by keyword (dedup). Returns niche_id."""
    now = datetime.now(timezone.utc).isoformat()
    keyword_norm = keyword.lower().strip()
    aliases_json = json.dumps(aliases) if aliases else None

    row = db.execute(
        "SELECT id FROM niche_candidates WHERE keyword=?", (keyword_norm,)
    ).fetchone()

    if row:
        niche_id = row[0]
        db.execute(
            "UPDATE niche_candidates SET aliases=?, llm_score=?, llm_reasoning=?, "
            "last_seen=?, occurrence_count=occurrence_count+1 WHERE id=?",
            (aliases_json, llm_score, llm_reasoning, now, niche_id),
        )
    else:
        niche_id = str(uuid.uuid4())
        db.execute(
            "INSERT INTO niche_candidates "
            "(id, keyword, aliases, llm_score, llm_reasoning, first_seen, last_seen) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (niche_id, keyword_norm, aliases_json, llm_score, llm_reasoning, now, now),
        )
    db.commit()
    return niche_id


def link_niche_item(
    db: sqlite3.Connection,
    niche_id: str,
    raw_item_id: str,
    keyphrase: str,
    relevance_score: float,
) -> None:
    try:
        db.execute(
            "INSERT INTO niche_item_links (niche_id, raw_item_id, keyphrase, relevance_score) "
            "VALUES (?, ?, ?, ?)",
            (niche_id, raw_item_id, keyphrase, relevance_score),
        )
        db.commit()
    except sqlite3.IntegrityError:
        pass


def get_active_niches_with_scores(db: sqlite3.Connection) -> list[dict]:
    """Return all active niches ordered by LLM score descending."""
    rows = db.execute(
        "SELECT id, keyword, aliases, llm_score, llm_reasoning, "
        "first_seen, last_seen, occurrence_count "
        "FROM niche_candidates WHERE status='active' "
        "ORDER BY llm_score DESC"
    ).fetchall()
    return [
        {
            "niche_id": r[0], "keyword": r[1],
            "aliases": json.loads(r[2]) if r[2] else [],
            "llm_score": r[3] or 0.0,
            "llm_reasoning": r[4] or "",
            "first_seen": r[5], "last_seen": r[6],
            "occurrence_count": r[7],
        }
        for r in rows
    ]


def get_niche_by_id(db: sqlite3.Connection, niche_id: str) -> dict | None:
    row = db.execute(
        "SELECT id, keyword, aliases, llm_score, llm_reasoning, "
        "first_seen, last_seen, occurrence_count "
        "FROM niche_candidates WHERE id=?",
        (niche_id,),
    ).fetchone()
    if not row:
        return None
    return {
        "niche_id": row[0], "keyword": row[1],
        "aliases": json.loads(row[2]) if row[2] else [],
        "llm_score": row[3] or 0.0,
        "llm_reasoning": row[4] or "",
        "first_seen": row[5], "last_seen": row[6],
        "occurrence_count": row[7],
    }


def get_niche_items(db: sqlite3.Connection, niche_id: str) -> list[dict]:
    rows = db.execute(
        "SELECT ri.id, ri.source, ri.source_id, ri.title, ri.body, ri.url, ri.score, "
        "ri.comment_count, ri.metadata, ri.collected_at, nil.keyphrase, nil.relevance_score "
        "FROM niche_item_links nil "
        "JOIN raw_items ri ON ri.id = nil.raw_item_id "
        "WHERE nil.niche_id=? ORDER BY ri.collected_at DESC",
        (niche_id,),
    ).fetchall()
    return [
        {
            "id": r[0], "source": r[1], "source_id": r[2],
            "title": r[3], "body": r[4], "url": r[5],
            "score": r[6], "comment_count": r[7],
            "metadata": json.loads(r[8]) if r[8] else None,
            "collected_at": r[9], "keyphrase": r[10],
            "relevance_score": r[11],
        }
        for r in rows
    ]


def get_system_health(db: sqlite3.Connection) -> list[dict]:
    sources = ["reddit", "google_trends", "hn", "github", "youtube"]
    latest_rows = db.execute(
        "SELECT cr.source, cr.status, cr.started_at, cr.items_collected "
        "FROM collection_runs cr "
        "WHERE cr.started_at = ("
        "  SELECT MAX(cr2.started_at) FROM collection_runs cr2 WHERE cr2.source = cr.source"
        ")"
    ).fetchall()
    latest = {r[0]: r for r in latest_rows}
    health = []
    for source in sources:
        row = latest.get(source)
        if row is None:
            health.append({"source": source, "status": "MISSING", "last_run": "-", "items": 0})
            continue
        status = "OK" if row[1] == "completed" else row[1].upper()
        health.append({"source": source, "status": status, "last_run": row[2], "items": row[3] or 0})
    return health


def get_app_setting(db: sqlite3.Connection, key: str) -> str | None:
    row = db.execute("SELECT value FROM app_settings WHERE key=?", (key,)).fetchone()
    return row[0] if row else None


def set_app_setting(db: sqlite3.Connection, key: str, value: str) -> None:
    db.execute(
        "INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)", (key, value)
    )
    db.commit()
