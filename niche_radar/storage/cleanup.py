"""Data retention cleanup — purge expired records."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import structlog

logger = structlog.get_logger()


def run_cleanup(
    db: sqlite3.Connection,
    settings,
    dry_run: bool = False,
) -> int:
    """Delete expired data according to retention settings. Returns total rows deleted."""
    now = datetime.now(timezone.utc)
    total = 0

    cutoffs = [
        (
            "raw_items",
            f"collected_at < '{(now - timedelta(days=settings.retention_raw_items)).isoformat()}'",
        ),
        (
            "niche_candidates",
            f"status = 'archived' AND last_seen < '{(now - timedelta(days=settings.retention_archived_niches)).isoformat()}'",
        ),
        (
            "niche_scores",
            f"scored_at < '{(now - timedelta(days=settings.retention_scores)).isoformat()}'",
        ),
        (
            "collection_runs",
            f"started_at < '{(now - timedelta(days=settings.retention_collection_runs)).isoformat()}'",
        ),
    ]

    for table, condition in cutoffs:
        count_row = db.execute(
            f"SELECT COUNT(*) FROM {table} WHERE {condition}"
        ).fetchone()
        count = count_row[0] if count_row else 0

        if count > 0 and not dry_run:
            db.execute(f"DELETE FROM {table} WHERE {condition}")
            db.commit()

        logger.info("cleanup_table", table=table, rows=count, dry_run=dry_run)
        total += count

    return total
