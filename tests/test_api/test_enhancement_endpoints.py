"""Tests for Phase 4+5 API endpoints: shortlist, filters, validate, momentum, weekly digest."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from niche_radar.api.server import app
from niche_radar.storage.database import get_db
from niche_radar.storage.repository import insert_collection_run, upsert_niche_candidate, upsert_raw_item


@pytest.fixture
def client_with_db(tmp_path, monkeypatch):
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    import niche_radar.config as cfg
    cfg._settings = None
    from niche_radar.config import Settings
    cfg._settings = Settings(database_url=db_url)
    db = get_db(db_url)
    return TestClient(app), db


def _seed_niche(db, keyword="test-niche"):
    niche_id = upsert_niche_candidate(
        db, keyword, ["kw1", "kw2"], 75.0, "good reasoning",
        tool_concept="A tool that does X", target_audience="developers",
        build_complexity=2, monetization="subscription: $29/mo", pain_points=[],
    )
    return niche_id


def test_shortlist_star_and_list(client_with_db):
    client, db = client_with_db
    niche_id = _seed_niche(db)

    resp = client.post(f"/api/niches/{niche_id}/shortlist", json={"note": "promising"})
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    resp2 = client.get("/api/shortlist")
    assert resp2.status_code == 200
    data = resp2.json()
    assert len(data) == 1
    assert data[0]["id"] == niche_id
    assert data[0]["note"] == "promising"


def test_shortlist_unstar(client_with_db):
    client, db = client_with_db
    niche_id = _seed_niche(db)

    client.post(f"/api/niches/{niche_id}/shortlist")
    resp = client.delete(f"/api/niches/{niche_id}/shortlist")
    assert resp.status_code == 200

    resp2 = client.get("/api/shortlist")
    assert resp2.json() == []


def test_star_unknown_niche_returns_404(client_with_db):
    client, db = client_with_db
    resp = client.post("/api/niches/nonexistent-id/shortlist", json={"note": ""})
    assert resp.status_code == 404


def test_niche_detail_includes_is_shortlisted(client_with_db):
    client, db = client_with_db
    niche_id = _seed_niche(db)

    resp = client.get(f"/api/niches/{niche_id}")
    assert resp.status_code == 200
    niche_data = resp.json()["niche"]
    assert "is_shortlisted" in niche_data
    assert niche_data["is_shortlisted"] is False

    client.post(f"/api/niches/{niche_id}/shortlist")
    resp2 = client.get(f"/api/niches/{niche_id}")
    assert resp2.json()["niche"]["is_shortlisted"] is True


def test_niches_list_filter_by_min_score(client_with_db):
    client, db = client_with_db
    _seed_niche(db, "high-score")
    low_id = upsert_niche_candidate(
        db, "low-score", [], 30.0, "r", tool_concept="t", target_audience="a",
        build_complexity=3, monetization="m", pain_points=[],
    )
    resp = client.get("/api/niches?min_score=60")
    keywords = {n["keyword"] for n in resp.json()}
    assert "high-score" in keywords
    assert "low-score" not in keywords


def test_niches_list_filter_by_trend(client_with_db):
    client, db = client_with_db
    niche_id = _seed_niche(db, "growing-one")
    db.execute(
        "UPDATE niche_candidates SET momentum_label='growing' WHERE id=?", (niche_id,)
    )
    db.commit()
    resp = client.get("/api/niches?trend=growing")
    keywords = {n["keyword"] for n in resp.json()}
    assert "growing-one" in keywords


def test_niches_list_csv_format(client_with_db):
    client, db = client_with_db
    _seed_niche(db)
    resp = client.get("/api/niches?format=csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers.get("content-type", "")
    assert "keyword" in resp.text


def test_momentum_endpoint_returns_data(client_with_db):
    client, db = client_with_db
    niche_id = _seed_niche(db)
    resp = client.get(f"/api/niches/{niche_id}/momentum")
    assert resp.status_code == 200
    data = resp.json()
    assert "this_week" in data
    assert "label" in data
    assert data["label"] in ("growing", "stable", "declining")


def test_validate_endpoint_returns_verdict(client_with_db, monkeypatch):
    client, db = client_with_db
    niche_id = _seed_niche(db)

    # Patch DDG so it doesn't make real HTTP calls
    from niche_radar.agents.web_validate import _cached_search
    monkeypatch.setattr("niche_radar.agents.web_validate._cached_search", lambda q: ())

    resp = client.post(f"/api/niches/{niche_id}/validate")
    assert resp.status_code == 200
    data = resp.json()
    assert "verdict" in data
    assert data["verdict"] in ("validated_gap", "crowded_market", "expensive_incumbents", "unclear")
