"""Unit tests for agents/pain_score.py."""

from __future__ import annotations

import pytest

from niche_radar.agents.models import A2Output
from niche_radar.agents.pain_score import compute_pain_score


def _a2(emotional_intensity=5, willingness_to_pay=False, keywords=None):
    return A2Output(
        who="user", what="problem",
        emotional_intensity=emotional_intensity,
        willingness_to_pay_signal=willingness_to_pay,
        keywords=keywords or ["aws", "cost"],
    )


def test_urgency_maps_directly_from_emotional_intensity():
    scores = compute_pain_score(None, "item-1", _a2(emotional_intensity=8))
    assert scores["urgency"] == 8.0


def test_monetization_is_3_when_willing_to_pay():
    scores = compute_pain_score(None, "item-1", _a2(willingness_to_pay=True))
    assert scores["monetization_score"] == 3


def test_monetization_is_0_when_not_willing():
    scores = compute_pain_score(None, "item-1", _a2(willingness_to_pay=False))
    assert scores["monetization_score"] == 0


def test_pain_score_total_within_range():
    scores = compute_pain_score(None, "item-1", _a2(emotional_intensity=10, willingness_to_pay=True))
    assert 0.0 <= scores["pain_score_total"] <= 10.0


def test_higher_intensity_yields_higher_score():
    low = compute_pain_score(None, "item-1", _a2(emotional_intensity=2))
    high = compute_pain_score(None, "item-2", _a2(emotional_intensity=9))
    assert high["pain_score_total"] > low["pain_score_total"]


def test_none_a2_returns_zeros():
    scores = compute_pain_score(None, "item-1", None)
    assert scores["pain_score_total"] == 0.0
    assert scores["urgency"] == 0.0


def test_competition_gap_contributes():
    with_gap = compute_pain_score(None, "item-1", _a2(emotional_intensity=5), competition_gap_score=9)
    without_gap = compute_pain_score(None, "item-1", _a2(emotional_intensity=5), competition_gap_score=0)
    assert with_gap["pain_score_total"] > without_gap["pain_score_total"]
