"""Tests for the pluggable web-search backend chain (Phase 4)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from niche_radar.agents import web_search
from niche_radar.agents.web_search import (
    BraveBackend,
    ChainSearcher,
    SearchResult,
    SerperBackend,
    get_searcher,
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("BRAVE_API_KEY", raising=False)
    monkeypatch.delenv("SERPER_API_KEY", raising=False)


class _StubFallback:
    def __init__(self, results):
        self.results = results
        self.called = False

    def search(self, query):
        self.called = True
        return self.results


def test_backends_unavailable_without_keys():
    assert BraveBackend().is_available() is False
    assert SerperBackend().is_available() is False


def test_chain_uses_fallback_when_no_backends():
    fb = _StubFallback([SearchResult("t", "https://x", "s")])
    searcher = ChainSearcher([], fallback=fb)
    out = searcher.search("anything")
    assert fb.called
    assert out[0].url == "https://x"


def test_brave_parsing(monkeypatch):
    monkeypatch.setenv("BRAVE_API_KEY", "brave-key")
    fake = {"web": {"results": [
        {"title": "Result A", "url": "https://a.com", "description": "snippet a"},
        {"title": "no url", "url": "", "description": "skip"},
    ]}}
    with patch.object(web_search._http, "get_json", return_value=fake):
        out = BraveBackend().search("query")
    assert len(out) == 1
    assert out[0].url == "https://a.com"
    assert out[0].snippet == "snippet a"


def test_serper_parsing(monkeypatch):
    monkeypatch.setenv("SERPER_API_KEY", "serper-key")
    fake = {"organic": [
        {"title": "R", "link": "https://b.com", "snippet": "snip b"},
    ]}
    with patch.object(web_search._http, "post_json", return_value=fake):
        out = SerperBackend().search("query")
    assert out[0].url == "https://b.com"


def test_chain_prefers_api_then_falls_back_on_empty(monkeypatch):
    monkeypatch.setenv("BRAVE_API_KEY", "brave-key")
    fb = _StubFallback([SearchResult("fb", "https://fallback", "s")])
    # Brave available but returns nothing → should fall through to DDG fallback.
    with patch.object(BraveBackend, "search", return_value=[]):
        searcher = get_searcher(ddg_fallback=fb)
        out = searcher.search("q")
    assert fb.called
    assert out[0].url == "https://fallback"


def test_chain_backend_error_falls_back(monkeypatch):
    monkeypatch.setenv("SERPER_API_KEY", "serper-key")
    fb = _StubFallback([SearchResult("fb", "https://fallback", "s")])
    with patch.object(SerperBackend, "search", side_effect=RuntimeError("boom")):
        searcher = get_searcher(ddg_fallback=fb)
        out = searcher.search("q")
    assert fb.called
    assert out[0].url == "https://fallback"


def test_active_backend_reports_priority(monkeypatch):
    monkeypatch.setenv("SERPER_API_KEY", "serper-key")
    assert get_searcher().active_backend == "serper"
    monkeypatch.setenv("BRAVE_API_KEY", "brave-key")
    assert get_searcher().active_backend == "brave"  # brave first in priority
