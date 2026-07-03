"""Tests for the live-collector canary's verdict logic (no network involved)."""
from __future__ import annotations

from niche_radar.eval.canary import CanaryResult, evaluate_canary


def _r(source: str, items: int, status: str = "completed", error: str | None = None) -> CanaryResult:
    return CanaryResult(source=source, status=status, items=items, error=error)


def test_all_sources_yielding_is_healthy():
    healthy, lines = evaluate_canary([_r("hn", 12), _r("github", 25)])
    assert healthy is True
    assert any("HEALTHY" in line for line in lines)


def test_minority_zero_sources_is_healthy_by_default():
    results = [_r("hn", 12), _r("github", 25), _r("v2ex", 0, status="failed")]
    healthy, lines = evaluate_canary(results)
    assert healthy is True
    assert any("ROT?" in line and "v2ex" in line for line in lines)


def test_majority_zero_sources_detects_rot():
    results = [_r("hn", 0, "failed"), _r("github", 0, "failed"), _r("v2ex", 7)]
    healthy, lines = evaluate_canary(results)
    assert healthy is False
    assert any("ROT DETECTED" in line for line in lines)


def test_strict_mode_fails_on_any_zero_source():
    results = [_r("hn", 12), _r("github", 0, "failed")]
    healthy, _ = evaluate_canary(results, strict=True)
    assert healthy is False


def test_strict_mode_passes_when_all_yield():
    results = [_r("hn", 12), _r("github", 3)]
    healthy, _ = evaluate_canary(results, strict=True)
    assert healthy is True


def test_empty_results_is_unhealthy():
    healthy, lines = evaluate_canary([])
    assert healthy is False
    assert lines


def test_exception_result_reported_with_error():
    results = [_r("hn", 0, "exception", "RuntimeError: boom"), _r("github", 5)]
    healthy, lines = evaluate_canary(results)
    assert healthy is True  # 1 of 2 — at the half boundary, allowed
    assert any("RuntimeError: boom" in line for line in lines)


def test_main_sources_flag_and_strict_flag_parse(monkeypatch):
    """--sources limits the run; --strict tightens the verdict. Network is
    stubbed out by monkeypatching run_canary."""
    from niche_radar.eval import canary

    seen: dict = {}

    def fake_run(sources):
        seen["sources"] = sources
        return [_r(s, 0, "failed") for s in sources]

    monkeypatch.setattr(canary, "run_canary", fake_run)
    exit_code = canary.main(["--sources", "hn,github", "--strict"])
    assert seen["sources"] == ["hn", "github"]
    assert exit_code == 1
