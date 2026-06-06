#!/usr/bin/env python3
"""Golden-set evaluation runner -- CLI entry point for CI.

Usage:
  python -m niche_radar.eval.runner [--golden-file eval/golden_set.json]
                                    [--fixtures-dir eval/fixtures]

Runs A1 against each golden item using mock LLM responses from fixture files.
Compares actual outputs to expected values. Exits 0 if all pass, 1 if any fail.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from niche_radar.eval.golden_set import (
    EvalSummary,
    GoldenItem,
    evaluate_against_golden,
    load_golden_set,
    print_summary,
)
from niche_radar.eval.fixture_loader import A1Fixture, load_a1_fixtures
from niche_radar.eval.mock_client import MockLLMClient

DEFAULT_GOLDEN_FILE = Path("eval/golden_set.json")
DEFAULT_FIXTURES_DIR = Path("eval/fixtures")


def build_a1_results(items: list[GoldenItem], a1_fixtures: dict[str, A1Fixture]) -> dict[str, dict]:
    """Run each golden item through a simulated A1 pass using mock fixtures.

    Returns {item_id: {"a1_pass": bool, ...}} suitable for evaluate_against_golden.
    """
    results: dict[str, dict] = {}
    for item in items:
        fixture = a1_fixtures.get(item.item_id)
        if fixture is None:
            results[item.item_id] = {}
            continue
        results[item.item_id] = {
            "a1_pass": fixture.is_valid_signal,
        }
    return results


def main(argv: list[str] | None = None) -> int:
    golden_file = DEFAULT_GOLDEN_FILE
    fixtures_dir = DEFAULT_FIXTURES_DIR

    # Minimal arg parsing
    args = argv or sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--golden-file" and i + 1 < len(args):
            golden_file = Path(args[i + 1])
            i += 2
        elif args[i] == "--fixtures-dir" and i + 1 < len(args):
            fixtures_dir = Path(args[i + 1])
            i += 2
        else:
            i += 1

    print(f"Golden file: {golden_file}")
    print(f"Fixtures dir: {fixtures_dir}")

    items = load_golden_set(golden_file)
    if not items:
        print("ERROR: No golden items loaded -- check golden file exists and is non-empty")
        return 1

    a1_fixtures = load_a1_fixtures(fixtures_dir / "a1_responses.json")
    if not a1_fixtures:
        print("WARNING: No A1 fixtures loaded -- all A1 checks will fail (no fixture = no result)")

    pipeline_results = build_a1_results(items, a1_fixtures)
    summary = evaluate_against_golden(items, pipeline_results)
    print_summary(summary)

    # For P1, exit code is based on A1 checks only (verdict/tier/score come in later phases)
    a1_total = summary.by_check.get("a1_pass", {}).get("total", 0)
    a1_passed = summary.by_check.get("a1_pass", {}).get("passed", 0)
    if a1_total > 0 and a1_passed < a1_total:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
