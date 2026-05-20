"""CRUD operations for the niche radar database."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone


def insert_collection_run(
    db: sqlite3.Connection, source: str, status: str = "running"
) -> str:
    """Insert a new collection run and return its ID."""
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
    """Mark a collection run as completed/failed."""
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
    """Insert or update a raw item (dedup by source+source_id). Returns item ID."""
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
        # Duplicate — update existing
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
    """Get raw items that haven't been linked to any niche yet."""
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
    niche_id: str,
    keyword: str,
    aliases: list[str] | None,
    embedding: bytes | None,
) -> None:
    """Insert or update a niche candidate."""
    now = datetime.now(timezone.utc).isoformat()
    aliases_json = json.dumps(aliases) if aliases else None
    try:
        db.execute(
            "INSERT INTO niche_candidates (id, keyword, aliases, embedding, first_seen, last_seen) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (niche_id, keyword, aliases_json, embedding, now, now),
        )
    except sqlite3.IntegrityError:
        db.execute(
            "UPDATE niche_candidates SET aliases=?, embedding=?, last_seen=?, "
            "occurrence_count=occurrence_count+1 WHERE id=?",
            (aliases_json, embedding, now, niche_id),
        )
    db.commit()


def link_niche_item(
    db: sqlite3.Connection,
    niche_id: str,
    raw_item_id: str,
    keyphrase: str,
    relevance_score: float,
) -> None:
    """Link a raw item to a niche candidate."""
    try:
        db.execute(
            "INSERT INTO niche_item_links (niche_id, raw_item_id, keyphrase, relevance_score) "
            "VALUES (?, ?, ?, ?)",
            (niche_id, raw_item_id, keyphrase, relevance_score),
        )
        db.commit()
    except sqlite3.IntegrityError:
        pass  # Already linked


def insert_niche_score(
    db: sqlite3.Connection,
    niche_id: str,
    engagement: float,
    search_trend: float,
    content_gap: float,
    market_traction: float,
    composite_score: float,
) -> str:
    """Insert a scored result for a niche."""
    score_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO niche_scores "
        "(id, niche_id, engagement, search_trend, content_gap, market_traction, composite_score) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (score_id, niche_id, engagement, search_trend, content_gap, market_traction, composite_score),
    )
    db.commit()
    return score_id


def get_active_niches(db: sqlite3.Connection) -> list[dict]:
    """Get all active niche candidates."""
    rows = db.execute(
        "SELECT id, keyword, aliases, status, first_seen, last_seen, occurrence_count "
        "FROM niche_candidates WHERE status='active' ORDER BY last_seen DESC"
    ).fetchall()
    return [
        {
            "id": r[0], "keyword": r[1],
            "aliases": json.loads(r[2]) if r[2] else [],
            "status": r[3], "first_seen": r[4],
            "last_seen": r[5], "occurrence_count": r[6],
        }
        for r in rows
    ]


def get_latest_scores(db: sqlite3.Connection) -> list[dict]:
    """Get the most recent score for each active niche."""
    rows = db.execute(
        "SELECT ns.id, ns.niche_id, nc.keyword, nc.aliases, "
        "ns.engagement, ns.search_trend, ns.content_gap, ns.market_traction, "
        "ns.composite_score, ns.scored_at, nc.first_seen, nc.last_seen "
        "FROM niche_scores ns "
        "JOIN niche_candidates nc ON ns.niche_id = nc.id "
        "WHERE nc.status = 'active' "
        "AND ns.scored_at = ("
        "  SELECT MAX(ns2.scored_at) FROM niche_scores ns2 WHERE ns2.niche_id = ns.niche_id"
        ") "
        "ORDER BY ns.composite_score DESC"
    ).fetchall()
    return [
        {
            "score_id": r[0], "niche_id": r[1], "keyword": r[2],
            "aliases": json.loads(r[3]) if r[3] else [],
            "engagement": r[4], "search_trend": r[5],
            "content_gap": r[6], "market_traction": r[7],
            "composite_score": r[8], "scored_at": r[9],
            "first_seen": r[10], "last_seen": r[11],
        }
        for r in rows
    ]


def get_niche_candidates_with_embeddings(db: sqlite3.Connection) -> list[dict]:
    """Return active niche candidates, including serialized embeddings."""
    rows = db.execute(
        "SELECT id, keyword, aliases, embedding, status, first_seen, last_seen, occurrence_count "
        "FROM niche_candidates WHERE status='active' ORDER BY last_seen DESC"
    ).fetchall()
    return [
        {
            "id": r[0], "keyword": r[1],
            "aliases": json.loads(r[2]) if r[2] else [],
            "embedding": r[3], "status": r[4],
            "first_seen": r[5], "last_seen": r[6],
            "occurrence_count": r[7],
        }
        for r in rows
    ]


def get_niche_items(db: sqlite3.Connection, niche_id: str) -> list[dict]:
    """Get raw items linked to a niche candidate."""
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


def get_item_scores(db: sqlite3.Connection, source: str | None = None) -> list[float]:
    """Return numeric raw-item scores, optionally filtered by source."""
    query = "SELECT score FROM raw_items WHERE score IS NOT NULL"
    params: tuple = ()
    if source:
        query += " AND source=?"
        params = (source,)
    rows = db.execute(query, params).fetchall()
    return [float(r[0]) for r in rows]


def get_trend_snapshots(db: sqlite3.Connection, niche_id: str) -> list[dict]:
    """Get stored trend snapshots for a niche candidate."""
    rows = db.execute(
        "SELECT source, data, snapshot_at FROM trend_snapshots WHERE niche_id=? ORDER BY snapshot_at ASC",
        (niche_id,),
    ).fetchall()
    return [
        {"source": r[0], "data": json.loads(r[1]) if r[1] else None, "snapshot_at": r[2]}
        for r in rows
    ]


def get_system_health(db: sqlite3.Connection) -> list[dict]:
    """Return the latest collection status for each configured source."""
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


def get_collection_run_count(db: sqlite3.Connection) -> int:
    """Return the total number of collection runs."""
    row = db.execute("SELECT COUNT(*) FROM collection_runs").fetchone()
    return int(row[0]) if row else 0


def get_raw_item_by_id(db: sqlite3.Connection, item_id: str) -> dict | None:
    """Return a single raw item by its UUID."""
    row = db.execute(
        "SELECT id, source, source_id, title, body, url, score, comment_count, metadata, collected_at "
        "FROM raw_items WHERE id=?",
        (item_id,),
    ).fetchone()
    if row is None:
        return None
    return {
        "id": row[0], "source": row[1], "source_id": row[2],
        "title": row[3], "body": row[4], "url": row[5],
        "score": row[6], "comment_count": row[7],
        "metadata": json.loads(row[8]) if row[8] else None,
        "collected_at": row[9],
    }


def insert_pipeline_result(
    db: sqlite3.Connection,
    raw_item_id: str | None,
    source: str,
    scraped_at: str | None,
    verdict: str,
    opportunity_score: float | None,
    tier: str | None,
    full_result: dict,
) -> str:
    """Persist a full pipeline result to the database."""
    result_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO pipeline_results "
        "(id, raw_item_id, source, scraped_at, verdict, opportunity_score, tier, full_result) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (result_id, raw_item_id, source, scraped_at, verdict, opportunity_score, tier,
         json.dumps(full_result)),
    )
    db.commit()
    return result_id


def get_pipeline_results(
    db: sqlite3.Connection,
    verdict: str | None = None,
    tier: str | None = None,
    source: str | None = None,
    limit: int = 100,
) -> list[dict]:
    """Query pipeline results with optional filters."""
    clauses: list[str] = []
    params: list = []
    if verdict:
        clauses.append("verdict=?")
        params.append(verdict)
    if tier:
        clauses.append("tier=?")
        params.append(tier)
    if source:
        clauses.append("source=?")
        params.append(source)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    params.append(limit)
    rows = db.execute(
        f"SELECT id, raw_item_id, source, scraped_at, verdict, opportunity_score, tier, "
        f"full_result, analyzed_at FROM pipeline_results {where} "
        f"ORDER BY analyzed_at DESC LIMIT ?",
        params,
    ).fetchall()
    return [
        {
            "id": r[0], "raw_item_id": r[1], "source": r[2], "scraped_at": r[3],
            "verdict": r[4], "opportunity_score": r[5], "tier": r[6],
            "full_result": json.loads(r[7]) if r[7] else None,
            "analyzed_at": r[8],
        }
        for r in rows
    ]


def get_pipeline_result_by_item(db: sqlite3.Connection, raw_item_id: str) -> dict | None:
    """Return the most recent pipeline result for a given raw_item_id."""
    row = db.execute(
        "SELECT id, raw_item_id, source, scraped_at, verdict, opportunity_score, tier, "
        "full_result, analyzed_at FROM pipeline_results WHERE raw_item_id=? "
        "ORDER BY analyzed_at DESC LIMIT 1",
        (raw_item_id,),
    ).fetchone()
    if row is None:
        return None
    return {
        "id": row[0], "raw_item_id": row[1], "source": row[2], "scraped_at": row[3],
        "verdict": row[4], "opportunity_score": row[5], "tier": row[6],
        "full_result": json.loads(row[7]) if row[7] else None,
        "analyzed_at": row[8],
    }
