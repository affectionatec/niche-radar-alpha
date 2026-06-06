"""LLM settings, scoring weights, and model listing endpoints."""
from __future__ import annotations

from typing import Optional

import httpx
from fastapi import APIRouter
from pydantic import BaseModel

from niche_radar.api.routes._common import _db
from niche_radar.config import get_settings
from niche_radar.storage import repository

router = APIRouter(tags=["settings"])


class LLMSettingsUpdate(BaseModel):
    llm_provider: Optional[str] = None
    llm_api_key: Optional[str] = None
    llm_model: Optional[str] = None
    llm_base_url: Optional[str] = None


class ScoringWeightsBody(BaseModel):
    problem_clarity: float = 1.0
    market_size: float = 1.5
    willingness_to_pay: float = 2.0
    competition_gap: float = 1.5
    technical_feasibility: float = 1.0
    distribution_clarity: float = 1.5
    trend_momentum: float = 1.0


@router.get("/api/settings")
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


@router.post("/api/settings")
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


@router.post("/api/settings/test")
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


@router.get("/api/settings/models")
def list_provider_models():
    """Fetch available models from the configured LLM provider's API."""
    db = _db()
    settings = get_settings()
    try:
        provider = repository.get_app_setting(db, "llm_provider") or settings.llm_provider
        base_url = repository.get_app_setting(db, "llm_base_url") or settings.llm_base_url
        api_key = repository.get_app_setting(db, "llm_api_key") or settings.llm_api_key

        if provider == "anthropic":
            return {"models": [], "source": "none"}

        url = (base_url.rstrip("/") if base_url else "https://api.openai.com/v1").rstrip("/")
        if not url.endswith("/models"):
            url += "/models"

        headers: dict[str, str] = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        resp = httpx.get(url, headers=headers, timeout=10.0)
        resp.raise_for_status()
        data = resp.json()

        model_ids: list[str] = []
        if "data" in data and isinstance(data["data"], list):
            for m in data["data"]:
                mid = m.get("id", "")
                if mid:
                    model_ids.append(mid)
        elif "models" in data and isinstance(data["models"], list):
            for m in data["models"]:
                name = m.get("name", "")
                if name:
                    model_ids.append(name.split(":")[0] if ":" in name else name)

        model_ids.sort()
        return {"models": model_ids, "source": "api"}
    except Exception as exc:
        return {"models": [], "source": "error", "error": str(exc)}
    finally:
        db.close()


@router.get("/api/settings/scoring-weights")
def get_scoring_weights_api():
    db = _db()
    try:
        return repository.get_scoring_weights(db)
    finally:
        db.close()


@router.put("/api/settings/scoring-weights")
def set_scoring_weights_api(body: ScoringWeightsBody):
    db = _db()
    try:
        weights = body.model_dump()
        repository.set_scoring_weights(db, weights)
        return {"status": "ok", "weights": weights}
    finally:
        db.close()
