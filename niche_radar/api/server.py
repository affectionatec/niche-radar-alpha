"""FastAPI HTTP server exposing Niche Radar data and pipeline controls."""
from __future__ import annotations

import subprocess
import sys
import threading
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from niche_radar.api.jobs import job_manager
from niche_radar.config import get_settings
from niche_radar.storage.database import get_db
from niche_radar.storage import repository

app = FastAPI(title="Niche Radar API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
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
    report_dir = Path(settings.report_output_dir).resolve()
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


@app.get("/api/reports/{filename}")
def get_report_content(filename: str):
    settings = get_settings()
    report_dir = Path(settings.report_output_dir).resolve()
    try:
        file_path = (report_dir / filename).resolve()
        file_path.relative_to(report_dir)
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Report not found")
    return {"content": file_path.read_text(encoding="utf-8")}


def _run_job(job_id: str, cmd: list[str]) -> None:
    """Run a single subprocess command, stream stdout to job logs."""
    job_manager.set_status(job_id, "running")
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        if proc.stdout is None:
            raise RuntimeError("subprocess stdout unavailable")
        for line in proc.stdout:
            job_manager.append_log(job_id, line.rstrip())
        proc.wait()
        job_manager.set_status(job_id, "done" if proc.returncode == 0 else "failed")
    except Exception as exc:
        job_manager.append_log(job_id, f"ERROR: {exc}")
        job_manager.set_status(job_id, "failed")


def _run_all_steps(job_id: str) -> None:
    """Run collect → extract → score → report sequentially."""
    steps = ["collect", "extract", "score", "report"]
    job_manager.set_status(job_id, "running")
    for step in steps:
        cmd = [sys.executable, "-m", "niche_radar", step]
        job_manager.append_log(job_id, f"=== {step.upper()} ===")
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            if proc.stdout is None:
                raise RuntimeError("subprocess stdout unavailable")
            for line in proc.stdout:
                job_manager.append_log(job_id, line.rstrip())
            proc.wait()
            if proc.returncode != 0:
                job_manager.append_log(job_id, f"FAILED (exit {proc.returncode})")
                job_manager.set_status(job_id, "failed")
                return
        except Exception as exc:
            job_manager.append_log(job_id, f"ERROR: {exc}")
            job_manager.set_status(job_id, "failed")
            return
    job_manager.set_status(job_id, "done")


@app.post("/api/pipeline/collect")
def trigger_collect(source: Optional[str] = None):
    job = job_manager.create("collect")
    cmd = [sys.executable, "-m", "niche_radar", "collect"]
    if source:
        cmd += ["--source", source]
    threading.Thread(target=_run_job, args=(job.id, cmd), daemon=True).start()
    return {"job_id": job.id, "status": job.status}


@app.post("/api/pipeline/extract")
def trigger_extract():
    job = job_manager.create("extract")
    cmd = [sys.executable, "-m", "niche_radar", "extract"]
    threading.Thread(target=_run_job, args=(job.id, cmd), daemon=True).start()
    return {"job_id": job.id, "status": job.status}


@app.post("/api/pipeline/score")
def trigger_score():
    job = job_manager.create("score")
    cmd = [sys.executable, "-m", "niche_radar", "score"]
    threading.Thread(target=_run_job, args=(job.id, cmd), daemon=True).start()
    return {"job_id": job.id, "status": job.status}


@app.post("/api/pipeline/report")
def trigger_report():
    job = job_manager.create("report")
    cmd = [sys.executable, "-m", "niche_radar", "report"]
    threading.Thread(target=_run_job, args=(job.id, cmd), daemon=True).start()
    return {"job_id": job.id, "status": job.status}


@app.post("/api/pipeline/run-all")
def trigger_run_all():
    job = job_manager.create("run-all")
    threading.Thread(target=_run_all_steps, args=(job.id,), daemon=True).start()
    return {"job_id": job.id, "status": job.status}


@app.get("/api/pipeline/jobs")
def list_jobs():
    jobs = job_manager.list_recent(20)
    return [
        {
            "id": j.id,
            "step": j.step,
            "status": j.status,
            "created_at": j.created_at,
            "completed_at": j.completed_at,
        }
        for j in jobs
    ]


@app.get("/api/pipeline/jobs/{job_id}/logs")
def get_job_logs(job_id: str):
    job = job_manager.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "id": job.id,
        "step": job.step,
        "status": job.status,
        "logs": job.logs,
        "created_at": job.created_at,
        "completed_at": job.completed_at,
    }
