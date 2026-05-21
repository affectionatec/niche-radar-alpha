"""Trend velocity / momentum tracking for niche_candidates.

Computes week-over-week change in raw_item mentions per niche and labels each
niche as "growing" / "stable" / "declining". Persists to three columns on
niche_candidates (added in the v3 migration).

No LLM involvement — pure SQL aggregation over raw_items.posted_at.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone


def compute_momentum(
    db: sqlite3.Connection,
    niche_id: str,
    window_days: int = 7,
) -> dict:
    """Return a momentum snapshot for one niche.

    Counts raw_items linked to the niche via niche_item_links:
      - this_week: items posted in [now-7d, now]
      - last_week: items posted in [now-14d, now-7d]

    Uses Laplace smoothing (+1 to both) so brand-new niches with no history
    don't divide by zero and don't artificially look "growing".
    """
    now = datetime.now(timezone.utc)
    this_start = (now - timedelta(days=window_days)).isoformat()
    last_start = (now - timedelta(days=window_days * 2)).isoformat()

    this_week = db.execute(
        """
        SELECT COUNT(*) FROM niche_item_links nil
        JOIN raw_items ri ON nil.raw_item_id = ri.id
        WHERE nil.niche_id = ? AND ri.posted_at >= ?
        """,
        (niche_id, this_start),
    ).fetchone()[0] or 0

    last_week = db.execute(
        """
        SELECT COUNT(*) FROM niche_item_links nil
        JOIN raw_items ri ON nil.raw_item_id = ri.id
        WHERE nil.niche_id = ? AND ri.posted_at >= ? AND ri.posted_at < ?
        """,
        (niche_id, last_start, this_start),
    ).fetchone()[0] or 0

    ratio = (this_week + 1) / (last_week + 1)

    if ratio > 1.5:
        label = "growing"
    elif ratio < 0.6:
        label = "declining"
    else:
        label = "stable"

    return {
        "this_week": this_week,
        "last_week": last_week,
        "ratio": round(ratio, 3),
        "label": label,
    }


def update_momentum_for_all_niches(
    db: sqlite3.Connection,
    window_days: int = 7,
) -> int:
    """Compute and persist momentum for every active niche_candidate.

    Writes to niche_candidates.momentum_ratio, .momentum_label, .momentum_updated_at.
    Returns the count of niches updated.
    """
    niche_ids = [
        r[0]
        for r in db.execute(
            "SELECT id FROM niche_candidates WHERE status='active'"
        ).fetchall()
    ]
    updated_at = datetime.now(timezone.utc).isoformat()
    count = 0
    for niche_id in niche_ids:
        m = compute_momentum(db, niche_id, window_days)
        db.execute(
            "UPDATE niche_candidates SET momentum_ratio=?, momentum_label=?, momentum_updated_at=? WHERE id=?",
            (m["ratio"], m["label"], updated_at, niche_id),
        )
        count += 1
    if count:
        db.commit()
    return count
