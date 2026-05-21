"""Tests for the /api/sources endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from niche_radar.api.server import app
from niche_radar.storage.database import get_db
import tempfile, os


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    # Force settings singleton to reload with the test DB
    import niche_radar.config as cfg
    cfg._settings = None
    from niche_radar.config import Settings
    cfg._settings = Settings(database_url=db_url)
    return TestClient(app)


def test_list_sources_returns_all_known(client):
    resp = client.get("/api/sources")
    assert resp.status_code == 200
    data = resp.json()
    slugs = {s["slug"] for s in data}
    # Core original sources must be present
    assert "reddit" in slugs
    assert "hn" in slugs
    # New P1 sources
    assert "product_hunt" in slugs
    assert "stack_overflow" in slugs


def test_get_source_returns_schema(client):
    resp = client.get("/api/sources/reddit")
    assert resp.status_code == 200
    data = resp.json()
    assert data["slug"] == "reddit"
    assert isinstance(data["schema"], list)
    keys = {f["key"] for f in data["schema"]}
    assert "client_id" in keys
    assert "search_queries" in keys


def test_get_unknown_source_returns_404(client):
    resp = client.get("/api/sources/nonexistent")
    assert resp.status_code == 404


def test_post_source_sets_credentials(client):
    resp = client.post("/api/sources/reddit", json={"credentials": {"client_id": "my-id", "search_queries": '["test"]'}})
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    # Verify persisted by re-reading
    get_resp = client.get("/api/sources/reddit")
    creds = get_resp.json()["credentials_set"]
    # client_id is not secret so it should appear as-is
    assert creds.get("client_id") == "my-id"
    # client_secret is secret so it would be masked if set
    assert creds.get("search_queries") == '["test"]'


def test_post_source_delete_credential(client):
    # Set then delete
    client.post("/api/sources/reddit", json={"credentials": {"user_agent": "temp"}})
    client.post("/api/sources/reddit", json={"credentials": {"user_agent": None}})
    get_resp = client.get("/api/sources/reddit")
    creds = get_resp.json()["credentials_set"]
    assert "user_agent" not in creds


def test_post_source_unknown_returns_404(client):
    resp = client.post("/api/sources/bogus", json={"credentials": {"k": "v"}})
    assert resp.status_code == 404


def test_test_source_endpoint_exists(client):
    # Just check the endpoint resolves without a 404 (may return ok=False for unconfigured sources)
    resp = client.post("/api/sources/stack_overflow/test")
    assert resp.status_code == 200
    data = resp.json()
    assert "ok" in data
    assert "message" in data
