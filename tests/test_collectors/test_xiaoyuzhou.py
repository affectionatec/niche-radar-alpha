"""Tests for the Xiaoyuzhou collector — all network calls mocked (fully offline).

MultiBackendCollector wrapping a single composed JinaReaderBackend (ADR-009).
Jina-gated (opt-in only) — same pattern as Xiaohongshu (ADR-007).
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from niche_radar.collectors import _jina
from niche_radar.collectors.xiaoyuzhou import (
    XiaoyuzhouCollector,
    _xiaoyuzhou_urls,
)
from niche_radar.config import Settings


@pytest.fixture
def settings():
    return Settings()


# ── URL construction ─────────────────────────────────────────────────────────


def test_urls_include_homepage_and_search_queries(settings, monkeypatch):
    monkeypatch.delenv("JINA_READER_ENABLED", raising=False)
    urls = _xiaoyuzhou_urls(settings, None)
    assert urls[0] == "https://www.xiaoyuzhoufm.com"
    assert len(urls) >= 9  # homepage + 8 default queries
    for url in urls[1:]:
        assert "/search?q=" in url


# ── collector integration ────────────────────────────────────────────────────


def test_collector_skips_when_jina_disabled(settings, monkeypatch):
    monkeypatch.delenv("JINA_READER_ENABLED", raising=False)
    monkeypatch.delenv("JINA_API_KEY", raising=False)
    assert XiaoyuzhouCollector.is_available(None, settings) is False


def test_collector_available_when_jina_enabled(settings, monkeypatch):
    monkeypatch.setenv("JINA_READER_ENABLED", "1")
    assert XiaoyuzhouCollector.is_available(None, settings) is True


def test_collect_returns_items_via_jina_backend(settings, monkeypatch):
    monkeypatch.setenv("JINA_READER_ENABLED", "1")

    def mock_read_url(url, settings, db, source):
        return f"# 小宇宙 podcast discovery\n\n推荐播客：独立开发者 survival guide\n\nShow notes: 如何从0到1做SaaS产品"

    with patch.object(_jina, "read_url", side_effect=mock_read_url):
        result = XiaoyuzhouCollector().collect(settings=settings)

    assert result.status == "completed"
    assert result.metadata["active_backend"] == "jina_reader"
    assert len(result.items) > 0
    for item in result.items:
        assert item["metadata"]["capture"] == "jina_reader"
        assert "xiaoyuzhoufm.com" in item["url"]


def test_collect_degrades_when_all_urls_fail(settings, monkeypatch):
    monkeypatch.setenv("JINA_READER_ENABLED", "1")

    def mock_read_url(url, settings, db, source):
        raise RuntimeError("jina network error")

    with patch.object(_jina, "read_url", side_effect=mock_read_url):
        result = XiaoyuzhouCollector().collect(settings=settings)

    assert result.status in ("partial", "failed")


def test_collect_dry_run_returns_empty(settings):
    result = XiaoyuzhouCollector().collect(settings=settings, dry_run=True)
    assert result.status == "completed"
    assert result.items == []


def test_test_connection_when_enabled(settings, monkeypatch):
    monkeypatch.setenv("JINA_READER_ENABLED", "1")
    ok, msg = XiaoyuzhouCollector.test_connection(None, settings)
    assert ok is True
    assert "enabled" in msg.lower() or "jina" in msg.lower()


def test_test_connection_when_disabled(settings, monkeypatch):
    monkeypatch.delenv("JINA_READER_ENABLED", raising=False)
    monkeypatch.delenv("JINA_API_KEY", raising=False)
    ok, msg = XiaoyuzhouCollector.test_connection(None, settings)
    assert ok is True
    assert "skip" in msg.lower() or "not enabled" in msg.lower()
