#!/usr/bin/env python3
"""Golden-set evaluation runner -- CLI entry point for CI.

Usage:
  python -m niche_radar.eval.runner [--golden-file eval/golden_set.json]
                                    [--fixtures-dir eval/fixtures]

For each golden item, runs the REAL A1 → A2 agent chain
(``orchestrator.run_single``) with a MockLLMClient that replays the item's
canned A1 response as the raw LLM output. This exercises prompt construction,
Pydantic output validation, and the A1 short-circuit decision — everything
except the network call. Compares actual outcomes to expected values.
Exits 0 if all enforced checks pass, 1 if any fail.

Enforced checks: a1_pass.
Informational (not yet wired to the cluster phase A3–A8): verdict, tier,
score_range — reported separately, never counted as failures.
"""
from __future__ import annotations

import sys
from pathlib import Path

from niche_radar.agents.orchestrator import run_single
from niche_radar.eval.fixture_loader import A1Fixture, load_a1_fixtures
from niche_radar.eval.golden_set import (
    GoldenItem,
    evaluate_against_golden,
    load_golden_set,
    print_summary,
)
from niche_radar.eval.mock_client import MockLLMClient

DEFAULT_GOLDEN_FILE = Path("eval/golden_set.json")
DEFAULT_FIXTURES_DIR = Path("eval/fixtures")

# Checks the gate enforces today. verdict/tier/score_range require replaying
# the cluster phase (A3–A8) with per-agent fixtures — not wired yet.
ENFORCED_CHECKS = ("a1_pass",)

# Minimal-but-valid canned A2 response so an A1-accepted item completes the
# run_single chain instead of polluting failed_agents.
_A2_STUB = {
    "who": "eval stub persona",
    "what": "eval stub pain",
    "keywords": ["eval"],
}


def _a1_response_from_fixture(fixture: A1Fixture) -> dict:
    """Shape a fixture as the raw structured-JSON dict A1's LLM call would return."""
    response: dict = {
        "is_valid_signal": fixture.is_valid_signal,
        "confidence": fixture.confidence,
    }
    if fixture.signal_type:
        response["signal_type"] = fixture.signal_type
    if fixture.reasoning:
        key = "pain_summary" if fixture.is_valid_signal else "rejection_reason"
        response[key] = fixture.reasoning
    return response


def build_a1_results(
    items: list[GoldenItem], a1_fixtures: dict[str, A1Fixture]
) -> dict[str, dict]:
    """Run each golden item through the real A1 → A2 chain using mock LLM responses.

    Returns {item_id: {"a1_pass": bool, ...}} suitable for evaluate_against_golden.
    """
    results: dict[str, dict] = {}
    for item in items:
        fixture = a1_fixtures.get(item.item_id)
        if fixture is None:
            results[item.item_id] = {}
            continue

        client = MockLLMClient(
            responses={
                "a1": _a1_response_from_fixture(fixture),
                "a2": dict(_A2_STUB),
            }
        )
        raw_signal = {
            "text": item.text,
            "source": item.source,
            "url": "",
            "scraped_at": "",
        }
        pipeline_result = run_single(raw_signal, clients=lambda _aid: (client, 0.0))

        a1 = pipeline_result.a1
        a1_failed = "a1" in pipeline_result.failed_agents
        results[item.item_id] = {
            # A terminal A1 failure (malformed response, validation error) is
            # None — distinct from a rejection — so it mismatches both True
            # and False expectations and surfaces in the gate.
            "a1_pass": None if a1_failed else bool(a1 is not None and a1.is_valid_signal),
            "a1_failed": a1_failed,
            "short_circuited_at": pipeline_result.short_circuited_at,
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
    summary = evaluate_against_golden(items, pipeline_results, checks=ENFORCED_CHECKS)
    print_summary(summary)

    deferred = sorted(
        {
            name
            for item in items
            for name, expected in (
                ("verdict", item.expected_a6_verdict),
                ("tier", item.expected_tier),
                ("score_range", item.expected_score_range),
            )
            if expected is not None
        }
    )
    if deferred:
        print(
            f"\nNot evaluated (cluster phase A3-A8 not wired into the eval yet): "
            f"{', '.join(deferred)}"
        )

    return 0 if summary.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
