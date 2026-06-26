"""Tests for the V2EX collector — all network calls are mocked (fully offline)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from niche_radar.collectors._http import HTTPError
from niche_radar.collectors.v2ex import (
    V2exCollector,
    V2exV1ApiBackend,
    V2exV2ApiBackend,
    _normalize,
)
from niche_radar.config import Settings


@pytest.fixture
def s_no_token():
    s = Settings()
    s.v2ex_api_token = ""
    return s


@pytest.fixture
def s_with_token():
    s = Settings()
    s.v2ex_api_token = "tok-test-123"
    return s


# ── backend availability ────────────────────────────────────────────────────


def test_v2_backend_unavailable_without_token(s_no_token):
    assert V2exV2ApiBackend().is_available(s_no_token, None) is False


def test_v2_backend_available_with_token(s_with_token):
    assert V2exV2ApiBackend().is_available(s_with_token, None) is True


def test_v1_backend_always_available(s_no_token):
    assert V2exV1ApiBackend().is_available(s_no_token, None) is True


# ── _normalize helper ───────────────────────────────────────────────────────


def test_normalize_returns_item_for_fresh_topic():
    from datetime import datetime, timezone

    topic = {
        "id": 999,
        "title": "How do I automate this workflow?",
        "content": "I wish there was a tool…",
        "replies": 5,
        "created": int(datetime.now(timezone.utc).timestamp()) - 3600,
        "url": "https://www.v2ex.com/t/999",
        "member": {"username": "alice"},
        "node": {"name": "qna", "title": "Q & A"},
    }
    from datetime import timedelta

    cutoff = datetime.now(timezone.utc) - timedelta(hours=72)
    result = _normalize(topic, cutoff)
    assert "999" in result
    item = result["999"]
    assert item["source_id"] == "999"
    assert item["title"] == "How do I automate this workflow?"
    assert item["metadata"]["node"] == "qna"
    assert item["metadata"]["author"] == "alice"


def test_normalize_drops_stale_topic():
    from datetime import datetime, timedelta, timezone

    topic = {
        "id": 1,
        "title": "Old post",
        "created": int((datetime.now(timezone.utc) - timedelta(hours=200)).timestamp()),
        "replies": 0,
    }
    cutoff = datetime.now(timezone.utc) - timedelta(hours=72)
    assert _normalize(topic, cutoff) == {}


def test_normalize_ignores_missing_id():
    from datetime import datetime, timedelta, timezone

    cutoff = datetime.now(timezone.utc) - timedelta(hours=72)
    assert _normalize({"title": "no id"}, cutoff) == {}


# ── v1 backend fetch ────────────────────────────────────────────────────────


def _make_topic(tid: int):
    import time

    return {
        "id": tid,
        "title": f"I need a tool for problem {tid}",
        "content": "help",
        "replies": tid,
        "created": int(time.time()) - 3600,
        "url": f"https://www.v2ex.com/t/{tid}",
        "member": {"username": "u"},
        "node": {"name": "startup"},
    }


def test_v1_backend_fetches_hot_and_latest(s_no_token):
    responses = {
        "https://www.v2ex.com/api/topics/hot.json": [_make_topic(1), _make_topic(2)],
        "https://www.v2ex.com/api/topics/latest.json": [_make_topic(3)],
    }

    def mock_get_json(url, **kwargs):
        return responses[url]

    with patch("niche_radar.collectors.v2ex.get_json", side_effect=mock_get_json):
        items = V2exV1ApiBackend().fetch(s_no_token, None)

    assert len(items) == 3
    ids = {i["source_id"] for i in items}
    assert ids == {"1", "2", "3"}


def test_v1_backend_raises_when_both_endpoints_fail(s_no_token):
    with patch("niche_radar.collectors.v2ex.get_json", side_effect=HTTPError("network fail", 503)):
        with pytest.raises(RuntimeError, match="network fail"):
            V2exV1ApiBackend().fetch(s_no_token, None)


# ── v2 backend fetch ────────────────────────────────────────────────────────


def test_v2_backend_queries_configured_nodes(s_with_token):
    called_nodes: list[str] = []

    def mock_get_json(url, **kwargs):
        node = url.split("/nodes/")[1].split("/")[0]
        called_nodes.append(node)
        return {"result": [_make_topic(10)], "success": True}

    with patch("niche_radar.collectors.v2ex.get_json", side_effect=mock_get_json):
        items = V2exV2ApiBackend().fetch(s_with_token, None)

    assert "startup" in called_nodes
    assert "qna" in called_nodes
    assert items  # deduped, but at least one


# ── full collector integration ──────────────────────────────────────────────


def test_collector_uses_v1_without_token(s_no_token):
    with patch(
        "niche_radar.collectors.v2ex.get_json",
        side_effect=lambda url, **kw: [_make_topic(99)] if "hot" in url else [],
    ):
        result = V2exCollector().collect(settings=s_no_token)

    assert result.status == "completed"
    assert result.metadata["active_backend"] == "v1_api"
    assert result.items[0]["source_id"] == "99"


def test_collector_prefers_v2_with_token(s_with_token):
    with patch(
        "niche_radar.collectors.v2ex.get_json",
        return_value={"result": [_make_topic(77)], "success": True},
    ):
        result = V2exCollector().collect(settings=s_with_token)

    assert result.status == "completed"
    assert result.metadata["active_backend"] == "v2_api"
    assert result.items[0]["source_id"] == "77"


def test_collector_falls_through_to_v1_when_v2_fails(s_with_token):
    call_count = {"n": 0}

    def flaky(url, **kw):
        if "/v2/nodes/" in url:
            raise HTTPError("v2 api down", 500)
        call_count["n"] += 1
        return [_make_topic(55)]

    with patch("niche_radar.collectors.v2ex.get_json", side_effect=flaky):
        result = V2exCollector().collect(settings=s_with_token)

    assert result.metadata["active_backend"] == "v1_api"
    assert call_count["n"] > 0


def test_collector_test_connection_no_token(s_no_token):
    ok, msg = V2exCollector.test_connection(None, s_no_token)
    assert ok is True
    assert "keyless" in msg.lower() or "v1" in msg.lower()


def test_collector_test_connection_with_token(s_with_token):
    ok, msg = V2exCollector.test_connection(None, s_with_token)
    assert ok is True
    assert "v2" in msg.lower()
