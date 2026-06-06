"""Entity intelligence endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from niche_radar.api.routes._common import _db
from niche_radar.entities.repository import (
    get_entities,
    get_entity_by_id,
    get_trending_entities,
    get_entity_mentions,
    ENTITY_TYPES,
)

router = APIRouter(tags=["entities"])


@router.get("/api/entities")
def api_get_entities(
    type: str | None = None,
    sort: str = "last_seen",
    limit: int = 50,
    offset: int = 0,
):
    """List entities with optional type filter, sort, and pagination."""
    if type and type not in ENTITY_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid type. Must be one of: {', '.join(ENTITY_TYPES)}",
        )
    db = _db()
    try:
        items = get_entities(db, entity_type=type, sort_by=sort, limit=limit, offset=offset)
        total = db.execute(
            "SELECT COUNT(*) FROM entities" + (f" WHERE type='{type}'" if type else "")
        ).fetchone()[0]
        return {"items": items, "total": total}
    finally:
        db.close()


@router.get("/api/entities/trending")
def api_get_trending_entities(type: str | None = None, limit: int = 10):
    """Top entities by velocity score."""
    if type and type not in ENTITY_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid type. Must be one of: {', '.join(ENTITY_TYPES)}",
        )
    db = _db()
    try:
        return get_trending_entities(db, limit=limit, entity_type=type)
    finally:
        db.close()


@router.get("/api/entities/{entity_id}")
def api_get_entity_detail(entity_id: str):
    """Detailed entity view with stats, recent mentions, and velocity history."""
    db = _db()
    try:
        entity = get_entity_by_id(db, entity_id)
        if not entity:
            raise HTTPException(status_code=404, detail="Entity not found")
        return entity
    finally:
        db.close()


@router.get("/api/entities/{entity_id}/mentions")
def api_get_entity_mentions(entity_id: str, limit: int = 50, offset: int = 0):
    """Paginated mentions for a specific entity."""
    db = _db()
    try:
        entity = get_entity_by_id(db, entity_id)
        if not entity:
            raise HTTPException(status_code=404, detail="Entity not found")
        items = get_entity_mentions(db, entity_id, limit=limit, offset=offset)
        total = db.execute(
            "SELECT COUNT(*) FROM entity_mentions WHERE entity_id=?", (entity_id,)
        ).fetchone()[0]
        return {"items": items, "total": total}
    finally:
        db.close()
