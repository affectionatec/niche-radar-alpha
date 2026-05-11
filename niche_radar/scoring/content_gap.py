"""Content gap scoring."""

from __future__ import annotations

import math

from niche_radar.storage.repository import get_niche_items

_TRIGGER_PHRASES = [
    "is there a tool",
    "i wish there was",
    "alternative to",
    "how do you automate",
    "pricing is crazy",
    "looking for",
    "recommend a",
    "frustrated with",
]


def score_content_gap(niche, db) -> float:
    """Count pain-point trigger phrases and log-scale the result."""
    hits = 0
    for item in get_niche_items(db, niche["id"]):
        text = f"{item.get('title') or ''} {item.get('body') or ''}".lower()
        hits += sum(text.count(phrase) for phrase in _TRIGGER_PHRASES)
    return round(min(100.0, 20.0 * math.log2(hits + 1)), 2)
