"""8-agent LLM analysis pipeline.

Phase A (per raw_item, parallel): A1 signal filter → A2 pain extractor.
Phase B: cluster surviving items by pain similarity.
Phase C (per cluster, parallel): A3 → A4 → A5 → A6 → (A7 if GO) → A8.
Phase D: upsert into niche_candidates via mapping layer (keeps existing UI working).
"""

from niche_radar.agents.models import (
    A1Output,
    A2Output,
    A3Output,
    A4Output,
    A5Output,
    A6Output,
    A7Output,
    A8Output,
    PipelineResult,
)

__all__ = [
    "A1Output",
    "A2Output",
    "A3Output",
    "A4Output",
    "A5Output",
    "A6Output",
    "A7Output",
    "A8Output",
    "PipelineResult",
]
