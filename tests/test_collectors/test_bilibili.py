"""Tests for the Bilibili collector — all network calls are mocked (fully offline)."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from niche_radar.collectors.bilibili import (
    BilibiliAuthApiBackend,
    BilibiliCollector,
    BilibiliPublicApiBackend,
    _clean,
    _normalize,
)
from niche_radar.config import Settings


@pytest.fixture
def s_no_cred():
    s = Settings()
    s.bilibili_sessdata = ""
    return s


@pytest.fixture
def s_with_sessdata():
    s = Settings()
    s.bilibili_sessdata = "sessdata-test-abc"
    return s


# ── availability ─────────────────────────────────────────────────────────────


def test_auth_backend_unavailable_without_sessdata(s_no_cred):
    assert BilibiliAuthApiBackend().is_available(s_no_cred, None) is False


def test_auth_backend_available_with_sessdata(s_with_sessdata):
    assert BilibiliAuthApiBackend().is_available(s_with_sessdata, None) is True


def test_public_backend_always_available(s_no_cred):
    assert BilibiliPublicApiBackend().is_available(s_no_cred, None) is True


# ── _clean helper ─────────────────────────────────────────────────────────────


def test_clean_strips_html_tags():
    assert _clean("<em>工具</em> 推荐") == "工具 推荐"


def test_clean_handles_none():
    assert _clean(None) == ""


def test_clean_handles_no_tags():
    assert _clean("plain text") == "plain text"


# ── _normalize helper ─────────────────────────────────────────────────────────


def test_normalize_maps_video_to_raw_item():
    from datetime import datetime, timedelta, timezone

    cutoff = datetime.now(timezone.utc) - timedelta(hours=336)
    video = {
        "bvid": "BV1test",
        "aid": 12345,
        "title": "有没有<em>工具</em>可以自动化这个流程",
        "description": "教程 手动操作太麻烦",
        "pubdate": int(time.time()) - 86400,
        "play": 50000,
        "video_review": 200,
        "author": "up主A",
        "tag": "工具,效率",
    }
    item = _normalize(video, cutoff, "有没有什么工具")
    assert item is not None
    assert item["source_id"] == "bili-BV1test"
    assert "工具" in item["title"]
    assert "<em>" not in item["title"]
    assert item["score"] == 50000
    assert item["comment_count"] == 200
    assert item["metadata"]["author"] == "up主A"
    assert item["metadata"]["matched_queries"] == ["有没有什么工具"]


def test_normalize_drops_stale_video():
    from datetime import datetime, timedelta, timezone

    cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
    video = {
        "bvid": "BVold",
        "pubdate": int((datetime.now(timezone.utc) - timedelta(hours=200)).timestamp()),
        "title": "old video",
    }
    assert _normalize(video, cutoff, "q") is None


def test_normalize_returns_none_without_id():
    from datetime import datetime, timedelta, timezone

    cutoff = datetime.now(timezone.utc) - timedelta(hours=336)
    assert _normalize({"title": "no id"}, cutoff, "q") is None


def test_normalize_uses_aid_when_no_bvid():
    from datetime import datetime, timedelta, timezone

    cutoff = datetime.now(timezone.utc) - timedelta(hours=336)
    video = {
        "aid": 9999,
        "title": "av-only video",
        "pubdate": int(time.time()) - 3600,
    }
    item = _normalize(video, cutoff, "q")
    assert item is not None
    assert item["source_id"] == "bili-9999"
    assert "/av9999" in item["url"]


# ── search helper (via backend) ───────────────────────────────────────────────


def _api_response(bvids: list[str]) -> dict:
    return {
        "code": 0,
        "message": "0",
        "data": {
            "result": [
                {
                    "bvid": bvid,
                    "title": f"视频 {bvid}",
                    "description": "工具推荐",
                    "pubdate": int(time.time()) - 3600,
                    "play": 1000,
                    "video_review": 10,
                    "author": "up",
                    "tag": "",
                }
                for bvid in bvids
            ]
        },
    }


def _mock_session(bvids_per_call: list[list[str]]):
    """Build a mock requests.Session whose get() cycles through bvids_per_call."""
    responses = [_make_resp(_api_response(bvids)) for bvids in bvids_per_call]
    sess = MagicMock()
    sess.get.side_effect = responses
    return sess


def _make_resp(data: dict, status: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = data
    return resp


# ── auth backend fetch ────────────────────────────────────────────────────────


def test_auth_backend_fetch_returns_items(s_with_sessdata):
    n_queries = len(__import__("niche_radar.collectors.bilibili", fromlist=["DEFAULT_QUERIES"]).DEFAULT_QUERIES)
    bvids_per_call = [["BVauth1"]] + [[]] * (n_queries - 1)

    with patch("niche_radar.collectors.bilibili._requests.Session") as MockSess:
        MockSess.return_value = _mock_session(bvids_per_call)
        items = BilibiliAuthApiBackend().fetch(s_with_sessdata, None)

    assert len(items) == 1
    assert items[0]["source_id"] == "bili-BVauth1"


def test_auth_backend_raises_when_all_queries_fail(s_with_sessdata):
    sess = MagicMock()
    sess.get.return_value = _make_resp({"code": -403, "message": "forbidden"})

    with patch("niche_radar.collectors.bilibili._requests.Session", return_value=sess):
        with pytest.raises(RuntimeError, match="API error"):
            BilibiliAuthApiBackend().fetch(s_with_sessdata, None)


# ── public backend fetch ──────────────────────────────────────────────────────


def test_public_backend_auto_fetches_buvid3(s_no_cred):
    cookie_resp = MagicMock()
    cookie_resp.cookies = {"buvid3": "auto-buvid3-xyz"}

    n_queries = len(__import__("niche_radar.collectors.bilibili", fromlist=["DEFAULT_QUERIES"]).DEFAULT_QUERIES)
    bvids_per_call = [["BVpub1"]] + [[]] * (n_queries - 1)

    with patch("niche_radar.collectors.bilibili._requests.get", return_value=cookie_resp), \
         patch("niche_radar.collectors.bilibili._requests.Session") as MockSess:
        MockSess.return_value = _mock_session(bvids_per_call)
        items = BilibiliPublicApiBackend().fetch(s_no_cred, None)

    assert len(items) == 1
    assert items[0]["source_id"] == "bili-BVpub1"


def test_public_backend_works_without_buvid3(s_no_cred):
    """Proceeds even when buvid3 auto-fetch fails (session without cookie)."""
    cookie_resp = MagicMock()
    cookie_resp.cookies = {}

    n_queries = len(__import__("niche_radar.collectors.bilibili", fromlist=["DEFAULT_QUERIES"]).DEFAULT_QUERIES)
    bvids_per_call = [["BVnb1"]] + [[]] * (n_queries - 1)

    with patch("niche_radar.collectors.bilibili._requests.get", return_value=cookie_resp), \
         patch("niche_radar.collectors.bilibili._requests.Session") as MockSess:
        MockSess.return_value = _mock_session(bvids_per_call)
        items = BilibiliPublicApiBackend().fetch(s_no_cred, None)

    assert items[0]["source_id"] == "bili-BVnb1"


# ── full collector integration ────────────────────────────────────────────────


def test_collector_prefers_auth_when_sessdata_set(s_with_sessdata):
    n_queries = len(__import__("niche_radar.collectors.bilibili", fromlist=["DEFAULT_QUERIES"]).DEFAULT_QUERIES)
    bvids_per_call = [["BVauth99"]] + [[]] * (n_queries - 1)

    with patch("niche_radar.collectors.bilibili._requests.Session") as MockSess:
        MockSess.return_value = _mock_session(bvids_per_call)
        result = BilibiliCollector().collect(settings=s_with_sessdata)

    assert result.status == "completed"
    assert result.metadata["active_backend"] == "auth_api"


def test_collector_uses_public_without_sessdata(s_no_cred):
    cookie_resp = MagicMock()
    cookie_resp.cookies = {"buvid3": "b3"}

    n_queries = len(__import__("niche_radar.collectors.bilibili", fromlist=["DEFAULT_QUERIES"]).DEFAULT_QUERIES)
    bvids_per_call = [["BVpub99"]] + [[]] * (n_queries - 1)

    with patch("niche_radar.collectors.bilibili._requests.get", return_value=cookie_resp), \
         patch("niche_radar.collectors.bilibili._requests.Session") as MockSess:
        MockSess.return_value = _mock_session(bvids_per_call)
        result = BilibiliCollector().collect(settings=s_no_cred)

    assert result.status == "completed"
    assert result.metadata["active_backend"] == "public_api"


def test_collector_falls_through_to_public_when_auth_fails(s_with_sessdata):
    call_count = {"n": 0}
    cookie_resp = MagicMock()
    cookie_resp.cookies = {"buvid3": "b3"}

    n_queries = len(__import__("niche_radar.collectors.bilibili", fromlist=["DEFAULT_QUERIES"]).DEFAULT_QUERIES)

    def session_factory():
        call_count["n"] += 1
        if call_count["n"] == 1:
            # auth backend: all API errors → raises
            sess = MagicMock()
            sess.get.return_value = _make_resp({"code": -403, "message": "forbidden"})
            return sess
        else:
            # public backend: one good result
            return _mock_session([["BVfallback"]] + [[]] * (n_queries - 1))

    with patch("niche_radar.collectors.bilibili._requests.get", return_value=cookie_resp), \
         patch("niche_radar.collectors.bilibili._requests.Session", side_effect=session_factory):
        result = BilibiliCollector().collect(settings=s_with_sessdata)

    assert result.metadata["active_backend"] == "public_api"
    assert result.items[0]["source_id"] == "bili-BVfallback"


def test_collector_dry_run_returns_empty(s_no_cred):
    result = BilibiliCollector().collect(settings=s_no_cred, dry_run=True)
    assert result.status == "completed"
    assert result.items == []


def test_collector_deduplicates_across_queries(s_no_cred):
    """Same bvid returned by two queries → appears once in output with merged matched_queries."""
    cookie_resp = MagicMock()
    cookie_resp.cookies = {"buvid3": "b3"}

    # All queries return the same bvid
    n_queries = len(__import__("niche_radar.collectors.bilibili", fromlist=["DEFAULT_QUERIES"]).DEFAULT_QUERIES)
    bvids_per_call = [["BVdup"]] * n_queries

    with patch("niche_radar.collectors.bilibili._requests.get", return_value=cookie_resp), \
         patch("niche_radar.collectors.bilibili._requests.Session") as MockSess:
        MockSess.return_value = _mock_session(bvids_per_call)
        result = BilibiliCollector().collect(settings=s_no_cred)

    ids = [i["source_id"] for i in result.items]
    assert ids.count("bili-BVdup") == 1
    # matched_queries should accumulate
    item = result.items[0]
    assert len(item["metadata"]["matched_queries"]) == n_queries


def test_collector_test_connection_with_sessdata(s_with_sessdata):
    ok, msg = BilibiliCollector.test_connection(None, s_with_sessdata)
    assert ok is True
    assert "sessdata" in msg.lower() or "auth" in msg.lower()


def test_collector_test_connection_no_sessdata(s_no_cred):
    ok, msg = BilibiliCollector.test_connection(None, s_no_cred)
    assert ok is True
    assert "public" in msg.lower() or "guest" in msg.lower()
