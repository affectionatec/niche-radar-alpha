"""Tests for FixtureLoader — loads mock A1 LLM response fixtures from JSON."""
from __future__ import annotations

import json

from niche_radar.eval.fixture_loader import A1Fixture, load_a1_fixtures


def test_load_a1_fixtures_parses_valid_file(tmp_path):
    data = {
        "golden_001": {
            "is_valid_signal": True,
            "confidence": 0.92,
            "signal_type": "pain_point",
            "reasoning": "Clear pain point.",
        },
        "golden_002": {
            "is_valid_signal": False,
            "confidence": 0.05,
            "signal_type": "noise",
            "reasoning": "Casual observation.",
        },
    }
    fixture_file = tmp_path / "a1_responses.json"
    fixture_file.write_text(json.dumps(data))

    fixtures = load_a1_fixtures(fixture_file)

    assert len(fixtures) == 2

    item = fixtures["golden_001"]
    assert isinstance(item, A1Fixture)
    assert item.is_valid_signal is True
    assert item.confidence == 0.92
    assert item.signal_type == "pain_point"
    assert item.reasoning == "Clear pain point."

    item = fixtures["golden_002"]
    assert item.is_valid_signal is False
    assert item.confidence == 0.05
    assert item.signal_type == "noise"
    assert item.reasoning == "Casual observation."


def test_load_a1_fixtures_returns_empty_for_missing_file(tmp_path):
    nonexistent = tmp_path / "does_not_exist.json"
    fixtures = load_a1_fixtures(nonexistent)
    assert fixtures == {}
