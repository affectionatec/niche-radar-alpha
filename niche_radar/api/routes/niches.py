"""Niche listing, detail, shortlist, validate, and momentum endpoints."""
from __future__ import annotations

import csv
import io
import json as _json
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from niche_radar.api.routes._common import _db, _tier
from niche_radar.storage import repository

router = APIRouter(tags=["niches"])


class ShortlistNote(BaseModel):
    note: Optional[str] = ""


@router.get("/api/niches")
def list_niches(
    source: Optional[str] = None,
    min_score: Optional[float] = None,
    max_score: Optional[float] = None,
    monetization: Optional[str] = None,
    trend: Optional[str] = None,
    format: Optional[str] = None,
):
    """List active niches with optional filters. Pass format=csv for CSV download."""
    db = _db()
    try:
        niches = repository.get_active_niches_with_scores(db)
        for n in niches:
            n["tier"] = _tier(n["llm_score"])

        if source:
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


@router.get("/api/niches/{niche_id}")
def get_niche(niche_id: str):
    db = _db()
    try:
        niche = repository.get_niche_by_id(db, niche_id)
        if not niche:
            raise HTTPException(status_code=404, detail="Niche not found")
        niche["tier"] = _tier(niche["llm_score"])
        niche["is_shortlisted"] = repository.is_shortlisted(db, niche_id)
        items = repository.get_niche_items(db, niche_id)
        analysis_row = db.execute(
            "SELECT verdict, opportunity_score, weighted_score, tier, feasibility_score, "
            "web_validation, a6_result, a7_result, a8_result, a4_result, "
            "a2_aggregate, a3_result, a5_result, confidence "
            "FROM niche_analyses WHERE niche_id=? ORDER BY analyzed_at DESC LIMIT 1",
            (niche_id,),
        ).fetchone()
        niche["analysis"] = None
        if analysis_row:
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


@router.post("/api/niches/{niche_id}/shortlist")
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


@router.delete("/api/niches/{niche_id}/shortlist")
def unstar_niche(niche_id: str):
    db = _db()
    try:
        repository.remove_from_shortlist(db, niche_id)
        return {"ok": True}
    finally:
        db.close()


@router.get("/api/shortlist")
def get_shortlist():
    db = _db()
    try:
        return repository.list_shortlist(db)
    finally:
        db.close()


@router.post("/api/niches/{niche_id}/validate")
def validate_niche(niche_id: str):
    """Re-run web validation (DDG search) for a niche on demand."""
    db = _db()
    try:
        niche = repository.get_niche_by_id(db, niche_id)
        if not niche:
            raise HTTPException(status_code=404, detail="Niche not found")

        from niche_radar.agents.web_validate import validate_opportunity

        keywords = ([niche.get("keyword", "")] + (niche.get("aliases") or []))
        keywords = [k for k in keywords if k][:5]
        vr = validate_opportunity(keywords, dry_run=False)
        result_json = _json.dumps(vr.to_dict())

        analysis_id_row = db.execute(
            "SELECT id FROM niche_analyses WHERE niche_id=? ORDER BY analyzed_at DESC LIMIT 1",
            (niche_id,),
        ).fetchone()
        if analysis_id_row:
            repository.set_web_validation(db, analysis_id_row[0], result_json)

        return {"verdict": vr.verdict, "evidence": vr.evidence}
    finally:
        db.close()


@router.get("/api/niches/{niche_id}/momentum")
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
