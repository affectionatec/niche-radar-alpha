"""FastAPI HTTP server exposing Niche Radar data and pipeline controls."""
from __future__ import annotations

import subprocess
import sys
import threading
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from niche_radar.api.jobs import job_manager
from niche_radar.config import get_settings
from niche_radar.storage.database import get_db
from niche_radar.storage import repository

app = FastAPI(title="Niche Radar API", version="0.2.0")

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
        niches = repository.get_active_niches_with_scores(db)
        for n in niches:
            n["tier"] = _tier(n["llm_score"])
        return niches
    finally:
        db.close()


@app.get("/api/niches/{niche_id}")
def get_niche(niche_id: str):
    db = _db()
    try:
        niche = repository.get_niche_by_id(db, niche_id)
        if not niche:
            raise HTTPException(status_code=404, detail="Niche not found")
        niche["tier"] = _tier(niche["llm_score"])
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
        (f for f in report_dir.iterdir() if f.is_file() and f.suffix == ".md"),
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


# ── Settings endpoints ────────────────────────────────────────────────────────

class LLMSettingsUpdate(BaseModel):
    llm_provider: Optional[str] = None
    llm_api_key: Optional[str] = None
    llm_model: Optional[str] = None
    llm_base_url: Optional[str] = None


@app.get("/api/settings")
def get_llm_settings():
    db = _db()
    settings = get_settings()
    try:
        provider = repository.get_app_setting(db, "llm_provider") or settings.llm_provider
        model = repository.get_app_setting(db, "llm_model") or settings.llm_model
        base_url = repository.get_app_setting(db, "llm_base_url") or settings.llm_base_url
        stored_key = repository.get_app_setting(db, "llm_api_key")
        has_key = bool(stored_key or settings.llm_api_key)
        return {
            "llm_provider": provider,
            "llm_model": model,
            "llm_base_url": base_url,
            "llm_api_key_set": has_key,
        }
    finally:
        db.close()


@app.post("/api/settings")
def update_llm_settings(body: LLMSettingsUpdate):
    db = _db()
    try:
        if body.llm_provider is not None:
            repository.set_app_setting(db, "llm_provider", body.llm_provider)
        if body.llm_api_key is not None:
            repository.set_app_setting(db, "llm_api_key", body.llm_api_key)
        if body.llm_model is not None:
            repository.set_app_setting(db, "llm_model", body.llm_model)
        if body.llm_base_url is not None:
            repository.set_app_setting(db, "llm_base_url", body.llm_base_url)
        return {"ok": True}
    finally:
        db.close()


@app.post("/api/settings/test")
def test_llm_connection():
    from niche_radar.analysis.analyzer import _get_llm_client
    db = _db()
    settings = get_settings()
    try:
        client = _get_llm_client(db, settings)
        client.complete("Reply with the word OK.")
        return {"ok": True, "message": "Connection successful"}
    except Exception as exc:
        return {"ok": False, "message": str(exc)}
    finally:
        db.close()


# ── Pipeline job runner ───────────────────────────────────────────────────────

def _run_job(job_id: str, cmd: list[str]) -> None:
    job_manager.set_status(job_id, "running")
    step_name = cmd[-1] if cmd else "?"
    print(f"[job {job_id[:8]} {step_name}] started", flush=True)
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
            line = line.rstrip()
            job_manager.append_log(job_id, line)
            # Mirror to container stdout so it appears in `docker logs` / Docker Dashboard
            print(f"[job {job_id[:8]} {step_name}] {line}", flush=True)
        proc.wait()
        if proc.returncode == 1:
            job_manager.append_log(job_id, "WARNING: completed with partial failures")
            print(f"[job {job_id[:8]} {step_name}] WARNING: partial failures", flush=True)
            job_manager.set_status(job_id, "done")
        else:
            status = "done" if proc.returncode == 0 else "failed"
            job_manager.set_status(job_id, status)
            print(f"[job {job_id[:8]} {step_name}] {status} (exit {proc.returncode})", flush=True)
    except Exception as exc:
        job_manager.append_log(job_id, f"ERROR: {exc}")
        print(f"[job {job_id[:8]} {step_name}] ERROR: {exc}", flush=True)
        job_manager.set_status(job_id, "failed")


def _run_all_steps(job_id: str) -> None:
    """Run collect → analyze → report sequentially."""
    steps = ["collect", "analyze", "report"]
    job_manager.set_status(job_id, "running")
    short = job_id[:8]
    print(f"[job {short} run-all] started: {' → '.join(steps)}", flush=True)
    for step in steps:
        cmd = [sys.executable, "-m", "niche_radar", step]
        job_manager.append_log(job_id, f"=== {step.upper()} ===")
        print(f"[job {short} run-all] === {step.upper()} ===", flush=True)
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
                line = line.rstrip()
                job_manager.append_log(job_id, line)
                print(f"[job {short} {step}] {line}", flush=True)
            proc.wait()
            if proc.returncode == 1:
                job_manager.append_log(job_id, f"WARNING: {step} had partial failures, continuing")
                print(f"[job {short} {step}] WARNING: partial failures", flush=True)
            elif proc.returncode >= 2:
                job_manager.append_log(job_id, f"FAILED (exit {proc.returncode})")
                print(f"[job {short} {step}] FAILED exit {proc.returncode}", flush=True)
                job_manager.set_status(job_id, "failed")
                return
        except Exception as exc:
            job_manager.append_log(job_id, f"ERROR: {exc}")
            print(f"[job {short} {step}] ERROR: {exc}", flush=True)
            job_manager.set_status(job_id, "failed")
            return
    job_manager.set_status(job_id, "done")
    print(f"[job {short} run-all] done", flush=True)


@app.post("/api/pipeline/collect")
def trigger_collect(source: Optional[str] = None):
    job = job_manager.create("collect")
    cmd = [sys.executable, "-m", "niche_radar", "collect"]
    if source:
        cmd += ["--source", source]
    threading.Thread(target=_run_job, args=(job.id, cmd), daemon=True).start()
    return {"job_id": job.id, "status": job.status}


@app.post("/api/pipeline/analyze")
def trigger_analyze():
    job = job_manager.create("analyze")
    cmd = [sys.executable, "-m", "niche_radar", "analyze"]
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
