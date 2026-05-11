"""Market traction scoring."""

from __future__ import annotations

import math

from niche_radar.storage.repository import get_item_scores, get_niche_items


def score_market_traction(niche, db) -> float:
    """Blend YouTube view strength with GitHub star strength."""
    items = get_niche_items(db, niche["id"])
    youtube_scores = [float(item["score"]) for item in items if item.get("source") == "youtube" and item.get("score") is not None]
    github_scores = [float(item["score"]) for item in items if item.get("source") == "github" and item.get("score") is not None]

    parts: list[float] = []
    if youtube_scores:
        avg_views = sum(youtube_scores) / len(youtube_scores)
        parts.append(min(100.0, 15.0 * math.log10(avg_views + 1.0)))
    if github_scores:
        baseline = sorted(score for score in get_item_scores(db, source="github") if score is not None)
        if baseline:
            ranks = [sum(value <= score for value in baseline) / len(baseline) * 100 for score in github_scores]
            parts.append(sum(ranks) / len(ranks))
    return round(sum(parts) / len(parts), 2) if parts else 0.0
