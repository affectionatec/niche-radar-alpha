"""Scoring utilities for the 8-agent pipeline."""

from __future__ import annotations

WEIGHTS: dict[str, float] = {
    "problem_clarity": 1.0,
    "market_size": 1.5,
    "willingness_to_pay": 2.0,
    "competition_gap": 1.5,
    "technical_feasibility": 1.0,
    "distribution_clarity": 1.5,
    "trend_momentum": 1.0,
}

_TOTAL_WEIGHT = sum(WEIGHTS.values())   # 10.0
_MAX_RAW = 10 * _TOTAL_WEIGHT           # 100.0


def opportunity_score(scores: dict) -> float:
    """Weighted average of 7 dimension scores, normalized to 0-100.

    `scores` is the dict from A4Output.scores where each value has a "score" key (1-10).
    """
    total = sum(
        scores[dim]["score"] * weight
        for dim, weight in WEIGHTS.items()
        if dim in scores and isinstance(scores[dim], dict)
    )
    return round((total / _MAX_RAW) * 100, 1)


def tier(total_score: int | float) -> str:
    """Map A4 total_score (0-70 scale) to a tier label."""
    if total_score > 50:
        return "hot"
    if total_score >= 35:
        return "warm"
    return "cold"
