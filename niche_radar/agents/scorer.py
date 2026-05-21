"""Composite scoring + tier classification for opportunities.

Two related but distinct quantities:
- weighted_score: the A4 dimension scores combined with the willingness-to-pay-weighted
  formula from refactor_prompt.md §SCORING WEIGHTS, normalized to 0-100. This is what
  populates niche_candidates.llm_score (existing UI shows 0-100).
- tier: "hot" (>50/70) | "warm" (35-50/70) | "cold" (<35/70) — thresholds defined on the
  RAW A4 total_score (0-70) per refactor_prompt.md.
"""

from __future__ import annotations

from typing import Literal

# Weights from refactor_prompt.md §SCORING WEIGHTS
WEIGHTS: dict[str, float] = {
    "problem_clarity": 1.0,
    "market_size": 1.5,
    "willingness_to_pay": 2.0,   # highest weight
    "competition_gap": 1.5,
    "technical_feasibility": 1.0,
    "distribution_clarity": 1.5,
    "trend_momentum": 1.0,
}
_TOTAL_WEIGHT = sum(WEIGHTS.values())  # 9.5
_MAX_DIMENSION = 10.0

# Tier thresholds on A4 raw total_score (0-70)
TIER_HOT_THRESHOLD = 50
TIER_WARM_THRESHOLD = 35


def weighted_score(a4_scores) -> float:
    """Weighted average of dimension scores, normalized to 0-100.

    Accepts either an A4Scores pydantic model or a plain dict shaped like
    {"problem_clarity": {"score": 7, ...}, ...}.

    Missing dimensions count as 0 — partial scoring still produces a number rather than
    raising. If ALL dimensions are missing, returns 0.0.
    """
    if a4_scores is None:
        return 0.0

    if hasattr(a4_scores, "model_dump"):
        scores_dict = a4_scores.model_dump()
    else:
        scores_dict = a4_scores

    total = 0.0
    for dim, weight in WEIGHTS.items():
        node = scores_dict.get(dim) or {}
        raw = node.get("score") if isinstance(node, dict) else None
        if raw is None:
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        value = max(0.0, min(_MAX_DIMENSION, value))
        total += value * weight

    # Weighted average across 1-10 dimensions, then ×10 for 0-100.
    return round((total / _TOTAL_WEIGHT) * (100.0 / _MAX_DIMENSION), 2)


def tier(total_score: int | float | None) -> Literal["hot", "warm", "cold"]:
    """Classify the A4 raw total_score (0-70) into a coarse priority bucket."""
    if total_score is None:
        return "cold"
    if total_score > TIER_HOT_THRESHOLD:
        return "hot"
    if total_score >= TIER_WARM_THRESHOLD:
        return "warm"
    return "cold"


def build_complexity_from_feasibility(feasibility_score: int | None) -> int:
    """Map A5 feasibility_score (1-10, higher=easier to build) to existing
    niche_candidates.build_complexity (1-5, higher=harder).

    A solo-buildable feasibility 9-10 → complexity 1.
    Brutal-to-build feasibility 1-2  → complexity 5.
    """
    if feasibility_score is None:
        return 3
    try:
        v = int(feasibility_score)
    except (TypeError, ValueError):
        return 3
    v = max(1, min(10, v))
    complexity = 5 - round(v / 2.5)
    return max(1, min(5, complexity))
