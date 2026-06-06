"""Pipeline trigger, jobs, runs, and prompt-pack endpoints."""
from __future__ import annotations

import subprocess
import sys
import threading
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from niche_radar.api.jobs import job_manager
from niche_radar.api.routes._common import _db

router = APIRouter(tags=["pipeline"])


class PipelineRunLabel(BaseModel):
    label: str


# ── Job runners ──────────────────────────────────────────────────────────────


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


# ── Trigger endpoints ────────────────────────────────────────────────────────


@router.post("/api/pipeline/collect")
def trigger_collect(source: Optional[str] = None):
    job = job_manager.create("collect")
    cmd = [sys.executable, "-m", "niche_radar", "collect"]
    if source:
        cmd += ["--source", source]
    threading.Thread(target=_run_job, args=(job.id, cmd), daemon=True).start()
    return {"job_id": job.id, "status": job.status}


@router.post("/api/pipeline/analyze")
def trigger_analyze():
    job = job_manager.create("analyze")
    cmd = [sys.executable, "-m", "niche_radar", "analyze"]
    threading.Thread(target=_run_job, args=(job.id, cmd), daemon=True).start()
    return {"job_id": job.id, "status": job.status}


@router.post("/api/pipeline/report")
def trigger_report():
    job = job_manager.create("report")
    cmd = [sys.executable, "-m", "niche_radar", "report"]
    threading.Thread(target=_run_job, args=(job.id, cmd), daemon=True).start()
    return {"job_id": job.id, "status": job.status}


@router.post("/api/pipeline/run-all")
def trigger_run_all():
    job = job_manager.create("run-all")
    threading.Thread(target=_run_all_steps, args=(job.id,), daemon=True).start()
    return {"job_id": job.id, "status": job.status}


# ── Job history ──────────────────────────────────────────────────────────────


@router.get("/api/pipeline/jobs")
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


@router.get("/api/pipeline/jobs/{job_id}/logs")
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


# ── Pipeline Runs (A/B comparison) ──────────────────────────────────────────


@router.get("/api/pipeline/runs")
def list_pipeline_runs(limit: int = 20):
    """List versioned pipeline runs for A/B comparison."""
    db = _db()
    try:
        rows = db.execute(
            "SELECT id, prompt_hash, model, item_count, cluster_count, niche_count, "
            "budget_used, label, started_at, completed_at "
            "FROM pipeline_runs ORDER BY started_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            {
                "id": r[0], "prompt_hash": r[1], "model": r[2],
                "item_count": r[3], "cluster_count": r[4], "niche_count": r[5],
                "budget_used": r[6], "label": r[7],
                "started_at": r[8], "completed_at": r[9],
            }
            for r in rows
        ]
    finally:
        db.close()


@router.get("/api/pipeline/runs/{run_id}")
def get_pipeline_run(run_id: str):
    """Get a specific pipeline run with its niche results for comparison."""
    db = _db()
    try:
        run_row = db.execute(
            "SELECT id, prompt_hash, model, item_count, cluster_count, niche_count, "
            "budget_used, label, started_at, completed_at "
            "FROM pipeline_runs WHERE id=?", (run_id,),
        ).fetchone()
        if not run_row:
            raise HTTPException(status_code=404, detail="Pipeline run not found")
        niches = db.execute(
            "SELECT na.niche_id, nc.keyword, na.verdict, na.opportunity_score, "
            "na.weighted_score, na.tier, na.feasibility_score "
            "FROM niche_analyses na JOIN niche_candidates nc ON na.niche_id = nc.id "
            "WHERE na.pipeline_run=? ORDER BY na.weighted_score DESC",
            (run_id,),
        ).fetchall()
        return {
            "run": {
                "id": run_row[0], "prompt_hash": run_row[1], "model": run_row[2],
                "item_count": run_row[3], "cluster_count": run_row[4], "niche_count": run_row[5],
                "budget_used": run_row[6], "label": run_row[7],
                "started_at": run_row[8], "completed_at": run_row[9],
            },
            "niches": [
                {
                    "niche_id": n[0], "keyword": n[1], "verdict": n[2],
                    "opportunity_score": n[3], "weighted_score": n[4],
                    "tier": n[5], "feasibility_score": n[6],
                }
                for n in niches
            ],
        }
    finally:
        db.close()


@router.put("/api/pipeline/runs/{run_id}/label")
def label_pipeline_run(run_id: str, body: PipelineRunLabel):
    """Label a pipeline run (e.g. 'baseline', 'new-prompts-v2')."""
    db = _db()
    try:
        db.execute("UPDATE pipeline_runs SET label=? WHERE id=?", (body.label, run_id))
        db.commit()
        return {"ok": True}
    finally:
        db.close()


# ── Prompt Packs ─────────────────────────────────────────────────────────────


@router.get("/api/prompt-packs")
def get_prompt_packs():
    """List available prompt packs."""
    from niche_radar.agents.prompts import list_prompt_packs
    return list_prompt_packs()
