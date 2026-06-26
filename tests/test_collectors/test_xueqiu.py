"""Tests for the Xueqiu collector — all network calls are mocked (fully offline)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
import requests

from niche_radar.collectors.xueqiu import XueqiuCollector, _normalize
from niche_radar.config import Settings


@pytest.fixture
def settings():
    s = Settings()
    s.xueqiu_cookie = ""
    return s


@pytest.fixture
def settings_with_cookie():
    s = Settings()
    s.xueqiu_cookie = "test-cookie-xyz"
    return s


# ── availability ────────────────────────────────────────────────────────────


def test_collector_is_always_available(settings):
    assert XueqiuCollector.is_available(None, settings) is True


# ── _normalize helper ───────────────────────────────────────────────────────


def test_normalize_maps_post_to_raw_item():
    import time
    from datetime import datetime, timedelta, timezone

    post = {
        "id": "123456",
        "title": "求推荐一款好用的财务管理工具",
        "text": "找了很久，找不到合适的工具",
        "created_at": int(time.time() * 1000) - 3_600_000,
        "like_count": 12,
        "reply_count": 5,
        "user": {"screen_name": "投资者A"},
    }
    cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
    item = _normalize(post, cutoff)
    assert item is not None
    assert item["source_id"] == "123456"
    assert "财务管理工具" in item["title"]
    assert item["comment_count"] == 5
    assert item["metadata"]["author"] == "投资者A"


def test_normalize_drops_stale_post():
    from datetime import datetime, timedelta, timezone

    post = {
        "id": "1",
        "created_at": int(
            (datetime.now(timezone.utc) - timedelta(hours=200)).timestamp() * 1000
        ),
        "text": "old",
    }
    cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
    assert _normalize(post, cutoff) is None


def test_normalize_uses_text_as_title_when_title_absent():
    import time
    from datetime import datetime, timedelta, timezone

    post = {
        "id": "7",
        "title": "",
        "text": "有没有工具可以自动化这个流程？",
        "created_at": int(time.time() * 1000),
    }
    cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
    item = _normalize(post, cutoff)
    assert item is not None
    assert "有没有工具" in item["title"]


# ── collect integration ──────────────────────────────────────────────────────


def _make_response(posts: list, status: int = 200):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = {"list": posts}
    return resp


def _make_post(pid: str):
    import time

    return {
        "id": pid,
        "title": f"求推荐工具 {pid}",
        "text": "手动处理太麻烦了",
        "created_at": int(time.time() * 1000) - 1_800_000,
        "like_count": 3,
        "reply_count": 1,
        "user": {"screen_name": "user"},
    }


def test_collect_with_explicit_cookie(settings_with_cookie):
    """Collector uses explicit cookie and maps posts to raw items."""
    posts = [_make_post("p1"), _make_post("p2")]
    mock_resp = _make_response(posts)
    empty_resp = _make_response([])

    sess_mock = MagicMock()
    sess_mock.get.side_effect = [mock_resp] + [empty_resp] * 20  # timeline + queries

    with patch("niche_radar.collectors.xueqiu._session", return_value=sess_mock):
        result = XueqiuCollector().collect(settings=settings_with_cookie)

    assert result.status == "completed"
    assert len(result.items) == 2
    ids = {i["source_id"] for i in result.items}
    assert ids == {"p1", "p2"}


def test_collect_auto_fetches_guest_cookie(settings):
    """When no explicit cookie is set, collector obtains an anonymous guest token."""
    cookie_resp = MagicMock()
    cookie_resp.cookies = {"xq_a_token": "auto-token-abc"}

    sess_mock = MagicMock()
    sess_mock.get.side_effect = [_make_response([_make_post("x1")])] + [_make_response([])] * 20

    with patch("requests.get", return_value=cookie_resp), \
         patch("niche_radar.collectors.xueqiu._session", return_value=sess_mock):
        result = XueqiuCollector().collect(settings=settings)

    assert result.status == "completed"
    assert result.items[0]["source_id"] == "x1"


def test_collect_fails_gracefully_when_no_cookie(settings, monkeypatch):
    """Returns 'failed' status when even the auto-guest-session fails."""
    monkeypatch.setattr(
        "niche_radar.collectors.xueqiu._get_cookie",
        lambda s, db: "",
    )
    result = XueqiuCollector().collect(settings=settings)
    assert result.status == "failed"
    assert "cookie" in (result.error_message or "").lower()


def test_collect_dry_run_returns_empty(settings):
    result = XueqiuCollector().collect(settings=settings, dry_run=True)
    assert result.status == "completed"
    assert result.items == []
