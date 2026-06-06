"""Tests for pipeline API endpoints."""
from __future__ import annotations

import os
import tempfile

# Point the app at an isolated temp database BEFORE importing the server, so the
# module-level `app` and its dependencies never touch the production sqlite file
# that Docker mounts via ./data:/app/data.
_TEST_DB_DIR = tempfile.mkdtemp(prefix="niche-radar-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB_DIR}/test.db"
os.environ["REPORT_OUTPUT_DIR"] = _TEST_DB_DIR

from fastapi.testclient import TestClient  # noqa: E402

# Reset the cached singleton so the env vars above take effect for this test process.
import niche_radar.config  # noqa: E402

niche_radar.config._settings = None

from niche_radar.api.server import app  # noqa: E402

client = TestClient(app)


def test_post_collect_returns_job():
    resp = client.post("/api/pipeline/collect")
    assert resp.status_code == 200
    data = resp.json()
    assert "job_id" in data
    assert data["status"] in ("pending", "running")


def test_post_collect_with_source():
    resp = client.post("/api/pipeline/collect?source=reddit")
    assert resp.status_code == 200
    assert "job_id" in resp.json()


def test_post_analyze_returns_job():
    resp = client.post("/api/pipeline/analyze")
    assert resp.status_code == 200
    assert resp.json()["status"] in ("pending", "running")


def test_post_report_returns_job():
    resp = client.post("/api/pipeline/report")
    assert resp.status_code == 200
    assert resp.json()["status"] in ("pending", "running")


def test_post_run_all_returns_job():
    resp = client.post("/api/pipeline/run-all")
    assert resp.status_code == 200
    assert resp.json()["status"] in ("pending", "running")


def test_get_jobs_returns_list():
    client.post("/api/pipeline/analyze")
    resp = client.get("/api/pipeline/jobs")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_get_job_logs_existing():
    r = client.post("/api/pipeline/collect")
    job_id = r.json()["job_id"]
    resp = client.get(f"/api/pipeline/jobs/{job_id}/logs")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == job_id
    assert "logs" in data
    assert "status" in data


def test_get_job_logs_missing_returns_404():
    resp = client.get("/api/pipeline/jobs/does-not-exist/logs")
    assert resp.status_code == 404


def test_get_report_missing_returns_404(tmp_path, monkeypatch):
    from niche_radar.config import Settings
    monkeypatch.setattr(
        "niche_radar.config.get_settings",
        lambda: Settings(report_output_dir=str(tmp_path)),
    )
    resp = client.get("/api/reports/nonexistent.md")
    assert resp.status_code == 404


def test_get_report_content_returns_text(tmp_path, monkeypatch):
    from niche_radar.config import Settings
    report_file = tmp_path / "test_report.md"
    report_file.write_text("# Test Report\nSome content")
    monkeypatch.setattr(
        "niche_radar.config.get_settings",
        lambda: Settings(report_output_dir=str(tmp_path)),
    )
    resp = client.get("/api/reports/test_report.md")
    assert resp.status_code == 200
    assert resp.json()["content"] == "# Test Report\nSome content"


def test_get_report_path_traversal_rejected(tmp_path, monkeypatch):
    from niche_radar.config import Settings
    monkeypatch.setattr(
        "niche_radar.config.get_settings",
        lambda: Settings(report_output_dir=str(tmp_path)),
    )
    resp = client.get("/api/reports/../../etc/passwd")
    assert resp.status_code in (403, 404, 422)


def test_get_settings_returns_config():
    resp = client.get("/api/settings")
    assert resp.status_code == 200
    data = resp.json()
    assert "llm_provider" in data
    assert "llm_api_key_set" in data


def test_post_settings_saves_model():
    resp = client.post("/api/settings", json={"llm_model": "gpt-4o"})
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_post_settings_test_returns_result():
    resp = client.post("/api/settings/test")
    assert resp.status_code == 200
    data = resp.json()
    assert "ok" in data
    assert "message" in data
    assert isinstance(data["ok"], bool)
