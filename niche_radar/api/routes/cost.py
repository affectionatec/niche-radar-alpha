"""Cost Insights endpoint."""
from __future__ import annotations

from fastapi import APIRouter

from niche_radar.api.routes._common import _db

router = APIRouter(tags=["cost"])


@router.get("/api/cost/summary")
def get_cost_summary(days: int = 30):
    """Aggregated LLM token usage for the Cost Insights dashboard."""
    from niche_radar.llm.usage import get_usage_summary
    db = _db()
    try:
        db_path_row = db.execute("PRAGMA database_list").fetchone()
        db_path = db_path_row[2] if db_path_row else ""
        return get_usage_summary(db_path, days=days)
    finally:
        db.close()
