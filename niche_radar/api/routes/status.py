"""GET /api/status — system health and data freshness."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from niche_radar.api.routes._common import _db
from niche_radar.config import get_settings
from niche_radar.storage import repository

router = APIRouter(tags=["status"])


@router.get("/api/status")
def get_status():
    db = _db()
    settings = get_settings()
    try:
        stats = db.execute(
            "SELECT "
            "(SELECT COUNT(*) FROM raw_items) as raw_count, "
            "(SELECT COUNT(*) FROM niche_candidates WHERE status='active') as niche_count, "
            "(SELECT MAX(started_at) FROM collection_runs) as last_run, "
            "(SELECT COUNT(*) FROM collection_runs) as cycle_count"
        ).fetchone()
        sources = repository.get_system_health(db)
        freshness = repository.get_freshness_summary(db)
        return {
            "raw_items": stats[0] or 0,
            "active_niches": stats[1] or 0,
            "last_collection": stats[2],
            "collection_cycle": stats[3] or 0,
            "sources": sources,
            "freshness": {
                "analysis_window_days": settings.analysis_window_days,
                "rules": {
                    "reddit_hours": settings.freshness_reddit_hours,
                    "hn_hours": settings.freshness_hn_hours,
                    "github_hours": settings.freshness_github_hours,
                    "google_trends_hours": settings.freshness_google_trends_hours,
                    "youtube_hours": settings.freshness_youtube_hours,
                },
                "per_source": freshness["sources"],
            },
        }
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Database error: {exc}") from exc
    finally:
        db.close()
