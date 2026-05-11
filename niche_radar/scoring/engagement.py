"""Engagement scoring."""

from __future__ import annotations

from niche_radar.storage.repository import get_item_scores, get_niche_items


def score_engagement(niche, db) -> float:
    """Use percentile rank of linked item scores."""
    baseline = sorted(score for score in get_item_scores(db) if score is not None)
    linked_scores = [float(item["score"]) for item in get_niche_items(db, niche["id"]) if item.get("score") is not None]
    if not baseline or not linked_scores:
        return 0.0

    percentiles = []
    for score in linked_scores:
        rank = sum(value <= score for value in baseline) / len(baseline)
        percentiles.append(rank * 100)
    return round(sum(percentiles) / len(percentiles), 2)
