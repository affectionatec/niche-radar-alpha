"""Shared helpers imported by all route modules."""
from __future__ import annotations

from niche_radar.config import get_settings
from niche_radar.storage.database import get_db


def _db():
    settings = get_settings()
    return get_db(settings.database_url)


def _tier(score: float) -> str:
    if score >= 80:
        return "high_priority"
    if score >= 65:
        return "watchlist"
    return "archive"
