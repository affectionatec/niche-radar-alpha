"""Tests for the Phase 0 foundations: resilient HTTP + MultiBackendCollector."""

from __future__ import annotations

import pytest
import requests

from niche_radar.collectors import _http
from niche_radar.collectors.multi_backend import MultiBackendCollector, SourceBackend
from niche_radar.config import Settings


@pytest.fixture
def settings():
    return Settings()


# ── _http secret redaction ──────────────────────────────────────────────────

def test_redact_masks_secrets():
    url = "https://api.example.com/v1/search?q=hi&api_key=sk-secret&token=abc123&page=2"
    masked = _http.redact(url)
    assert "sk-secret" not in masked
    assert "abc123" not in masked
    assert "api_key=***" in masked
    assert "token=***" in masked
    assert "page=2" in masked  # non-secret params survive


def test_request_returns_json(monkeypatch):
    class FakeResp:
        status_code = 200
        content = b"{}"
        text = '{"hello": "world"}'
        headers: dict = {}

        def json(self):
            return {"hello": "world"}

    monkeypatch.setattr(requests, "request", lambda *a, **k: FakeResp())
    assert _http.get_json("https://x/y") == {"hello": "world"}


def test_request_raises_on_non_retryable_4xx(monkeypatch):
    class FakeResp:
        status_code = 401
        content = b"nope"
        text = "unauthorized"
        headers: dict = {}

    monkeypatch.setattr(requests, "request", lambda *a, **k: FakeResp())
    with pytest.raises(_http.HTTPError) as exc:
        _http.get_json("https://x/y", retries=2)
    assert exc.value.status_code == 401


def test_request_caps_429_retries(monkeypatch):
    calls = {"n": 0}

    class FakeResp:
        status_code = 429
        content = b""
        text = "slow down"
        headers = {"Retry-After": "0"}

    def fake(*a, **k):
        calls["n"] += 1
        return FakeResp()

    monkeypatch.setattr(requests, "request", fake)
    monkeypatch.setattr(_http.time, "sleep", lambda *_: None)
    with pytest.raises(_http.HTTPError) as exc:
        _http.get_json("https://x/y", max_429_retries=2)
    assert exc.value.status_code == 429
    # initial + 2 retries = 3 calls, then it gives up
    assert calls["n"] == 3


# ── MultiBackendCollector chain ─────────────────────────────────────────────

class _Backend(SourceBackend):
    def __init__(self, name, available=True, items=None, raises=False):
        self.name = name
        self._available = available
        self._items = items or []
        self._raises = raises

    def is_available(self, settings, db):
        return self._available

    def fetch(self, settings, db):
        if self._raises:
            raise RuntimeError("boom")
        return self._items


def _collector(backends):
    class _C(MultiBackendCollector):
        source_name = "fake"

        def build_backends(self):
            return backends

    return _C()


def test_first_available_backend_with_items_wins(settings):
    primary = _Backend("primary", items=[{"source_id": "1", "title": "a"}])
    secondary = _Backend("secondary", items=[{"source_id": "2", "title": "b"}])
    result = _collector([primary, secondary]).collect(settings=settings)
    assert result.status == "completed"
    assert [i["source_id"] for i in result.items] == ["1"]
    assert result.metadata["active_backend"] == "primary"
    assert result.metadata["backends"][0]["status"] == "ok"


def test_falls_through_unavailable_and_empty(settings):
    chain = [
        _Backend("unavailable", available=False),
        _Backend("empty", items=[]),
        _Backend("winner", items=[{"source_id": "3", "title": "c"}]),
    ]
    result = _collector(chain).collect(settings=settings)
    assert result.status == "completed"
    assert result.items[0]["source_id"] == "3"


def test_backend_error_does_not_break_chain(settings):
    chain = [
        _Backend("explodes", raises=True),
        _Backend("winner", items=[{"source_id": "4", "title": "d"}]),
    ]
    result = _collector(chain).collect(settings=settings)
    assert result.status == "completed"
    assert result.items[0]["source_id"] == "4"
    assert result.error_message and "explodes" in result.error_message


def test_all_unavailable_is_failed(settings):
    chain = [_Backend("a", available=False), _Backend("b", available=False)]
    result = _collector(chain).collect(settings=settings)
    assert result.status == "failed"
    assert "no backend available" in result.error_message


def test_available_but_empty_is_partial(settings):
    chain = [_Backend("a", items=[]), _Backend("b", items=[])]
    result = _collector(chain).collect(settings=settings)
    assert result.status == "partial"


def test_is_available_reflects_chain(settings):
    class _C(MultiBackendCollector):
        source_name = "fake"

        def build_backends(self):
            return [_Backend("a", available=False), _Backend("b", available=True)]

    assert _C.is_available(None, settings) is True

    class _D(MultiBackendCollector):
        source_name = "fake2"

        def build_backends(self):
            return [_Backend("a", available=False)]

    assert _D.is_available(None, settings) is False


def test_dry_run_short_circuits(settings):
    primary = _Backend("primary", items=[{"source_id": "1"}])
    result = _collector([primary]).collect(settings=settings, dry_run=True)
    assert result.items_collected == 0
