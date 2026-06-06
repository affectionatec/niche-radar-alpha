"""Golden set evaluation framework for pipeline A/B testing.

Usage:
  python -m niche_radar.eval.golden_set [--golden-file path/to/golden.json]

The golden set is a list of manually annotated items with expected outcomes.
Running eval compares actual pipeline outputs against expected results and
produces accuracy metrics per agent.

Golden file format (JSON):
[
  {
    "item_id": "reddit_abc123",
    "text": "I wish there was a tool that...",
    "source": "reddit",
    "expected_a1_pass": true,
    "expected_a6_verdict": "GO",
    "expected_tier": "hot",
    "expected_score_range": [50, 70],
    "notes": "Clear pain point with monetization signal"
  }
]
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Any

DEFAULT_GOLDEN_PATH = Path("eval/golden_set.json")


@dataclass
class GoldenItem:
    item_id: str
    text: str
    source: str = "manual"
    expected_a1_pass: bool | None = None
    expected_a6_verdict: str | None = None
    expected_tier: str | None = None
    expected_score_range: tuple[int, int] | None = None
    notes: str = ""


@dataclass
class EvalResult:
    item_id: str
    checks: dict[str, bool] = field(default_factory=dict)
    details: dict[str, str] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return all(self.checks.values()) if self.checks else False


@dataclass
class EvalSummary:
    total: int = 0
    passed: int = 0
    failed: int = 0
    by_check: dict[str, dict[str, int]] = field(default_factory=dict)
    results: list[EvalResult] = field(default_factory=list)

    @property
    def accuracy(self) -> float:
        return self.passed / self.total if self.total else 0.0

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "accuracy": round(self.accuracy, 3),
            "by_check": self.by_check,
            "results": [
                {"item_id": r.item_id, "passed": r.passed, "checks": r.checks, "details": r.details}
                for r in self.results
            ],
        }


def load_golden_set(path: Path = DEFAULT_GOLDEN_PATH) -> list[GoldenItem]:
    """Load golden set from a JSON file."""
    if not path.exists():
        return []
    with open(path) as f:
        data = json.load(f)
    items = []
    for entry in data:
        score_range = entry.get("expected_score_range")
        items.append(GoldenItem(
            item_id=entry["item_id"],
            text=entry.get("text", ""),
            source=entry.get("source", "manual"),
            expected_a1_pass=entry.get("expected_a1_pass"),
            expected_a6_verdict=entry.get("expected_a6_verdict"),
            expected_tier=entry.get("expected_tier"),
            expected_score_range=tuple(score_range) if score_range else None,
            notes=entry.get("notes", ""),
        ))
    return items


def evaluate_against_golden(
    golden_items: list[GoldenItem],
    pipeline_results: dict[str, dict[str, Any]],
) -> EvalSummary:
    """Compare pipeline outputs against golden set expectations.

    pipeline_results: {item_id: {"a1_pass": bool, "verdict": str, "tier": str, "score": int}}
    """
    summary = EvalSummary()
    check_names = ["a1_pass", "verdict", "tier", "score_range"]

    for name in check_names:
        summary.by_check[name] = {"total": 0, "passed": 0}

    for golden in golden_items:
        result = EvalResult(item_id=golden.item_id)
        actual = pipeline_results.get(golden.item_id, {})

        if golden.expected_a1_pass is not None:
            actual_pass = actual.get("a1_pass")
            ok = actual_pass == golden.expected_a1_pass
            result.checks["a1_pass"] = ok
            result.details["a1_pass"] = f"expected={golden.expected_a1_pass}, got={actual_pass}"
            summary.by_check["a1_pass"]["total"] += 1
            if ok:
                summary.by_check["a1_pass"]["passed"] += 1

        if golden.expected_a6_verdict is not None:
            actual_verdict = actual.get("verdict")
            ok = actual_verdict == golden.expected_a6_verdict
            result.checks["verdict"] = ok
            result.details["verdict"] = f"expected={golden.expected_a6_verdict}, got={actual_verdict}"
            summary.by_check["verdict"]["total"] += 1
            if ok:
                summary.by_check["verdict"]["passed"] += 1

        if golden.expected_tier is not None:
            actual_tier = actual.get("tier")
            ok = actual_tier == golden.expected_tier
            result.checks["tier"] = ok
            result.details["tier"] = f"expected={golden.expected_tier}, got={actual_tier}"
            summary.by_check["tier"]["total"] += 1
            if ok:
                summary.by_check["tier"]["passed"] += 1

        if golden.expected_score_range is not None:
            actual_score = actual.get("score")
            lo, hi = golden.expected_score_range
            ok = actual_score is not None and lo <= actual_score <= hi
            result.checks["score_range"] = ok
            result.details["score_range"] = f"expected=[{lo},{hi}], got={actual_score}"
            summary.by_check["score_range"]["total"] += 1
            if ok:
                summary.by_check["score_range"]["passed"] += 1

        summary.results.append(result)
        summary.total += 1
        if result.passed:
            summary.passed += 1
        else:
            summary.failed += 1

    return summary


def print_summary(summary: EvalSummary, file: IO | None = None) -> None:
    """Print a human-readable evaluation summary."""
    out = file or sys.stdout
    print(f"\n{'='*60}", file=out)
    print(f"Golden Set Evaluation Results", file=out)
    print(f"{'='*60}", file=out)
    print(f"Total items:  {summary.total}", file=out)
    print(f"Passed:       {summary.passed}", file=out)
    print(f"Failed:       {summary.failed}", file=out)
    print(f"Accuracy:     {summary.accuracy:.1%}", file=out)
    print(file=out)

    for check_name, counts in summary.by_check.items():
        if counts["total"] == 0:
            continue
        rate = counts["passed"] / counts["total"]
        print(f"  {check_name}: {counts['passed']}/{counts['total']} ({rate:.1%})", file=out)

    if summary.failed > 0:
        print(f"\nFailures:", file=out)
        for r in summary.results:
            if not r.passed:
                for check, ok in r.checks.items():
                    if not ok:
                        print(f"  [{r.item_id}] {check}: {r.details[check]}", file=out)
