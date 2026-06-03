"""SQLite CRUD operations for entities, mentions, and velocity tracking."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import date, datetime, timedelta, timezone

ENTITY_TYPES = ("company", "product", "technology", "person", "category")


def upsert_entity(
    db: sqlite3.Connection,
    canonical_name: str,
    entity_type: str,
    aliases: list[str] | None = None,
    source: str | None = None,
) -> str:
    """Create or update an entity. Returns the entity ID."""
    now = datetime.now(timezone.utc).isoformat()

    row = db.execute(
        "SELECT id, aliases, mention_count FROM entities WHERE canonical_name=?",
        (canonical_name,),
    ).fetchone()

    if row:
        entity_id = row["id"]
        existing_aliases = json.loads(row["aliases"]) if row["aliases"] else []
        new_aliases = list(set(existing_aliases + (aliases or [])))
        new_count = row["mention_count"] + 1

        db.execute(
            "UPDATE entities SET aliases=?, mention_count=?, last_seen=? WHERE id=?",
            (json.dumps(new_aliases), new_count, now, entity_id),
        )

        if source:
            src_row = db.execute(
                "SELECT COUNT(DISTINCT ri.source) FROM entity_mentions em "
                "JOIN raw_items ri ON ri.id = em.raw_item_id "
                "WHERE em.entity_id = ?",
                (entity_id,),
            ).fetchone()
            src_count = src_row[0] if src_row else 0
            db.execute(
                "UPDATE entities SET source_diversity=? WHERE id=?",
                (src_count, entity_id),
            )

        db.commit()
        return entity_id

    entity_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO entities (id, type, canonical_name, aliases, first_seen, last_seen, mention_count) "
        "VALUES (?, ?, ?, ?, ?, ?, 1)",
        (entity_id, entity_type, canonical_name, json.dumps(aliases or []), now, now),
    )
    db.commit()
    return entity_id


def link_mention(
    db: sqlite3.Connection,
    entity_id: str,
    raw_item_id: str,
    sentiment: str = "neutral",
    relevance: float = 1.0,
) -> None:
    """Link an entity to a raw item via entity_mentions. Idempotent."""
    db.execute(
        "INSERT OR IGNORE INTO entity_mentions (entity_id, raw_item_id, sentiment, relevance) "
        "VALUES (?, ?, ?, ?)",
        (entity_id, raw_item_id, sentiment, relevance),
    )

    row = db.execute(
        "SELECT COUNT(DISTINCT ri.source) FROM entity_mentions em "
        "JOIN raw_items ri ON ri.id = em.raw_item_id "
        "WHERE em.entity_id = ?",
        (entity_id,),
    ).fetchone()
    source_count = row[0] if row else 0

    db.execute(
        "UPDATE entities SET source_diversity=? WHERE id=?",
        (source_count, entity_id),
    )
    db.commit()


def get_existing_entities_for_dedup(db: sqlite3.Connection) -> list[dict]:
    """Return all existing entities as dicts for dedup resolution."""
    rows = db.execute(
        "SELECT id, canonical_name, aliases FROM entities"
    ).fetchall()
    return [{"id": r["id"], "canonical_name": r["canonical_name"], "aliases": r["aliases"]} for r in rows]


def get_entities(
    db: sqlite3.Connection,
    entity_type: str | None = None,
    sort_by: str = "last_seen",
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """Paginated entity list with optional type filter."""
    valid_sorts = {"last_seen", "mentions", "velocity"}
    if sort_by not in valid_sorts:
        sort_by = "last_seen"
    sort_col = {
        "last_seen": "last_seen DESC",
        "mentions": "mention_count DESC",
        "velocity": "velocity_score DESC",
    }[sort_by]

    if entity_type and entity_type in ENTITY_TYPES:
        rows = db.execute(
            f"SELECT * FROM entities WHERE type=? ORDER BY {sort_col} LIMIT ? OFFSET ?",
            (entity_type, limit, offset),
        ).fetchall()
    else:
        rows = db.execute(
            f"SELECT * FROM entities ORDER BY {sort_col} LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()

    return [dict(r) for r in rows]


def get_entity_by_id(db: sqlite3.Connection, entity_id: str) -> dict | None:
    """Get a single entity with stats, recent mentions, and velocity history."""
    row = db.execute(
        "SELECT * FROM entities WHERE id=?", (entity_id,)
    ).fetchone()
    if not row:
        return None
    result = dict(row)
    result["aliases"] = json.loads(result["aliases"]) if result["aliases"] else []

    mentions = db.execute(
        "SELECT em.*, ri.title, ri.source, ri.url FROM entity_mentions em "
        "JOIN raw_items ri ON ri.id = em.raw_item_id "
        "WHERE em.entity_id=? ORDER BY em.extracted_at DESC LIMIT 20",
        (entity_id,),
    ).fetchall()
    result["recent_mentions"] = [dict(m) for m in mentions]

    vel_rows = db.execute(
        "SELECT * FROM entity_velocity WHERE entity_id=? ORDER BY week_start DESC LIMIT 8",
        (entity_id,),
    ).fetchall()
    result["velocity_history"] = [dict(v) for v in reversed(vel_rows)]

    return result


def get_trending_entities(
    db: sqlite3.Connection,
    limit: int = 10,
    entity_type: str | None = None,
) -> list[dict]:
    """Entities with highest velocity scores."""
    if entity_type and entity_type in ENTITY_TYPES:
        rows = db.execute(
            "SELECT * FROM entities WHERE type=? AND mention_count >= 2 "
            "ORDER BY velocity_score DESC LIMIT ?",
            (entity_type, limit),
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM entities WHERE mention_count >= 2 "
            "ORDER BY velocity_score DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_entity_mentions(
    db: sqlite3.Connection,
    entity_id: str,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """Paginated mentions for an entity."""
    rows = db.execute(
        "SELECT em.*, ri.title, ri.source, ri.url, ri.collected_at "
        "FROM entity_mentions em "
        "JOIN raw_items ri ON ri.id = em.raw_item_id "
        "WHERE em.entity_id=? ORDER BY em.extracted_at DESC LIMIT ? OFFSET ?",
        (entity_id, limit, offset),
    ).fetchall()
    return [dict(r) for r in rows]


def compute_entity_velocity(db: sqlite3.Connection) -> None:
    """Compute week-over-week velocity for all entities and persist."""
    today = date.today()
    this_week_start = today - timedelta(days=today.weekday())
    last_week_start = this_week_start - timedelta(weeks=1)

    entities = db.execute("SELECT id FROM entities").fetchall()

    for entity in entities:
        eid = entity["id"]

        this_week = db.execute(
            "SELECT COUNT(*) as cnt FROM entity_mentions WHERE entity_id=? AND extracted_at >= ?",
            (eid, this_week_start.isoformat()),
        ).fetchone()
        this_count = this_week["cnt"]

        this_sources = db.execute(
            "SELECT COUNT(DISTINCT ri.source) as cnt FROM entity_mentions em "
            "JOIN raw_items ri ON ri.id = em.raw_item_id "
            "WHERE em.entity_id=? AND em.extracted_at >= ?",
            (eid, this_week_start.isoformat()),
        ).fetchone()

        last_week = db.execute(
            "SELECT mention_count FROM entity_velocity WHERE entity_id=? AND week_start=?",
            (eid, last_week_start.isoformat()),
        ).fetchone()
        last_count = last_week["mention_count"] if last_week else 0

        if last_count > 0:
            score = ((this_count - last_count) / last_count) * 100
        elif this_count > 0:
            score = 100.0
        else:
            score = 0.0

        label = _velocity_label(score)

        db.execute(
            "INSERT OR REPLACE INTO entity_velocity "
            "(entity_id, week_start, mention_count, source_count, velocity_label, velocity_score) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (eid, this_week_start.isoformat(), this_count, this_sources["cnt"], label, score),
        )

        db.execute(
            "UPDATE entities SET velocity_score=? WHERE id=?",
            (score, eid),
        )

    db.commit()


def _velocity_label(score: float) -> str:
    if score > 100:
        return "surging"
    elif score > 25:
        return "growing"
    elif score >= -25:
        return "stable"
    else:
        return "declining"
