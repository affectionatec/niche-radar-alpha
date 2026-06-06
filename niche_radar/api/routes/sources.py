"""Source credential and connection-test endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from niche_radar.api.routes._common import _db
from niche_radar.config import get_settings
from niche_radar.storage import repository

router = APIRouter(tags=["sources"])


class SourceCredentialUpdate(BaseModel):
    credentials: dict


@router.get("/api/sources")
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
            schema = getattr(collector, "CREDENTIAL_SCHEMA", [])
            required_missing = [
                f["key"] for f in schema
                if not f.get("optional") and not creds.get(f["key"])
            ]
            row = db.execute(
                "SELECT MAX(completed_at) FROM collection_runs WHERE source=? AND status != 'failed'",
                (slug,),
            ).fetchone()
            last_success = row[0] if row else None
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


@router.get("/api/sources/{slug}")
def get_source(slug: str):
    """Return credential schema + current (masked) values for one source."""
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


@router.post("/api/sources/{slug}")
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


@router.post("/api/sources/{slug}/test")
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
