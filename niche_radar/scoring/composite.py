"""Composite niche scoring."""

from __future__ import annotations


def compute_composite(
    engagement: float,
    search_trend: float,
    content_gap: float,
    market_traction: float,
) -> float:
    """Compute the weighted composite score."""
    score = (
        (engagement * 0.25)
        + (search_trend * 0.30)
        + (content_gap * 0.25)
        + (market_traction * 0.20)
    )
    return round(score, 2)
