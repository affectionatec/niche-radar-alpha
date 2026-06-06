"""Fixture loader for mock A1 LLM response fixtures used in golden-set evaluation.

Loads canned LLM responses from JSON files so the eval runner can replay
deterministic responses against golden items without calling a real LLM.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class A1Fixture:
    """Canned LLM response for a single A1 golden item."""

    is_valid_signal: bool
    confidence: float
    signal_type: str = ""
    reasoning: str = ""


def load_a1_fixtures(path: Path) -> dict[str, A1Fixture]:
    """Load A1 fixture responses from a JSON file.

    The JSON file is expected to map ``item_id -> {is_valid_signal, confidence,
    signal_type, reasoning}``.

    Returns an empty dict if the file does not exist.
    """
    if not path.exists():
        return {}

    with path.open() as f:
        raw: dict[str, dict[str, Any]] = json.load(f)

    fixtures: dict[str, A1Fixture] = {}
    for item_id, entry in raw.items():
        fixtures[item_id] = A1Fixture(
            is_valid_signal=entry["is_valid_signal"],
            confidence=entry["confidence"],
            signal_type=entry.get("signal_type", ""),
            reasoning=entry.get("reasoning", ""),
        )
    return fixtures
