"""Fixtures for entity intelligence tests — uses monkeypatching for DB isolation."""
from __future__ import annotations

import os
import tempfile

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """TestClient with an isolated temp database, monkeypatched into _db()."""
    test_db_dir = tempfile.mkdtemp(prefix="niche-radar-test-entities-")
    db_url = f"sqlite:///{test_db_dir}/test.db"
    os.environ["REPORT_OUTPUT_DIR"] = test_db_dir

    from niche_radar.storage.database import get_db as raw_get_db

    def _test_db():
        return raw_get_db(db_url)

    import niche_radar.api.server as server_module
    original_db = server_module._db
    server_module._db = _test_db

    import niche_radar.config
    original_settings = niche_radar.config._settings
    niche_radar.config._settings = None
    os.environ["DATABASE_URL"] = db_url

    yield TestClient(server_module.app)

    server_module._db = original_db
    niche_radar.config._settings = original_settings


@pytest.fixture
def db_url():
    """Return a temp database URL for direct repository tests (not via API)."""
    test_db_dir = tempfile.mkdtemp(prefix="niche-radar-test-repo-")
    db_url = f"sqlite:///{test_db_dir}/test.db"
    os.environ["REPORT_OUTPUT_DIR"] = test_db_dir
    return db_url
