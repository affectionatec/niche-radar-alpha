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
def list_niches(
    source: Optional[str] = None,
    min_score: Optional[float] = None,
    max_score: Optional[float] = None,
    monetization: Optional[str] = None,  # any | yes | no
    trend: Optional[str] = None,         # any | growing | stable | declining
    format: Optional[str] = None,        # csv
):
    """List active niches with optional filters. Pass format=csv for CSV download."""
    import csv, io
    db = _db()
    try:
        niches = repository.get_active_niches_with_scores(db)
        for n in niches:
            n["tier"] = _tier(n["llm_score"])

        # Apply filters
        if source:
            # Filter niches that have at least one linked item from this source
            linked_sources = {}
            for n in niches:
                nid = n["id"]
                row = db.execute(
                    "SELECT COUNT(*) FROM niche_item_links nil JOIN raw_items ri ON nil.raw_item_id=ri.id WHERE nil.niche_id=? AND ri.source=?",
                    (nid, source),
                ).fetchone()
                linked_sources[nid] = (row[0] or 0) > 0
            niches = [n for n in niches if linked_sources.get(n["id"])]

        if min_score is not None:
            niches = [n for n in niches if (n.get("llm_score") or 0) >= min_score]
        if max_score is not None:
            niches = [n for n in niches if (n.get("llm_score") or 0) <= max_score]

        if monetization and monetization != "any":
            # Pain points JSON contains willingness-to-pay evidence
            for n in niches:
                pains = n.get("pain_points") or []
                has_monetization = any(p.get("quote") for p in pains)
                n["_has_monetization"] = has_monetization
            if monetization == "yes":
                niches = [n for n in niches if n.get("_has_monetization")]
            elif monetization == "no":
                niches = [n for n in niches if not n.get("_has_monetization")]
            for n in niches:
                n.pop("_has_monetization", None)

        if trend and trend != "any":
            niches = [n for n in niches if n.get("momentum_label") == trend]

        if format == "csv":
            from fastapi.responses import StreamingResponse
            buf = io.StringIO()
            fields = ["id", "keyword", "tool_concept", "llm_score", "tier", "build_complexity",
                      "target_audience", "monetization", "momentum_label", "verdict", "last_seen"]
            writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(niches)
            buf.seek(0)
            return StreamingResponse(
                iter([buf.getvalue()]),
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=niches.csv"},
            )

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
        niche["is_shortlisted"] = repository.is_shortlisted(db, niche_id)
        items = repository.get_niche_items(db, niche_id)
        # Latest analysis row for web_validation + verdict details
        analysis_row = db.execute(
            "SELECT verdict, opportunity_score, weighted_score, tier, feasibility_score, "
            "web_validation, a6_result, a7_result, a8_result, a4_result, "
            "a2_aggregate, a3_result, a5_result, confidence "
            "FROM niche_analyses WHERE niche_id=? ORDER BY analyzed_at DESC LIMIT 1",
            (niche_id,),
        ).fetchone()
        niche["analysis"] = None
        if analysis_row:
            import json as _json
            a4_raw = _json.loads(analysis_row[9]) if analysis_row[9] else None
            a4_scores = None
            if isinstance(a4_raw, dict):
                a4_scores = a4_raw.get("scores", a4_raw)
            a6_full = _json.loads(analysis_row[6]) if analysis_row[6] else None
            niche["analysis"] = {
                "verdict": analysis_row[0],
                "opportunity_score": analysis_row[1],
                "weighted_score": analysis_row[2],
                "pipeline_tier": analysis_row[3],
                "feasibility_score": analysis_row[4],
                "web_validation": _json.loads(analysis_row[5]) if analysis_row[5] else None,
                "go_no_go_rationale": (a6_full or {}).get("full_rationale"),
                "prd": _json.loads(analysis_row[7]) if analysis_row[7] else None,
                "brief": _json.loads(analysis_row[8]) if analysis_row[8] else None,
                "a4_scores": a4_scores,
                "a6_detail": a6_full,
                "a5_detail": _json.loads(analysis_row[12]) if analysis_row[12] else None,
                "confidence": analysis_row[13],
            }
        return {"niche": niche, "items": items}
    finally:
        db.close()


class ShortlistNote(BaseModel):
    note: Optional[str] = ""


@app.post("/api/niches/{niche_id}/shortlist")
def star_niche(niche_id: str, body: ShortlistNote = ShortlistNote()):
    db = _db()
    try:
        niche = repository.get_niche_by_id(db, niche_id)
        if not niche:
            raise HTTPException(status_code=404, detail="Niche not found")
        repository.add_to_shortlist(db, niche_id, body.note or "")
        return {"ok": True}
    finally:
        db.close()


@app.delete("/api/niches/{niche_id}/shortlist")
def unstar_niche(niche_id: str):
    db = _db()
    try:
        repository.remove_from_shortlist(db, niche_id)
        return {"ok": True}
    finally:
        db.close()


@app.get("/api/shortlist")
def get_shortlist():
    db = _db()
    try:
        return repository.list_shortlist(db)
    finally:
        db.close()


@app.post("/api/niches/{niche_id}/validate")
def validate_niche(niche_id: str):
    """Re-run web validation (DDG search) for a niche on demand."""
    db = _db()
    try:
        niche = repository.get_niche_by_id(db, niche_id)
        if not niche:
            raise HTTPException(status_code=404, detail="Niche not found")

        import json as _json
        from niche_radar.agents.web_validate import validate_opportunity

        # Get the niche's keywords from aliases + keyword
        keywords = ([niche.get("keyword", "")] + (niche.get("aliases") or []))
        keywords = [k for k in keywords if k][:5]
        vr = validate_opportunity(keywords, dry_run=False)
        result_json = _json.dumps(vr.to_dict())

        # Persist to the latest analysis row
        analysis_id_row = db.execute(
            "SELECT id FROM niche_analyses WHERE niche_id=? ORDER BY analyzed_at DESC LIMIT 1",
            (niche_id,),
        ).fetchone()
        if analysis_id_row:
            repository.set_web_validation(db, analysis_id_row[0], result_json)

        return {"verdict": vr.verdict, "evidence": vr.evidence}
    finally:
        db.close()


@app.get("/api/niches/{niche_id}/momentum")
def get_momentum(niche_id: str):
    db = _db()
    try:
        niche = repository.get_niche_by_id(db, niche_id)
        if not niche:
            raise HTTPException(status_code=404, detail="Niche not found")
        from niche_radar.storage.momentum import compute_momentum
        return compute_momentum(db, niche_id)
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


@app.get("/api/settings/models")
def list_provider_models():
    """Fetch available models from the configured LLM provider's API.

    Calls GET {base_url}/models (OpenAI-compatible) or returns an empty
    list for providers that don't support model listing (e.g. Anthropic).
    """
    import httpx

    db = _db()
    settings = get_settings()
    try:
        provider = repository.get_app_setting(db, "llm_provider") or settings.llm_provider
        base_url = repository.get_app_setting(db, "llm_base_url") or settings.llm_base_url
        api_key = repository.get_app_setting(db, "llm_api_key") or settings.llm_api_key

        # Anthropic doesn't have a list-models endpoint
        if provider == "anthropic":
            return {"models": [], "source": "none"}

        # Build the models endpoint URL
        url = (base_url.rstrip("/") if base_url else "https://api.openai.com/v1").rstrip("/")
        if not url.endswith("/models"):
            url += "/models"

        headers: dict[str, str] = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        resp = httpx.get(url, headers=headers, timeout=10.0)
        resp.raise_for_status()
        data = resp.json()

        # OpenAI-compatible format: {"data": [{"id": "model-name", ...}, ...]}
        model_ids: list[str] = []
        if "data" in data and isinstance(data["data"], list):
            for m in data["data"]:
                mid = m.get("id", "")
                if mid:
                    model_ids.append(mid)
        # Ollama format: {"models": [{"name": "llama3.3", ...}, ...]}
        elif "models" in data and isinstance(data["models"], list):
            for m in data["models"]:
                name = m.get("name", "")
                if name:
                    # Strip ":latest" tag that Ollama appends
                    model_ids.append(name.split(":")[0] if ":" in name else name)

        model_ids.sort()
        return {"models": model_ids, "source": "api"}
    except Exception as exc:
        return {"models": [], "source": "error", "error": str(exc)}
    finally:
        db.close()


# ── Scoring weights ──────────────────────────────────────────────────────────


@app.get("/api/settings/scoring-weights")
def get_scoring_weights_api():
    db = _db()
    try:
        return repository.get_scoring_weights(db)
    finally:
        db.close()


class ScoringWeightsBody(BaseModel):
    problem_clarity: float = 1.0
    market_size: float = 1.5
    willingness_to_pay: float = 2.0
    competition_gap: float = 1.5
    technical_feasibility: float = 1.0
    distribution_clarity: float = 1.5
    trend_momentum: float = 1.0


@app.put("/api/settings/scoring-weights")
def set_scoring_weights_api(body: ScoringWeightsBody):
    db = _db()
    try:
        weights = body.model_dump()
        repository.set_scoring_weights(db, weights)
        return {"status": "ok", "weights": weights}
    finally:
        db.close()


# ── Source credentials & configuration ───────────────────────────────────────

class SourceCredentialUpdate(BaseModel):
    credentials: dict  # {key: value, ...}  — values are strings; None means delete


@app.get("/api/sources")
def list_sources():
    """List all known sources with credential status and last collection timestamp."""
    from niche_radar.collectors import ALL_SOURCES, _get_collector
    db = _db()
    try:
        out = []
        for slug in ALL_SOURCES:
            try:
                collector = _get_collector(slug)
            except Exception:
                continue
            creds = repository.get_source_credentials(db, slug)
            # Determine which required fields are missing
            schema = getattr(collector, "CREDENTIAL_SCHEMA", [])
            required_missing = [
                f["key"] for f in schema
                if not f.get("optional") and not creds.get(f["key"])
            ]
            # Last successful collection
            row = db.execute(
                "SELECT MAX(completed_at) FROM collection_runs WHERE source=? AND status != 'failed'",
                (slug,),
            ).fetchone()
            last_success = row[0] if row else None
            # Mask secrets in output
            masked = {k: ("••••" if any(f["key"] == k and f.get("secret") for f in schema) else v)
                      for k, v in creds.items()}
            out.append({
                "slug": slug,
                "schema": schema,
                "credentials_set": masked,
                "required_missing": required_missing,
                "configured": len(required_missing) == 0,
                "last_success": last_success,
            })
        return out
    finally:
        db.close()


@app.get("/api/sources/{slug}")
def get_source(slug: str):
    """Return credential schema + current (masked) values for one source.

    Returns the same shape as a single item from GET /api/sources so the
    per-source frontend page can reuse the same SourceStatus type.
    """
    from niche_radar.collectors import _get_collector
    try:
        collector = _get_collector(slug)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Unknown source: {slug}")
    db = _db()
    try:
        schema = getattr(collector, "CREDENTIAL_SCHEMA", [])
        creds = repository.get_source_credentials(db, slug)
        required_missing = [
            f["key"] for f in schema
            if not f.get("optional") and not creds.get(f["key"])
        ]
        masked = {k: ("••••" if any(f["key"] == k and f.get("secret") for f in schema) else v)
                  for k, v in creds.items()}
        row = db.execute(
            "SELECT MAX(completed_at) FROM collection_runs WHERE source=? AND status != 'failed'",
            (slug,),
        ).fetchone()
        last_success = row[0] if row else None
        return {
            "slug": slug,
            "schema": schema,
            "credentials_set": masked,
            "required_missing": required_missing,
            "configured": len(required_missing) == 0,
            "last_success": last_success,
        }
    finally:
        db.close()


@app.post("/api/sources/{slug}")
def update_source_credentials(slug: str, body: SourceCredentialUpdate):
    """Upsert or delete per-source credentials. Pass value=None to delete a key."""
    from niche_radar.collectors import _get_collector
    try:
        _get_collector(slug)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Unknown source: {slug}")
    db = _db()
    try:
        for key, value in body.credentials.items():
            if value is None:
                repository.delete_source_credential(db, slug, key)
            else:
                repository.set_source_credential(db, slug, key, str(value))
        return {"ok": True}
    finally:
        db.close()


@app.post("/api/sources/{slug}/test")
def test_source_connection(slug: str):
    """Invoke the collector's test_connection() classmethod and return the result."""
    from niche_radar.collectors import _get_collector
    try:
        collector_cls = type(_get_collector(slug))
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Unknown source: {slug}")
    db = _db()
    settings = get_settings()
    try:
        ok, message = collector_cls.test_connection(db, settings)
        return {"ok": ok, "message": message}
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


# ── Cost Insights ──────────────────────────────────────────────────────────────

@app.get("/api/cost/summary")
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
