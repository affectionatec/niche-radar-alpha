"""Search trend scoring."""

from __future__ import annotations

from niche_radar.storage.repository import get_trend_snapshots


def _flatten(values) -> list[float]:
    if isinstance(values, (int, float)):
        return [float(values)]
    if isinstance(values, list):
        flattened: list[float] = []
        for item in values:
            flattened.extend(_flatten(item))
        return flattened
    if isinstance(values, dict):
        for key in ("interest", "values", "timeline_data", "series", "data"):
            if key in values:
                return _flatten(values[key])
        if "value" in values:
            return _flatten(values["value"])
    return []


def score_search_trend(niche, db) -> float:
    """Compute a 0-100 score from the trend-series slope."""
    series: list[float] = []
    for snapshot in get_trend_snapshots(db, niche["id"]):
        series.extend(_flatten(snapshot.get("data")))
    if len(series) < 2:
        return 0.0

    x_values = list(range(len(series)))
    x_mean = sum(x_values) / len(x_values)
    y_mean = sum(series) / len(series)
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_values, series, strict=False))
    denominator = sum((x - x_mean) ** 2 for x in x_values)
    slope = 0.0 if denominator == 0 else numerator / denominator
    clamped = max(-5.0, min(5.0, slope))
    return round(((clamped + 5.0) / 10.0) * 100.0, 2)
