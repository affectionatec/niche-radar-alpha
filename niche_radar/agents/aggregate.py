"""Aggregate per-item A2 outputs into one cluster-level A2.

Deterministic, no LLM call. Strategy:
- who:                     longest by token count (most specific wins)
- what:                    longest by token count (richer description wins)
- when:                    first non-empty
- current_workaround:      first non-empty
- why_current_sucks:       longest non-empty
- desired_outcome:         longest non-empty
- emotional_intensity:     max across the cluster
- frequency:               mode (most-common)
- affected_scale:          mode
- willingness_to_pay_signal: any True
- pay_signal_evidence:     longest quote among items where WTP was True
- keywords:                top-5 deduped by frequency across the cluster

If the cluster is a singleton, just return that item's A2 unchanged.
"""

from __future__ import annotations

from collections import Counter
from typing import Iterable

from niche_radar.agents.models import A2Output


def _safe_str(v) -> str:
    return v if isinstance(v, str) else ""


def _tokens(s: str) -> int:
    return len((_safe_str(s)).split())


def _longest_str(values: Iterable, *, by_tokens: bool = True) -> str | None:
    vals = [_safe_str(v) for v in values if v]
    if not vals:
        return None
    key = (lambda s: _tokens(s)) if by_tokens else (lambda s: len(s))
    return max(vals, key=key)


def _first_str(values: Iterable) -> str | None:
    for v in values:
        if isinstance(v, str) and v.strip():
            return v
    return None


def _mode(values: Iterable):
    pool = [v for v in values if v]
    if not pool:
        return None
    return Counter(pool).most_common(1)[0][0]


def aggregate_cluster_a2(extractions: list[dict]) -> A2Output:
    """Merge per-item A2 dicts (from `item_pain_extractions.a2_result`) into one A2Output.

    Each entry in `extractions` must have an `a2` key whose value is a dict (or None).
    """
    a2s: list[dict] = [e.get("a2") or {} for e in extractions if e.get("a2")]
    if not a2s:
        return A2Output()
    if len(a2s) == 1:
        # Pass-through — just validate via pydantic
        return A2Output(**a2s[0])

    # Keyword frequency
    bag: Counter = Counter()
    for a2 in a2s:
        for kw in (a2.get("keywords") or []):
            if isinstance(kw, str) and kw.strip():
                bag[kw.strip().lower()] += 1
    top_keywords = [k for k, _ in bag.most_common(5)]

    # Willingness to pay
    wtp = any(bool(a2.get("willingness_to_pay_signal")) for a2 in a2s)
    quote_pool = [a2.get("pay_signal_evidence") for a2 in a2s
                  if bool(a2.get("willingness_to_pay_signal"))]
    pay_signal_evidence = _longest_str(quote_pool, by_tokens=False)

    # Numeric max
    intensities = [a2.get("emotional_intensity") for a2 in a2s
                   if isinstance(a2.get("emotional_intensity"), (int, float))]
    emotional_intensity = max(intensities) if intensities else None

    return A2Output(
        who=_longest_str(a2.get("who") for a2 in a2s),
        what=_longest_str(a2.get("what") for a2 in a2s),
        when=_first_str(a2.get("when") for a2 in a2s),
        current_workaround=_first_str(a2.get("current_workaround") for a2 in a2s),
        why_current_sucks=_longest_str(a2.get("why_current_sucks") for a2 in a2s),
        desired_outcome=_longest_str(a2.get("desired_outcome") for a2 in a2s),
        emotional_intensity=emotional_intensity,
        frequency=_mode(a2.get("frequency") for a2 in a2s),
        affected_scale=_mode(a2.get("affected_scale") for a2 in a2s),
        willingness_to_pay_signal=wtp,
        pay_signal_evidence=pay_signal_evidence,
        keywords=top_keywords,
    )
