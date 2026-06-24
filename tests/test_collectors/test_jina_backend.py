"""Tests for the Jina Reader fallback backend and its use in fragile collectors.

All network is mocked (`_http.request` / `requests` are patched) — these run
fully offline, and the opt-in gate keeps the Jina path from making live calls
unless a test explicitly enables it.
"""

from __future__ import annotations

import pytest

from niche_radar.collectors import _http, _jina
from niche_radar.collectors.backends import JinaReaderBackend
from niche_radar.config import Settings


@pytest.fixture
def settings():
    s = Settings()
    s.max_retries = 1  # keep direct-scrape retry loops instant in tests
    return s


# ── opt-in availability ──────────────────────────────────────────────────────

def test_jina_disabled_by_default(monkeypatch, settings):
    monkeypatch.delenv("JINA_READER_ENABLED", raising=False)
    monkeypatch.delenv("JINA_API_KEY", raising=False)
    backend = JinaReaderBackend("g2_reviews", lambda s, db: ["https://x"])
    assert backend.is_available(settings, None) is False


def test_jina_enabled_via_env(monkeypatch, settings):
    monkeypatch.setenv("JINA_READER_ENABLED", "1")
    backend = JinaReaderBackend("g2_reviews", lambda s, db: ["https://x"])
    assert backend.is_available(settings, None) is True


def test_jina_enabled_via_api_key(monkeypatch, settings):
    monkeypatch.delenv("JINA_READER_ENABLED", raising=False)
    monkeypatch.setenv("JINA_API_KEY", "jina-test-key")
    backend = JinaReaderBackend("indie_hackers", lambda s, db: ["https://x"])
    assert backend.is_available(settings, None) is True


def test_is_enabled_never_raises(settings):
    # db that explodes on any use must not break availability checks
    class _Boom:
        def __getattr__(self, _):
            raise RuntimeError("db down")

    assert _jina.is_enabled(settings, _Boom(), "g2_reviews") in (True, False)


# ── page normalization ───────────────────────────────────────────────────────

def test_page_to_items_builds_one_document():
    md = "# Notion is missing a feature\n\nUsers complain about export."
    items = _jina.page_to_items(md, "https://g2.com/products/notion/reviews", "g2_reviews")
    assert len(items) == 1
    it = items[0]
    assert it["title"] == "Notion is missing a feature"
    assert "export" in it["body"]
    assert it["metadata"]["capture"] == "jina_reader"
    assert it["source_id"].startswith("g2_reviews-jina-")


def test_page_to_items_deterministic_id():
    md = "# Heading\n\nbody text"
    a = _jina.page_to_items(md, "https://x/y", "s")[0]["source_id"]
    b = _jina.page_to_items(md, "https://x/y", "s")[0]["source_id"]
    assert a == b


def test_page_to_items_empty_returns_nothing():
    assert _jina.page_to_items("", "https://x", "s") == []
    assert _jina.page_to_items("   \n  ", "https://x", "s") == []


# ── backend fetch semantics ──────────────────────────────────────────────────

def test_fetch_reads_each_url_through_jina(monkeypatch, settings):
    seen = []

    def fake_request(method, url, **kw):
        seen.append(url)
        return "# Page\n\ncaptured content"

    monkeypatch.setattr(_http, "request", fake_request)
    backend = JinaReaderBackend("g2_reviews", lambda s, db: ["https://a", "https://b"])
    items = backend.fetch(settings, None)
    assert len(items) == 2
    assert all(i["metadata"]["capture"] == "jina_reader" for i in items)
    assert seen == ["https://r.jina.ai/https://a", "https://r.jina.ai/https://b"]


def test_fetch_raises_when_all_urls_fail(monkeypatch, settings):
    def boom(*a, **k):
        raise _http.HTTPError("blocked", status_code=403)

    monkeypatch.setattr(_http, "request", boom)
    backend = JinaReaderBackend("g2_reviews", lambda s, db: ["https://a"])
    with pytest.raises(RuntimeError):
        backend.fetch(settings, None)


def test_fetch_returns_partial_on_some_failure(monkeypatch, settings):
    calls = {"n": 0}

    def flaky(method, url, **kw):
        calls["n"] += 1
        if calls["n"] == 1:
            raise _http.HTTPError("blocked", status_code=403)
        return "# ok\n\ncontent"

    monkeypatch.setattr(_http, "request", flaky)
    backend = JinaReaderBackend("s", lambda s, db: ["https://a", "https://b"])
    items = backend.fetch(settings, None)
    assert len(items) == 1  # second URL succeeded; no raise


# ── integration: fragile collectors fall through to Jina when blocked ────────

def test_g2_falls_through_to_jina_when_blocked(monkeypatch, settings):
    from niche_radar.collectors import g2_reviews

    class _Resp:
        status_code = 403
        text = ""

    class _Session:
        def __init__(self):
            self.headers = {}

        def get(self, *a, **k):
            return _Resp()

    monkeypatch.setattr(g2_reviews.requests, "Session", lambda: _Session())
    monkeypatch.setenv("JINA_READER_ENABLED", "1")
    monkeypatch.setattr(_http, "request", lambda *a, **k: "# Notion reviews\n\nmissing export feature")

    result = g2_reviews.G2ReviewsCollector().collect(settings=settings)
    assert result.status == "completed"
    assert result.metadata["active_backend"] == "jina_reader"
    assert result.items[0]["metadata"]["capture"] == "jina_reader"


def test_indie_hackers_falls_through_to_jina_when_blocked(monkeypatch, settings):
    from niche_radar.collectors import indie_hackers

    class _Resp:
        status_code = 403
        text = ""

    monkeypatch.setattr(indie_hackers.requests, "get", lambda *a, **k: _Resp())
    monkeypatch.setenv("JINA_READER_ENABLED", "1")
    monkeypatch.setattr(_http, "request", lambda *a, **k: "# IH products\n\nrevenue-verified products")

    result = indie_hackers.IndieHackersCollector().collect(settings=settings)
    assert result.status == "completed"
    assert result.metadata["active_backend"] == "jina_reader"
    assert result.items[0]["metadata"]["capture"] == "jina_reader"


def test_blocked_without_jina_degrades_not_crashes(monkeypatch, settings):
    from niche_radar.collectors import g2_reviews

    class _Resp:
        status_code = 403
        text = ""

    class _Session:
        def __init__(self):
            self.headers = {}

        def get(self, *a, **k):
            return _Resp()

    monkeypatch.setattr(g2_reviews.requests, "Session", lambda: _Session())
    monkeypatch.delenv("JINA_READER_ENABLED", raising=False)
    monkeypatch.delenv("JINA_API_KEY", raising=False)

    result = g2_reviews.G2ReviewsCollector().collect(settings=settings)
    assert result.status in ("failed", "partial")  # never raises
    names = [b["backend"] for b in result.metadata["backends"]]
    assert "jina_reader" in names  # fallback present in chain, just unavailable
