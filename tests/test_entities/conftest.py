"""Fixtures for entity intelligence tests — uses env var + settings reset for DB isolation."""
from __future__ import annotations

import os
import tempfile

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """TestClient with an isolated temp database.

    Sets DATABASE_URL env var and resets the settings singleton so
    _db() picks up the test URL through normal get_settings() flow.
    No monkeypatching needed — the _db() helper in routes/_common.py
    calls get_settings() at call time, which re-reads DATABASE_URL.
    """
    test_db_dir = tempfile.mkdtemp(prefix="niche-radar-test-entities-")
    db_url = f"sqlite:///{test_db_dir}/test.db"
    os.environ["REPORT_OUTPUT_DIR"] = test_db_dir
    os.environ["DATABASE_URL"] = db_url

    import niche_radar.config
    original_settings = niche_radar.config._settings
    niche_radar.config._settings = None

    from niche_radar.api.server import app
    yield TestClient(app)

    niche_radar.config._settings = original_settings


@pytest.fixture
def db_url():
    """Return a temp database URL for direct repository tests (not via API)."""
    test_db_dir = tempfile.mkdtemp(prefix="niche-radar-test-repo-")
    db_url = f"sqlite:///{test_db_dir}/test.db"
    os.environ["REPORT_OUTPUT_DIR"] = test_db_dir
    return db_url
