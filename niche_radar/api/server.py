"""FastAPI HTTP server exposing Niche Radar data."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from niche_radar.config import get_settings
from niche_radar.storage.database import get_db
from niche_radar.storage import repository

app = FastAPI(title="Niche Radar API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


def _db():
    settings = get_settings()
    return get_db(settings.database_url)


@app.get("/api/status")
def get_status():
    db = _db()
    try:
        stats = db.execute(
            "SELECT "
            "(SELECT COUNT(*) FROM raw_items) as raw_count, "
            "(SELECT COUNT(*) FROM niche_candidates WHERE status='active') as niche_count, "
            "(SELECT COUNT(*) FROM niche_scores) as score_count, "
            "(SELECT MAX(started_at) FROM collection_runs) as last_run, "
            "(SELECT COUNT(*) FROM collection_runs) as cycle_count"
        ).fetchone()
        sources = repository.get_system_health(db)
        return {
            "raw_items": stats[0] or 0,
            "active_niches": stats[1] or 0,
            "scores_recorded": stats[2] or 0,
            "last_collection": stats[3],
            "collection_cycle": stats[4] or 0,
            "sources": sources,
        }
    finally:
        db.close()


def _tier(score: float) -> str:
    if score >= 80:
        return "high_priority"
    if score >= 65:
        return "watchlist"
    return "archive"


@app.get("/api/niches")
def list_niches():
    db = _db()
    try:
        scores = repository.get_latest_scores(db)
        for s in scores:
            s["tier"] = _tier(s["composite_score"])
            row = db.execute(
                "SELECT occurrence_count FROM niche_candidates WHERE id=?",
                (s["niche_id"],),
            ).fetchone()
            s["occurrence_count"] = row[0] if row else 1
        return scores
    finally:
        db.close()


@app.get("/api/niches/{niche_id}")
def get_niche(niche_id: str):
    db = _db()
    try:
        scores = repository.get_latest_scores(db)
        niche = next((s for s in scores if s["niche_id"] == niche_id), None)
        if not niche:
            raise HTTPException(status_code=404, detail="Niche not found")
        niche["tier"] = _tier(niche["composite_score"])
        row = db.execute(
            "SELECT occurrence_count FROM niche_candidates WHERE id=?",
            (niche_id,),
        ).fetchone()
        niche["occurrence_count"] = row[0] if row else 1
        items = repository.get_niche_items(db, niche_id)
        return {"niche": niche, "items": items}
    finally:
        db.close()


@app.get("/api/reports")
def list_reports():
    settings = get_settings()
    report_dir = Path(settings.report_output_dir)
    if not report_dir.exists():
        return []
    files = sorted(
        (f for f in report_dir.iterdir() if f.is_file()),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )
    return [
        {"filename": f.name, "size": f.stat().st_size, "modified": f.stat().st_mtime}
        for f in files
    ]
