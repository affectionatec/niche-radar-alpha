"""Unit tests for niche_radar.agents.scorer — weighted scoring and tier classification."""

from niche_radar.agents.scorer import (
    WEIGHTS,
    build_complexity_from_feasibility,
    tier,
    weighted_score,
)


def _scores(**overrides):
    """Build a scores dict with all 7 dimensions defaulting to 5."""
    base = {
        "problem_clarity":       {"score": 5, "rationale": ""},
        "market_size":           {"score": 5, "rationale": ""},
        "willingness_to_pay":    {"score": 5, "rationale": ""},
        "competition_gap":       {"score": 5, "rationale": ""},
        "technical_feasibility": {"score": 5, "rationale": ""},
        "distribution_clarity":  {"score": 5, "rationale": ""},
        "trend_momentum":        {"score": 5, "rationale": ""},
    }
    for k, v in overrides.items():
        base[k] = {"score": v, "rationale": ""}
    return base


def test_weighted_score_all_fives_is_50():
    # Each dim 5/10 → weighted average 5 → ×10 = 50.
    assert weighted_score(_scores()) == 50.0


def test_weighted_score_all_tens_is_100():
    s = {k: {"score": 10, "rationale": ""} for k in WEIGHTS}
    assert weighted_score(s) == 100.0


def test_weighted_score_all_zeros_is_0():
    s = {k: {"score": 0, "rationale": ""} for k in WEIGHTS}
    assert weighted_score(s) == 0.0


def test_weighted_score_willingness_to_pay_weighted_highest():
    # WTP=10, everything else=5 → must score higher than market_size=10, rest=5
    wtp_high = weighted_score(_scores(willingness_to_pay=10))
    market_high = weighted_score(_scores(market_size=10))
    assert wtp_high > market_high


def test_weighted_score_handles_missing_dimensions():
    s = {"problem_clarity": {"score": 10, "rationale": ""}}  # others absent
    score = weighted_score(s)
    # Only 1.0 weight contributes 10 out of total weight 9.5 → 10*1.0/9.5*10 ≈ 10.53
    assert 10.0 < score < 11.0


def test_weighted_score_none_returns_zero():
    assert weighted_score(None) == 0.0


def test_weighted_score_handles_pydantic_model():
    from niche_radar.agents.models import A4Score, A4Scores
    pm = A4Scores(
        problem_clarity=A4Score(score=8, rationale="x"),
        market_size=A4Score(score=8, rationale="x"),
        willingness_to_pay=A4Score(score=8, rationale="x"),
        competition_gap=A4Score(score=8, rationale="x"),
        technical_feasibility=A4Score(score=8, rationale="x"),
        distribution_clarity=A4Score(score=8, rationale="x"),
        trend_momentum=A4Score(score=8, rationale="x"),
    )
    assert weighted_score(pm) == 80.0


def test_weighted_score_clamps_out_of_range():
    # Score 15 → clamped to 10
    s = _scores(problem_clarity=15)
    s2 = _scores(problem_clarity=10)
    assert weighted_score(s) == weighted_score(s2)


def test_tier_hot_above_50():
    assert tier(60) == "hot"
    assert tier(51) == "hot"


def test_tier_warm_35_to_50():
    assert tier(50) == "warm"
    assert tier(35) == "warm"
    assert tier(42) == "warm"


def test_tier_cold_under_35():
    assert tier(34) == "cold"
    assert tier(0) == "cold"


def test_tier_none_is_cold():
    assert tier(None) == "cold"


def test_build_complexity_from_feasibility_inverts():
    # feasibility 10 (easy) → complexity 1; feasibility 1 (hard) → complexity ≥4
    assert build_complexity_from_feasibility(10) == 1
    assert build_complexity_from_feasibility(1) >= 4
    assert build_complexity_from_feasibility(5) == 3


def test_build_complexity_handles_missing_or_bad_input():
    assert build_complexity_from_feasibility(None) == 3
    assert build_complexity_from_feasibility("bogus") == 3  # type: ignore[arg-type]
    # Clamp out-of-range
    assert 1 <= build_complexity_from_feasibility(15) <= 5
