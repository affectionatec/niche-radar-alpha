"""Scoring engine orchestration."""

from __future__ import annotations

import structlog

from niche_radar.scoring.composite import compute_composite
from niche_radar.scoring.content_gap import score_content_gap
from niche_radar.scoring.engagement import score_engagement
from niche_radar.scoring.market_traction import score_market_traction
from niche_radar.scoring.search_trend import score_search_trend
from niche_radar.storage.repository import get_active_niches, insert_niche_score

logger = structlog.get_logger()


def run_scoring(db, settings, dry_run: bool = False) -> int:
    """Score all active niches above the occurrence threshold."""
    scored = 0
    for niche in get_active_niches(db):
        if niche.get("occurrence_count", 0) < settings.min_occurrence_threshold:
            continue
        engagement = score_engagement(niche, db)
        search_trend = score_search_trend(niche, db)
        content_gap = score_content_gap(niche, db)
        market_traction = score_market_traction(niche, db)
        composite = compute_composite(engagement, search_trend, content_gap, market_traction)
        if not dry_run:
            insert_niche_score(db, niche["id"], engagement, search_trend, content_gap, market_traction, composite)
        scored += 1
    logger.info("scoring_finished", niches=scored, dry_run=dry_run)
    return scored
