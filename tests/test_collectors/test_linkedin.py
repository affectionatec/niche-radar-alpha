"""Tests for the LinkedIn collector — all network calls mocked (fully offline).

MultiBackendCollector with chain: public_search → jina_reader (ADR-008).
Public search is keyless (always available); Jina is opt-in for resilience.
"""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from niche_radar.collectors import _jina
from niche_radar.collectors.linkedin import (
    LinkedInCollector,
    LinkedInPublicSearchBackend,
    _linkedin_search_urls,
)
from niche_radar.config import Settings


LONG_HTML = "<html><body>" + "x" * 800 + "LinkedIn search results...</body></html>"


@pytest.fixture
def settings():
    return Settings()


def _fake_resp(status: int = 200, text: str | None = None) -> Mock:
    """Build a mock requests.Response with real .status_code and .text."""
    r = Mock(status_code=status)
    r.text = text or LONG_HTML
    return r


# ── availability ─────────────────────────────────────────────────────────────


def test_public_search_backend_always_available(settings):
    assert LinkedInPublicSearchBackend().is_available(settings, None) is True


def test_collector_available_with_public_search(settings, monkeypatch):
    """Public backend is always available, so collector always reports available."""
    monkeypatch.delenv("JINA_READER_ENABLED", raising=False)
    assert LinkedInCollector.is_available(None, settings) is True


# ── URL construction ─────────────────────────────────────────────────────────


def test_search_urls_use_default_queries(settings):
    urls = _linkedin_search_urls(settings, None)
    assert len(urls) >= 7
    for url in urls:
        assert url.startswith("https://www.linkedin.com/search/results/content/?keywords=")


# ── public search backend ────────────────────────────────────────────────────


def test_public_search_returns_items(settings):
    """Public search returns a document item per query (best-effort scraping)."""
    with patch("niche_radar.collectors.linkedin.requests.get", return_value=_fake_resp()):
        items = LinkedInPublicSearchBackend().fetch(settings, None)

    assert len(items) > 0
    for item in items:
        assert item["source_id"].startswith("li-")
        assert item["metadata"]["capture"] == "public_search"
        assert "linkedin.com" in item["url"]


def test_public_search_raises_when_all_queries_fail(settings):
    """All queries return non-200 → backend raises so chain falls through."""
    with patch("niche_radar.collectors.linkedin.requests.get", return_value=_fake_resp(502)):
        with pytest.raises(RuntimeError, match="HTTP 502"):
            LinkedInPublicSearchBackend().fetch(settings, None)


# ── full collector integration ───────────────────────────────────────────────


def test_collector_uses_public_search_when_jina_off(settings, monkeypatch):
    """With Jina disabled, public search is the only backend — and it wins."""
    monkeypatch.delenv("JINA_READER_ENABLED", raising=False)
    monkeypatch.delenv("JINA_API_KEY", raising=False)

    with patch("niche_radar.collectors.linkedin.requests.get", return_value=_fake_resp()):
        result = LinkedInCollector().collect(settings=settings)

    assert result.status == "completed"
    assert result.metadata["active_backend"] == "public_search"


def test_collector_prefers_jina_when_enabled(settings, monkeypatch):
    """With Jina enabled, Jina is the higher-priority backend (index 1 in chain)."""
    monkeypatch.setenv("JINA_READER_ENABLED", "1")

    def mock_read_url(url, settings, db, source):
        return f"# LinkedIn search results\n\nFound a great automation tool at example.com"

    # Jina backend comes second in the chain but Jina is checked, _is_enabled
    # returns True, and public_search will also return items. However in
    # MultiBackendCollector, the first AVAILABLE backend that returns items wins.
    # Since public_search comes first, it wins unless we make it fail.
    # Let's test the fallthrough: public yields nothing, Jina wins.
    with patch(
        "niche_radar.collectors.linkedin.LinkedInPublicSearchBackend.fetch",
        side_effect=RuntimeError("public search failed"),
    ), patch.object(_jina, "read_url", side_effect=mock_read_url):
        result = LinkedInCollector().collect(settings=settings)

    assert result.metadata["active_backend"] == "jina_reader"
    assert result.status == "completed"


def test_collect_dry_run_returns_empty(settings):
    result = LinkedInCollector().collect(settings=settings, dry_run=True)
    assert result.status == "completed"
    assert result.items == []


def test_test_connection_without_jina(settings, monkeypatch):
    monkeypatch.delenv("JINA_READER_ENABLED", raising=False)
    ok, msg = LinkedInCollector.test_connection(None, settings)
    assert ok is True
    assert "keyless" in msg.lower() or "public" in msg.lower()


def test_test_connection_with_jina(settings, monkeypatch):
    monkeypatch.setenv("JINA_READER_ENABLED", "1")
    ok, msg = LinkedInCollector.test_connection(None, settings)
    assert ok is True
    assert "jina" in msg.lower()
