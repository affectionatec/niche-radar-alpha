"""Tests for the golden-set eval CLI runner.

The runner routes each golden item through the REAL orchestrator.run_single
(A1 → A2) with a MockLLMClient replaying canned responses — these tests pin
that the gate exercises actual agent code, not fixture-vs-fixture comparison.
"""
from __future__ import annotations

import json
from pathlib import Path

from niche_radar.eval.fixture_loader import load_a1_fixtures
from niche_radar.eval.golden_set import evaluate_against_golden, load_golden_set
from niche_radar.eval.mock_client import MockLLMClient
from niche_radar.eval.runner import build_a1_results, main


def _write_golden(tmp_path: Path, golden_data: list[dict]) -> Path:
    golden_path = tmp_path / "golden.json"
    golden_path.write_text(json.dumps(golden_data))
    return golden_path


def _write_fixtures(tmp_path: Path, fixture_data: dict) -> Path:
    fixtures_dir = tmp_path / "fixtures"
    fixtures_dir.mkdir()
    (fixtures_dir / "a1_responses.json").write_text(json.dumps(fixture_data))
    return fixtures_dir


def test_runner_integration_with_mock_client(tmp_path: Path):
    """End-to-end: golden items + mock fixtures -> eval summary with 100% accuracy."""
    golden_path = _write_golden(tmp_path, [
        {"item_id": "test_001", "text": "I need a tool for X", "source": "reddit",
         "expected_a1_pass": True},
        {"item_id": "test_002", "text": "Nice weather today", "source": "hn",
         "expected_a1_pass": False},
    ])
    fixture_path = _write_fixtures(tmp_path, {
        "test_001": {"is_valid_signal": True, "confidence": 0.9, "signal_type": "pain_point"},
        "test_002": {"is_valid_signal": False, "confidence": 0.05, "signal_type": "noise"},
    })

    items = load_golden_set(golden_path)
    assert len(items) == 2

    fixtures = load_a1_fixtures(fixture_path / "a1_responses.json")
    assert len(fixtures) == 2

    pipeline_results = build_a1_results(items, fixtures)

    summary = evaluate_against_golden(items, pipeline_results)
    assert summary.total == 2
    assert summary.passed == 2
    assert summary.failed == 0


def test_build_a1_results_executes_real_a1_chain(tmp_path: Path):
    """An accepted item runs A1 then A2; a rejected item short-circuits at A1."""
    golden_path = _write_golden(tmp_path, [
        {"item_id": "accept", "text": "I waste hours on X", "source": "reddit",
         "expected_a1_pass": True},
        {"item_id": "reject", "text": "Nice weather", "source": "hn",
         "expected_a1_pass": False},
    ])
    fixture_path = _write_fixtures(tmp_path, {
        "accept": {"is_valid_signal": True, "confidence": 0.9, "signal_type": "pain_point",
                   "reasoning": "clear pain"},
        "reject": {"is_valid_signal": False, "confidence": 0.1, "signal_type": "noise",
                   "reasoning": "no signal"},
    })

    items = load_golden_set(golden_path)
    fixtures = load_a1_fixtures(fixture_path / "a1_responses.json")
    results = build_a1_results(items, fixtures)

    assert results["accept"]["a1_pass"] is True
    assert results["accept"]["short_circuited_at"] is None
    assert results["accept"]["a1_failed"] is False

    assert results["reject"]["a1_pass"] is False
    assert results["reject"]["short_circuited_at"] == "a1"


def test_build_a1_results_missing_fixture_yields_empty_result(tmp_path: Path):
    golden_path = _write_golden(tmp_path, [
        {"item_id": "no_fixture", "text": "text", "source": "reddit",
         "expected_a1_pass": True},
    ])
    items = load_golden_set(golden_path)
    results = build_a1_results(items, {})
    assert results["no_fixture"] == {}


def test_run_single_with_garbage_llm_response_takes_failure_path():
    """A response that fails A1Output validation exercises the orchestrator's
    retry/failure path — the eval must report a1_pass=False, not crash."""
    from niche_radar.agents.orchestrator import run_single

    client = MockLLMClient(default={})  # empty dict fails "no recognizable fields"
    result = run_single(
        {"text": "anything", "source": "reddit", "url": "", "scraped_at": ""},
        clients=lambda _aid: (client, 0.0),
    )
    assert result.a1 is None
    assert "a1" in result.failed_agents
    assert result.short_circuited_at == "a1"


def test_runner_cli_terminal_a1_failure_fails_gate_even_when_rejection_expected(tmp_path: Path):
    """A fixture that fails A1Output validation (invalid signal_type literal)
    is an agent-machinery failure, not a rejection — it must fail the gate
    even when the golden item expects a1_pass=False."""
    golden_path = _write_golden(tmp_path, [
        {"item_id": "a", "text": "I hate X", "source": "hn", "expected_a1_pass": False},
    ])
    fixtures_dir = _write_fixtures(tmp_path, {
        "a": {"is_valid_signal": False, "confidence": 0.1, "signal_type": "not_a_valid_literal"},
    })

    exit_code = main(["--golden-file", str(golden_path), "--fixtures-dir", str(fixtures_dir)])
    assert exit_code == 1


def test_runner_cli_exit_code_zero_on_all_pass(tmp_path: Path):
    """Runner main() returns 0 when all golden items pass."""
    golden_path = _write_golden(tmp_path, [
        {"item_id": "a", "text": "I need X", "source": "reddit", "expected_a1_pass": True},
        {"item_id": "b", "text": "I want Y", "source": "hn", "expected_a1_pass": False},
    ])
    fixtures_dir = _write_fixtures(tmp_path, {
        "a": {"is_valid_signal": True, "confidence": 0.9, "signal_type": "pain_point"},
        "b": {"is_valid_signal": False, "confidence": 0.05, "signal_type": "noise"},
    })

    exit_code = main(["--golden-file", str(golden_path), "--fixtures-dir", str(fixtures_dir)])
    assert exit_code == 0


def test_runner_cli_exit_code_nonzero_on_failure(tmp_path: Path):
    """Runner main() returns 1 when any golden item fails."""
    golden_path = _write_golden(tmp_path, [
        {"item_id": "a", "text": "I need X", "source": "reddit", "expected_a1_pass": True},
    ])
    # Fixture says False, golden expects True -> mismatch -> failure
    fixtures_dir = _write_fixtures(tmp_path, {
        "a": {"is_valid_signal": False, "confidence": 0.05, "signal_type": "noise"},
    })

    exit_code = main(["--golden-file", str(golden_path), "--fixtures-dir", str(fixtures_dir)])
    assert exit_code == 1


def test_runner_cli_deferred_checks_are_informational_not_failures(tmp_path: Path, capsys):
    """verdict/tier/score_range expectations aren't exercised by the A1-only
    replay; they must be reported as deferred, not silently counted or ignored."""
    golden_path = _write_golden(tmp_path, [
        {"item_id": "a", "text": "I need X", "source": "reddit",
         "expected_a1_pass": True, "expected_a6_verdict": "GO",
         "expected_tier": "hot", "expected_score_range": [40, 70]},
    ])
    fixtures_dir = _write_fixtures(tmp_path, {
        "a": {"is_valid_signal": True, "confidence": 0.9, "signal_type": "pain_point"},
    })

    exit_code = main(["--golden-file", str(golden_path), "--fixtures-dir", str(fixtures_dir)])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Not evaluated" in output
    assert "verdict" in output
    assert "tier" in output
    assert "score_range" in output
