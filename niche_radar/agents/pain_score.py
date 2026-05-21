"""Per-item pain score (0-10 composite) stored on item_pain_extractions.

Components — all derived from what A2 already extracted; NO new LLM calls:

  urgency         A2.emotional_intensity (0-10)         weight 0.4
  monetization    A2.willingness_to_pay_signal (0 or 3) weight 0.2
  frequency       cross-item keyword overlap (0-3)       weight 0.2
  competition_gap cluster A4.competition_gap (0-10)     weight 0.2

VADER/TextBlob are explicitly skipped — A2.emotional_intensity is the LLM-extracted
urgency and disagrees noisily with classical sentiment on technical complaint text.
"""

from __future__ import annotations

import sqlite3

from niche_radar.agents.models import A2Output


def compute_frequency_score(
    db: sqlite3.Connection,
    item_id: str,
    a2: A2Output,
    window_days: int = 14,
) -> int:
    """Count other A1-passed items in the last `window_days` days whose A2.keywords
    overlap by at least one token with this item's keywords. Capped at 3.

    This is a cheap SQL query — no LLM needed.
    """
    if not a2 or not a2.keywords:
        return 0
    # Build a LIKE condition for each keyword against the stored a2_result JSON
    conditions = " OR ".join(["a2_result LIKE ?"] * len(a2.keywords))
    params = [f'%"{kw}"%' for kw in a2.keywords]
    params += [item_id, window_days]
    try:
        count = db.execute(
            f"""
            SELECT COUNT(*) FROM item_pain_extractions
            WHERE a1_is_valid = 1
              AND raw_item_id != ?
              AND ({conditions})
              AND processed_at >= datetime('now', ? || ' days')
            """.replace("? || ' days'", f"'-{window_days} days'"),
            [item_id] + [f'%"{kw}"%' for kw in a2.keywords],
        ).fetchone()[0]
    except Exception:
        return 0
    return min(3, count)


def compute_pain_score(
    db: sqlite3.Connection,
    item_id: str,
    a2: A2Output | None,
    competition_gap_score: int | None = None,
    window_days: int = 14,
) -> dict:
    """Compute a 0-10 composite pain score for one raw_item after A2 ran.

    Returns a dict with component scores + total, suitable for DB storage.
    """
    if a2 is None:
        return {
            "urgency": 0.0,
            "monetization_score": 0,
            "frequency_score": 0,
            "pain_score_total": 0.0,
        }

    # Urgency: direct from A2
    urgency = float(a2.emotional_intensity or 0)
    urgency = max(0.0, min(10.0, urgency))

    # Monetization binary signal: 0 or 3
    monetization = 3 if a2.willingness_to_pay_signal else 0

    # Frequency: cross-item overlap
    frequency = compute_frequency_score(db, item_id, a2, window_days)

    # Competition gap: from cluster's A4 (may be None if A4 hasn't run yet)
    comp_gap = float(competition_gap_score or 0)
    comp_gap = max(0.0, min(10.0, comp_gap))

    # Weighted composite, normalized to 0-10
    total = (
        urgency * 0.4
        + monetization * 0.2   # monetization is already 0 or 3 → 0.0 or 0.6
        + frequency * 0.2      # frequency max 3 → 0.6
        + comp_gap * 0.2
    )
    # Re-scale so max is 10: weights sum to 1.0 and max contributions are
    # 4.0 + 0.6 + 0.6 + 2.0 = 7.2 → scale up to 10 proportionally
    total = min(10.0, round(total * (10.0 / 7.2), 2))

    return {
        "urgency": urgency,
        "monetization_score": monetization,
        "frequency_score": frequency,
        "pain_score_total": total,
    }


def persist_pain_score(db: sqlite3.Connection, item_id: str, scores: dict) -> None:
    """Write computed pain score components back to item_pain_extractions."""
    db.execute(
        "UPDATE item_pain_extractions SET urgency=?, monetization_score=?, frequency_score=?, pain_score_total=? WHERE raw_item_id=?",
        (
            scores["urgency"],
            scores["monetization_score"],
            scores["frequency_score"],
            scores["pain_score_total"],
            item_id,
        ),
    )
    db.commit()
