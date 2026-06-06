"""Tests for GitHub Trending collector — parsing helpers and dry-run path."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from niche_radar.collectors.github_trending import (
    GitHubTrendingCollector,
    _to_int,
)
from niche_radar.config import Settings


@pytest.fixture
def settings():
    return Settings()


def test_to_int_extracts_digits():
    assert _to_int("1,234 stars today") == 1234
    assert _to_int("56") == 56
    assert _to_int(None) == 0
    assert _to_int("no digits") == 0
    assert _to_int("") == 0


def test_collect_dry_run_returns_empty(settings):
    result = GitHubTrendingCollector().collect(settings=settings, dry_run=True)
    assert result.source == "github"
    assert result.status == "completed"
    assert result.items_collected == 0
    assert result.items == []
    assert result.duration_seconds >= 0


def test_collect_returns_github_source_name(settings):
    """Collect dry-run returns pending source_name=github."""
    result = GitHubTrendingCollector().collect(settings=settings, dry_run=True)
    assert result.source == "github"
    assert result.status == "completed"


def test_test_connection_requires_real_db(tmp_path):
    """test_connection needs a real DB to check for stored credentials."""
    from niche_radar.storage.database import get_db
    db = get_db(f"sqlite:///{tmp_path / 'test.db'}")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    with patch("requests.get", return_value=mock_resp):
        ok, msg = GitHubTrendingCollector.test_connection(db, Settings())
    assert ok is True
    assert "reachable" in msg


def test_test_connection_unreachable(tmp_path):
    from niche_radar.storage.database import get_db
    db = get_db(f"sqlite:///{tmp_path / 'test.db'}")

    mock_resp = MagicMock()
    mock_resp.status_code = 503
    with patch("requests.get", return_value=mock_resp):
        ok, msg = GitHubTrendingCollector.test_connection(db, Settings())
    assert ok is False
