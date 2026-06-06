"""Tests for GitHub Trending collector — parsing helpers and dry-run path."""
from __future__ import annotations

from unittest.mock import patch, MagicMock

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


def test_collect_scrapes_trending_page(settings):
    """The collector scrapes github.com/trending HTML."""
    html = """<html><body>
    <article class="Box-row">
      <h2><a href="/owner/repo">owner / repo</a></h2>
      <p>A test repository description.</p>
      <span>123 stars today</span>
    </article>
    </body></html>"""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = html

    with patch("requests.get", return_value=mock_response):
        with patch("niche_radar.collectors.github_trending.BeautifulSoup") as mock_bs:
            # We need to provide a functional BS mock
            from bs4 import BeautifulSoup
            mock_bs.side_effect = lambda html, parser: BeautifulSoup(html, parser)
            result = GitHubTrendingCollector().collect(settings=settings, dry_run=False)

    assert result.source == "github"
    assert result.items_collected >= 1


def test_test_connection_reachable():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    with patch("requests.get", return_value=mock_resp):
        ok, msg = GitHubTrendingCollector.test_connection(None, Settings())
    assert ok is True
    assert "reachable" in msg


def test_test_connection_unreachable():
    mock_resp = MagicMock()
    mock_resp.status_code = 503
    with patch("requests.get", return_value=mock_resp):
        ok, msg = GitHubTrendingCollector.test_connection(None, Settings())
    assert ok is False
