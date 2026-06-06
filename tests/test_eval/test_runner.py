"""Tests for the golden set evaluation runner."""
from __future__ import annotations

import io

from niche_radar.eval.golden_set import (
    EvalResult,
    EvalSummary,
    GoldenItem,
    evaluate_against_golden,
    print_summary,
)


def test_evaluate_against_golden_all_pass():
    """All checks pass for all items."""
    golden_items = [
        GoldenItem(
            item_id="item1",
            text="Some text about a tool for self-hosted analytics.",
            expected_a1_pass=True,
            expected_a6_verdict="GO",
            expected_tier="hot",
            expected_score_range=(40, 70),
        ),
        GoldenItem(
            item_id="item2",
            text="Just a casual observation.",
            expected_a1_pass=False,
            expected_a6_verdict="STOP",
            expected_tier="cold",
            expected_score_range=(0, 30),
        ),
    ]
    pipeline_results = {
        "item1": {"a1_pass": True, "verdict": "GO", "tier": "hot", "score": 55},
        "item2": {"a1_pass": False, "verdict": "STOP", "tier": "cold", "score": 10},
    }

    summary = evaluate_against_golden(golden_items, pipeline_results)

    assert summary.total == 2
    assert summary.passed == 2
    assert summary.failed == 0
    assert summary.accuracy == 1.0


def test_evaluate_against_golden_detects_failure():
    """A single mismatched check causes the item to fail."""
    golden_items = [GoldenItem(item_id="fail1", text="A product pain point.", expected_a1_pass=True)]
    pipeline_results = {"fail1": {"a1_pass": False}}

    summary = evaluate_against_golden(golden_items, pipeline_results)

    assert summary.total == 1
    assert summary.passed == 0
    assert summary.failed == 1
    assert not summary.results[0].checks["a1_pass"]
    assert summary.results[0].passed is False


def test_evaluate_against_golden_missing_result_counts_as_failure():
    """An item present in the golden set but absent from pipeline results is
    counted as a failure (missing data means checks can't pass)."""
    golden_items = [GoldenItem(item_id="missing1", text="I need a better way to manage my tasks.", expected_a1_pass=True)]
    pipeline_results: dict = {}

    summary = evaluate_against_golden(golden_items, pipeline_results)

    assert summary.total == 1
    assert summary.passed == 0
    assert summary.failed == 1
    assert not summary.results[0].checks["a1_pass"]


def test_evaluate_against_golden_skips_unspecified_checks():
    """When expected_a1_pass is None (unspecified), that check is skipped."""
    golden_items = [
        GoldenItem(
            item_id="no_a1",
            text="Some text for testing.",
            expected_a1_pass=None,
            expected_a6_verdict="GO",
        )
    ]
    pipeline_results = {"no_a1": {"verdict": "GO"}}

    summary = evaluate_against_golden(golden_items, pipeline_results)

    assert summary.total == 1
    assert summary.passed == 1
    assert summary.failed == 0
    assert "a1_pass" not in summary.results[0].checks
    assert summary.results[0].checks["verdict"] is True
    assert summary.by_check["a1_pass"]["total"] == 0
    assert summary.by_check["verdict"]["total"] == 1


def test_evaluate_against_golden_score_range():
    """Score within range passes; score outside range fails."""
    golden_items = [
        GoldenItem(item_id="in_range", text="A scoring item within range.", expected_score_range=(40, 70)),
        GoldenItem(item_id="out_of_range", text="A scoring item outside range.", expected_score_range=(40, 70)),
    ]
    pipeline_results = {
        "in_range": {"score": 55},
        "out_of_range": {"score": 20},
    }

    summary = evaluate_against_golden(golden_items, pipeline_results)

    assert summary.total == 2
    assert summary.passed == 1
    assert summary.failed == 1
    assert summary.results[0].checks["score_range"] is True
    assert summary.results[1].checks["score_range"] is False


def test_print_summary_empty():
    """Empty summary produces output with Total items: 0 and no failures."""
    summary = EvalSummary()
    buf = io.StringIO()
    print_summary(summary, file=buf)
    output = buf.getvalue()
    assert "Total items:  0" in output
    assert "Failures:" not in output


def test_print_summary_all_pass():
    """All-pass summary has no Failures: section."""
    summary = EvalSummary(total=2, passed=2, failed=0)
    summary.results = [
        EvalResult(item_id="a", checks={"a1_pass": True}),
        EvalResult(item_id="b", checks={"verdict": True}),
    ]
    summary.by_check = {"a1_pass": {"total": 1, "passed": 1}, "verdict": {"total": 1, "passed": 1}}
    buf = io.StringIO()
    print_summary(summary, file=buf)
    output = buf.getvalue()
    assert "Total items:  2" in output
    assert "Failures:" not in output


def test_print_summary_with_failures():
    """Summary with failures shows Failures: section and failed item_id."""
    summary = EvalSummary(total=2, passed=1, failed=1)
    summary.results = [
        EvalResult(item_id="ok", checks={"a1_pass": True}),
        EvalResult(item_id="bad", checks={"a1_pass": False}, details={"a1_pass": "expected=True, got=False"}),
    ]
    summary.by_check = {"a1_pass": {"total": 2, "passed": 1}}
    buf = io.StringIO()
    print_summary(summary, file=buf)
    output = buf.getvalue()
    assert "Total items:  2" in output
    assert "Failures:" in output
    assert "bad" in output
    assert "bad" in output.split("Failures:")[1]
