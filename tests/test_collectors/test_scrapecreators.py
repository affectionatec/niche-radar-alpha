"""Tests for the ScrapeCreators family (TikTok, Instagram, Threads)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from niche_radar.collectors import _scrapecreators as sc
from niche_radar.collectors.instagram import InstagramCollector
from niche_radar.collectors.threads import ThreadsCollector
from niche_radar.collectors.tiktok import TikTokCollector
from niche_radar.config import Settings
from niche_radar.storage.database import get_db
from niche_radar.storage.repository import set_source_credential


@pytest.fixture
def settings():
    return Settings()


@pytest.fixture
def db(tmp_path):
    return get_db(f"sqlite:///{tmp_path / 'test.db'}")


@pytest.fixture(autouse=True)
def _fast(monkeypatch):
    monkeypatch.setattr(sc, "_INTER_QUERY_DELAY", 0)
    monkeypatch.delenv("SCRAPECREATORS_API_KEY", raising=False)


_RECENT = int(datetime.now(timezone.utc).timestamp())


# ── gating ──────────────────────────────────────────────────────────────────

def test_unavailable_without_key(settings, db):
    assert TikTokCollector.is_available(db, settings) is False
    assert InstagramCollector.is_available(db, settings) is False
    assert ThreadsCollector.is_available(db, settings) is False


def test_env_key_enables_all(settings, db, monkeypatch):
    monkeypatch.setenv("SCRAPECREATORS_API_KEY", "sc-test")
    assert TikTokCollector.is_available(db, settings) is True
    assert ThreadsCollector.is_available(db, settings) is True


def test_per_source_key_enables_one(settings, db):
    set_source_credential(db, "tiktok", "scrapecreators_api_key", "sc-test")
    assert TikTokCollector.is_available(db, settings) is True
    assert InstagramCollector.is_available(db, settings) is False


def test_schema_has_key_field():
    for cls in (TikTokCollector, InstagramCollector, ThreadsCollector):
        keys = {f["key"] for f in cls.CREDENTIAL_SCHEMA}
        assert "scrapecreators_api_key" in keys


def test_dry_run(settings):
    assert TikTokCollector().collect(settings=settings, dry_run=True).items_collected == 0


# ── parsing / normalization ─────────────────────────────────────────────────

def test_tiktok_collect_normalizes(settings, db):
    set_source_credential(db, "tiktok", "scrapecreators_api_key", "sc-test")
    set_source_credential(db, "tiktok", "search_queries", '["I wish there was an app"]')
    resp = {"search_item_list": [{"aweme_info": {
        "aweme_id": "v123",
        "desc": "I wish there was an app to track my plants",
        "statistics": {"digg_count": 100, "share_count": 10, "comment_count": 5, "play_count": 9000},
        "author": {"unique_id": "planty"},
        "create_time": _RECENT,
    }}]}
    with patch.object(sc._http, "get_json", return_value=resp):
        result = TikTokCollector().collect(settings=settings, db=db)
    assert result.status == "completed"
    item = result.items[0]
    assert item["source_id"] == "v123"
    assert item["score"] == 110  # digg + share
    assert item["comment_count"] == 5
    assert item["url"] == "https://www.tiktok.com/@planty/video/v123"
    assert item["metadata"]["auth_mode"] == "scrapecreators_tiktok"


def test_threads_collect_normalizes(settings, db):
    set_source_credential(db, "threads", "scrapecreators_api_key", "sc-test")
    set_source_credential(db, "threads", "search_queries", '["someone should build"]')
    resp = {"items": [{
        "id": "th9", "text": "someone should build a CRM for plumbers",
        "user": {"username": "bob"}, "code": "abc",
        "like_count": 20, "repost_count": 4, "reply_count": 3,
        "taken_at": _RECENT,
    }]}
    with patch.object(sc._http, "get_json", return_value=resp):
        result = ThreadsCollector().collect(settings=settings, db=db)
    item = result.items[0]
    assert item["source_id"] == "th9"
    assert item["score"] == 24
    assert item["url"] == "https://www.threads.net/post/abc"


def test_instagram_collect_normalizes(settings, db):
    set_source_credential(db, "instagram", "scrapecreators_api_key", "sc-test")
    set_source_credential(db, "instagram", "search_queries", '["is there an app that"]')
    resp = {"reels": [{
        "id": "ig1", "shortcode": "XYZ",
        "caption": {"text": "is there an app that does meal prep"},
        "owner": {"username": "chef"},
        "like_count": 50, "comment_count": 8, "taken_at": _RECENT,
    }]}
    with patch.object(sc._http, "get_json", return_value=resp):
        result = InstagramCollector().collect(settings=settings, db=db)
    item = result.items[0]
    assert item["source_id"] == "ig1"
    assert item["score"] == 50
    assert item["url"] == "https://www.instagram.com/reel/XYZ"


def test_stale_items_dropped(settings, db):
    set_source_credential(db, "threads", "scrapecreators_api_key", "sc-test")
    set_source_credential(db, "threads", "search_queries", '["someone should build"]')
    old = int(datetime(2020, 1, 1, tzinfo=timezone.utc).timestamp())
    resp = {"items": [{"id": "old", "text": "ancient", "user": {"username": "x"},
                       "code": "old", "taken_at": old}]}
    with patch.object(sc._http, "get_json", return_value=resp):
        result = ThreadsCollector().collect(settings=settings, db=db)
    assert result.items == []


def test_empty_text_skipped(settings, db):
    set_source_credential(db, "threads", "scrapecreators_api_key", "sc-test")
    set_source_credential(db, "threads", "search_queries", '["x"]')
    resp = {"items": [{"id": "n", "text": "", "user": {"username": "x"}, "code": "n"}]}
    with patch.object(sc._http, "get_json", return_value=resp):
        result = ThreadsCollector().collect(settings=settings, db=db)
    assert result.items == []
