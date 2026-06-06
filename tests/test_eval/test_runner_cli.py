"""Tests for the golden-set eval CLI runner."""
from __future__ import annotations

import json
from pathlib import Path

from niche_radar.eval.golden_set import EvalSummary, evaluate_against_golden, load_golden_set
from niche_radar.eval.fixture_loader import load_a1_fixtures


def test_runner_integration_with_mock_client(tmp_path: Path):
    """End-to-end: golden items + mock fixtures -> eval summary with 100% accuracy."""
    golden_data = [
        {"item_id": "test_001", "text": "I need a tool for X", "source": "reddit",
         "expected_a1_pass": True},
        {"item_id": "test_002", "text": "Nice weather today", "source": "hn",
         "expected_a1_pass": False},
    ]
    golden_path = tmp_path / "golden.json"
    golden_path.write_text(json.dumps(golden_data))

    fixture_data = {
        "test_001": {"is_valid_signal": True, "confidence": 0.9, "signal_type": "pain_point"},
        "test_002": {"is_valid_signal": False, "confidence": 0.05, "signal_type": "noise"},
    }
    fixture_path = tmp_path / "a1_fixtures.json"
    fixture_path.write_text(json.dumps(fixture_data))

    items = load_golden_set(golden_path)
    assert len(items) == 2

    fixtures = load_a1_fixtures(fixture_path)
    assert len(fixtures) == 2

    from niche_radar.eval.runner import build_a1_results

    pipeline_results = build_a1_results(items, fixtures)

    summary = evaluate_against_golden(items, pipeline_results)
    assert summary.total == 2
    assert summary.passed == 2
    assert summary.failed == 0


def test_runner_cli_exit_code_zero_on_all_pass(tmp_path: Path):
    """Runner main() returns 0 when all golden items pass."""
    from niche_radar.eval.runner import main

    golden_data = [
        {"item_id": "a", "text": "I need X", "source": "reddit", "expected_a1_pass": True},
        {"item_id": "b", "text": "I want Y", "source": "hn", "expected_a1_pass": False},
    ]
    golden_path = tmp_path / "golden.json"
    golden_path.write_text(json.dumps(golden_data))

    fixture_data = {
        "a": {"is_valid_signal": True, "confidence": 0.9, "signal_type": "pain_point"},
        "b": {"is_valid_signal": False, "confidence": 0.05, "signal_type": "noise"},
    }
    fixtures_dir = tmp_path / "fixtures"
    fixtures_dir.mkdir()
    fixture_path = fixtures_dir / "a1_responses.json"
    fixture_path.write_text(json.dumps(fixture_data))

    exit_code = main(["--golden-file", str(golden_path), "--fixtures-dir", str(fixtures_dir)])
    assert exit_code == 0


def test_runner_cli_exit_code_nonzero_on_failure(tmp_path: Path):
    """Runner main() returns 1 when any golden item fails."""
    from niche_radar.eval.runner import main

    golden_data = [
        {"item_id": "a", "text": "I need X", "source": "reddit", "expected_a1_pass": True},
    ]
    golden_path = tmp_path / "golden.json"
    golden_path.write_text(json.dumps(golden_data))

    # Fixture says False, golden expects True -> mismatch -> failure
    fixture_data = {
        "a": {"is_valid_signal": False, "confidence": 0.05, "signal_type": "noise"},
    }
    fixtures_dir = tmp_path / "fixtures"
    fixtures_dir.mkdir()
    fixture_path = fixtures_dir / "a1_responses.json"
    fixture_path.write_text(json.dumps(fixture_data))

    exit_code = main(["--golden-file", str(golden_path), "--fixtures-dir", str(fixtures_dir)])
    assert exit_code == 1
