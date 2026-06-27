"""Tests for the Xiaohongshu collector — all network calls mocked (fully offline).

The collector is a MultiBackendCollector wrapping a single composed
JinaReaderBackend (ADR-007).  The Jina tier is opt-in only — no surprise
outbound calls because is_enabled returns False by default.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from niche_radar.collectors import _jina
from niche_radar.collectors.xiaohongshu import (
    XiaohongshuCollector,
    _xhs_search_urls,
)
from niche_radar.config import Settings


@pytest.fixture
def settings():
    return Settings()


# ── URL construction ─────────────────────────────────────────────────────────


def test_search_urls_use_default_queries(settings, monkeypatch):
    monkeypatch.delenv("JINA_READER_ENABLED", raising=False)
    urls = _xhs_search_urls(settings, None)
    assert len(urls) >= 8
    for url in urls:
        assert url.startswith("https://www.xiaohongshu.com/search_result?keyword=")


# ── collector integration ────────────────────────────────────────────────────


def test_collector_skips_when_jina_disabled(settings, monkeypatch):
    """Collector is unavailable when Jina is off → source skipped in unattended runs."""
    monkeypatch.delenv("JINA_READER_ENABLED", raising=False)
    monkeypatch.delenv("JINA_API_KEY", raising=False)
    assert XiaohongshuCollector.is_available(None, settings) is False


def test_collector_available_when_jina_enabled(settings, monkeypatch):
    monkeypatch.setenv("JINA_READER_ENABLED", "1")
    assert XiaohongshuCollector.is_available(None, settings) is True


def test_collect_returns_items_via_jina_backend(settings, monkeypatch):
    monkeypatch.setenv("JINA_READER_ENABLED", "1")

    def mock_read_url(url, settings, db, source):
        return f"# 小红书搜索: {url}\n\n发现了一个好用的工具推荐给大家"

    with patch.object(_jina, "read_url", side_effect=mock_read_url):
        result = XiaohongshuCollector().collect(settings=settings)

    assert result.status == "completed"
    assert result.metadata["active_backend"] == "jina_reader"
    assert len(result.items) > 0
    for item in result.items:
        assert item["metadata"]["capture"] == "jina_reader"
        assert "xiaohongshu.com" in item["url"]


def test_collect_degrades_when_jina_fails_on_all_urls(settings, monkeypatch):
    monkeypatch.setenv("JINA_READER_ENABLED", "1")

    def mock_read_url(url, settings, db, source):
        raise RuntimeError("jina network error")

    with patch.object(_jina, "read_url", side_effect=mock_read_url):
        result = XiaohongshuCollector().collect(settings=settings)

    # All backends failed → multi_backend returns failed/partial
    assert result.status in ("partial", "failed")


def test_collect_dry_run_returns_empty(settings):
    result = XiaohongshuCollector().collect(settings=settings, dry_run=True)
    assert result.status == "completed"
    assert result.items == []


def test_test_connection_when_enabled(settings, monkeypatch):
    monkeypatch.setenv("JINA_READER_ENABLED", "1")
    ok, msg = XiaohongshuCollector.test_connection(None, settings)
    assert ok is True
    assert "enabled" in msg.lower() or "jina" in msg.lower()


def test_test_connection_when_disabled(settings, monkeypatch):
    monkeypatch.delenv("JINA_READER_ENABLED", raising=False)
    monkeypatch.delenv("JINA_API_KEY", raising=False)
    ok, msg = XiaohongshuCollector.test_connection(None, settings)
    assert ok is True  # succeeds gracefully — source just skips
    assert "skip" in msg.lower() or "not enabled" in msg.lower()
