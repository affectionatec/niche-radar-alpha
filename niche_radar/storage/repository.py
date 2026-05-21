"""CRUD operations for the niche radar database."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone


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
    posted_at: str | None = None,
) -> str:
    item_id = str(uuid.uuid4())
    meta_json = json.dumps(metadata) if metadata else None
    try:
        db.execute(
            "INSERT INTO raw_items "
            "(id, collection_run, source, source_id, title, body, url, score, comment_count, metadata, posted_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (item_id, collection_run, source, source_id, title, body, url, score, comment_count, meta_json, posted_at),
        )
    except sqlite3.IntegrityError:
        # Update existing — preserve original posted_at if the new value is None
        db.execute(
            "UPDATE raw_items SET title=?, body=?, score=?, comment_count=?, metadata=?, "
            "posted_at=COALESCE(?, posted_at), collected_at=CURRENT_TIMESTAMP "
            "WHERE source=? AND source_id=?",
            (title, body, score, comment_count, meta_json, posted_at, source, source_id),
        )
        row = db.execute(
            "SELECT id FROM raw_items WHERE source=? AND source_id=?",
            (source, source_id),
        ).fetchone()
        item_id = row[0] if row else item_id
    db.commit()
    return item_id


def get_unprocessed_items(
    db: sqlite3.Connection,
    limit: int = 500,
    max_age_days: int | None = None,
) -> list[dict]:
    """Get unprocessed raw items posted within the freshness window.

    Items without a posted_at are excluded if a window is specified (we have no way to
    confirm they're fresh). Pass max_age_days=None to skip the freshness filter.
    """
    if max_age_days is not None:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=max_age_days)).isoformat()
        rows = db.execute(
            "SELECT ri.id, ri.source, ri.source_id, ri.title, ri.body, ri.url, ri.score, "
            "ri.comment_count, ri.metadata, ri.collected_at, ri.posted_at "
            "FROM raw_items ri "
            "LEFT JOIN niche_item_links nil ON ri.id = nil.raw_item_id "
            "WHERE nil.raw_item_id IS NULL "
            "AND ri.posted_at IS NOT NULL AND ri.posted_at >= ? "
            "ORDER BY ri.posted_at DESC LIMIT ?",
            (cutoff, limit),
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT ri.id, ri.source, ri.source_id, ri.title, ri.body, ri.url, ri.score, "
            "ri.comment_count, ri.metadata, ri.collected_at, ri.posted_at "
            "FROM raw_items ri "
            "LEFT JOIN niche_item_links nil ON ri.id = nil.raw_item_id "
            "WHERE nil.raw_item_id IS NULL "
            "ORDER BY COALESCE(ri.posted_at, ri.collected_at) DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [
        {
            "id": r[0], "source": r[1], "source_id": r[2],
            "title": r[3], "body": r[4], "url": r[5],
            "score": r[6], "comment_count": r[7],
            "metadata": json.loads(r[8]) if r[8] else None,
            "collected_at": r[9], "posted_at": r[10],
        }
        for r in rows
    ]


def archive_stale_niches(db: sqlite3.Connection, max_age_days: int) -> int:
    """Mark niches whose last_seen is older than max_age_days as archived. Returns count."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=max_age_days)).isoformat()
    cur = db.execute(
        "UPDATE niche_candidates SET status='archived' "
        "WHERE status='active' AND last_seen < ?",
        (cutoff,),
    )
    db.commit()
    return cur.rowcount or 0


def _parse_timestamp(value: str | None) -> datetime | None:
    """Parse either ISO-8601 ('2026-05-17T08:08:03+00:00') or SQLite naive ('2026-05-17 08:08:03')."""
    if not value:
        return None
    s = str(value).replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        # Older SQLite default format with space instead of T
        try:
            dt = datetime.fromisoformat(s.replace(" ", "T", 1))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def get_freshness_summary(db: sqlite3.Connection) -> dict:
    """Per-source freshness snapshot: count, oldest/newest posted_at, newest age in hours."""
    rows = db.execute(
        "SELECT source, COUNT(*), MIN(posted_at), MAX(posted_at) "
        "FROM raw_items WHERE posted_at IS NOT NULL "
        "GROUP BY source"
    ).fetchall()
    now = datetime.now(timezone.utc)
    sources = []
    for r in rows:
        source, count, oldest, newest = r
        newest_age_h = None
        newest_dt = _parse_timestamp(newest)
        if newest_dt is not None:
            newest_age_h = (now - newest_dt).total_seconds() / 3600
        sources.append({
            "source": source,
            "items": count,
            "oldest_posted": oldest,
            "newest_posted": newest,
            "newest_age_hours": round(newest_age_h, 1) if newest_age_h is not None else None,
        })
    return {"sources": sources}


def upsert_niche_candidate(
    db: sqlite3.Connection,
    keyword: str,
    aliases: list[str] | None,
    llm_score: float,
    llm_reasoning: str,
    *,
    tool_concept: str = "",
    target_audience: str = "",
    build_complexity: int | None = None,
    monetization: str = "",
    pain_points: list[dict] | None = None,
) -> str:
    """Insert or update AI-tool opportunity by keyword (dedup). Returns niche_id."""
    now = datetime.now(timezone.utc).isoformat()
    keyword_norm = keyword.lower().strip()
    aliases_json = json.dumps(aliases) if aliases else None
    pain_points_json = json.dumps(pain_points) if pain_points else None

    row = db.execute(
        "SELECT id FROM niche_candidates WHERE keyword=?", (keyword_norm,)
    ).fetchone()

    if row:
        niche_id = row[0]
        db.execute(
            "UPDATE niche_candidates SET aliases=?, llm_score=?, llm_reasoning=?, "
            "tool_concept=?, target_audience=?, build_complexity=?, monetization=?, pain_points=?, "
            "last_seen=?, occurrence_count=occurrence_count+1 WHERE id=?",
            (
                aliases_json, llm_score, llm_reasoning,
                tool_concept, target_audience, build_complexity, monetization, pain_points_json,
                now, niche_id,
            ),
        )
    else:
        niche_id = str(uuid.uuid4())
        db.execute(
            "INSERT INTO niche_candidates "
            "(id, keyword, aliases, llm_score, llm_reasoning, "
            "tool_concept, target_audience, build_complexity, monetization, pain_points, "
            "first_seen, last_seen) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                niche_id, keyword_norm, aliases_json, llm_score, llm_reasoning,
                tool_concept, target_audience, build_complexity, monetization, pain_points_json,
                now, now,
            ),
        )
    db.commit()
    return niche_id


def _build_niche_dict(row: tuple) -> dict:
    return {
        "niche_id": row[0],
        "keyword": row[1],
        "aliases": json.loads(row[2]) if row[2] else [],
        "llm_score": row[3] or 0.0,
        "llm_reasoning": row[4] or "",
        "tool_concept": row[5] or "",
        "target_audience": row[6] or "",
        "build_complexity": row[7],
        "monetization": row[8] or "",
        "pain_points": json.loads(row[9]) if row[9] else [],
        "first_seen": row[10],
        "last_seen": row[11],
        "occurrence_count": row[12],
    }


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


_NICHE_COLUMNS = (
    "id, keyword, aliases, llm_score, llm_reasoning, "
    "tool_concept, target_audience, build_complexity, monetization, pain_points, "
    "first_seen, last_seen, occurrence_count"
)


def get_active_niches_with_scores(db: sqlite3.Connection) -> list[dict]:
    """Return all active AI-tool opportunities ranked by build-priority (score x quick-build)."""
    rows = db.execute(
        f"SELECT {_NICHE_COLUMNS} FROM niche_candidates WHERE status='active' "
        "ORDER BY (llm_score * (6 - COALESCE(build_complexity, 3))) DESC, llm_score DESC"
    ).fetchall()
    return [_build_niche_dict(r) for r in rows]


def get_niche_by_id(db: sqlite3.Connection, niche_id: str) -> dict | None:
    row = db.execute(
        f"SELECT {_NICHE_COLUMNS} FROM niche_candidates WHERE id=?",
        (niche_id,),
    ).fetchone()
    if not row:
        return None
    return _build_niche_dict(row)


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
