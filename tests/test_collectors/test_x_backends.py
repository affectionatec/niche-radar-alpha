"""Tests for the X multi-backend chain (xAI, Xquik, GraphQL-cookie)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from niche_radar.collectors.twitter import TwitterCollector
from niche_radar.collectors.x_backends import XaiBackend, XquikBackend
from niche_radar.collectors.x_backends.base import ParsedTweet, XBackend
from niche_radar.config import Settings
from niche_radar.storage.database import get_db
from niche_radar.storage.repository import set_source_credential


@pytest.fixture(autouse=True)
def _no_pacing(monkeypatch):
    """Null out the polite inter-query delay so tests run fast."""
    monkeypatch.setattr("niche_radar.collectors.x_backends.base.INTER_QUERY_DELAY", 0)


@pytest.fixture
def settings():
    return Settings()


@pytest.fixture
def db(tmp_path):
    return get_db(f"sqlite:///{tmp_path / 'test.db'}")


# ── XBackend.fetch normalization (via a stub backend) ───────────────────────

class _StubBackend(XBackend):
    name = "stub"

    def __init__(self, tweets):
        self._tweets = tweets

    def is_available(self, settings, db):
        return True

    def search_one(self, query, settings, db):
        return list(self._tweets)


def test_fetch_normalizes_and_dedupes(settings, db):
    now = datetime.now(timezone.utc)
    backend = _StubBackend([
        ParsedTweet(id="1", text="I wish there was a tool for X", author="alice",
                    created_at=now, likes=10, retweets=5, replies=2),
        ParsedTweet(id="1", text="dup", author="alice", created_at=now),  # same id → deduped
    ])
    items = backend.fetch(settings, db)
    assert len(items) == 1
    item = items[0]
    assert item["source_id"] == "1"
    assert item["score"] == 15  # likes + retweets
    assert item["comment_count"] == 2
    assert item["url"] == "https://x.com/alice/status/1"
    assert item["metadata"]["auth_mode"] == "stub"
    assert item["title"] == "I wish there was a tool for X"


def test_fetch_drops_stale_items(settings, db):
    old = datetime(2000, 1, 1, tzinfo=timezone.utc)
    backend = _StubBackend([ParsedTweet(id="9", text="old", created_at=old)])
    assert backend.fetch(settings, db) == []


def test_search_queries_override_from_db(settings, db):
    set_source_credential(db, "twitter", "search_queries", '["custom phrase"]')
    seen = []

    class _Recorder(_StubBackend):
        def search_one(self, query, settings, db):
            seen.append(query)
            return []

    _Recorder([]).fetch(settings, db)
    assert seen == ["custom phrase"]


# ── XaiBackend parsing ──────────────────────────────────────────────────────

def test_xai_parse_extracts_items(settings, db):
    set_source_credential(db, "twitter", "xai_api_key", "xai-test")
    backend = XaiBackend()
    assert backend.is_available(settings, db)

    fake_resp = {
        "output": [{
            "type": "message",
            "content": [{"type": "output_text", "text":
                '{"items": [{"text": "someone should build a CRM for vets",'
                ' "url": "https://x.com/bob/status/123", "author_handle": "@bob",'
                ' "date": "2026-06-01", "engagement": {"likes": 4, "reposts": 1, "replies": 0}}]}'
            }],
        }]
    }
    with patch("niche_radar.collectors.x_backends.xai._http.post_json", return_value=fake_resp):
        tweets = backend.search_one("someone should build", settings, db)
    assert len(tweets) == 1
    assert tweets[0].id == "123"
    assert tweets[0].author == "bob"
    assert tweets[0].likes == 4


def test_xai_unavailable_without_key(settings, db):
    assert XaiBackend().is_available(settings, db) is False


# ── XquikBackend parsing ────────────────────────────────────────────────────

def test_xquik_parse_extracts_items(settings, db):
    set_source_credential(db, "twitter", "xquik_api_key", "xq-test")
    backend = XquikBackend()
    assert backend.is_available(settings, db)

    fake_resp = {"tweets": [{
        "id": "555",
        "text": "is there a tool that does this",
        "author": {"username": "carol"},
        "createdAt": "2026-06-01T10:00:00Z",
        "likeCount": 7, "retweetCount": 2, "replyCount": 3,
    }]}
    with patch("niche_radar.collectors.x_backends.xquik._http.get_json", return_value=fake_resp):
        tweets = backend.search_one("is there a tool that", settings, db)
    assert len(tweets) == 1
    assert tweets[0].id == "555"
    assert tweets[0].author == "carol"
    assert tweets[0].retweets == 2


# ── Collector wiring / fallback ─────────────────────────────────────────────

def test_collector_unavailable_without_any_creds(settings, db):
    assert TwitterCollector.is_available(db, settings) is False
    ok, msg = TwitterCollector.test_connection(db, settings)
    assert ok is False
    assert "No X backend" in msg


def test_collector_prefers_xai_then_reports_backend(settings, db):
    set_source_credential(db, "twitter", "xai_api_key", "xai-test")
    assert TwitterCollector.is_available(db, settings) is True
    ok, msg = TwitterCollector.test_connection(db, settings)
    assert ok is True
    assert "xai" in msg


def test_collector_falls_through_to_xquik(settings, db):
    # No xAI key, but Xquik configured → chain should land on xquik.
    set_source_credential(db, "twitter", "xquik_api_key", "xq-test")
    fake_resp = {"tweets": [{
        "id": "777", "text": "we do this manually every week",
        "author": {"username": "dave"}, "createdAt": datetime.now(timezone.utc).isoformat(),
        "likeCount": 1, "retweetCount": 0, "replyCount": 0,
    }]}
    with patch("niche_radar.collectors.x_backends.xquik._http.get_json", return_value=fake_resp):
        result = TwitterCollector().collect(settings=settings, db=db)
    assert result.status == "completed"
    assert result.metadata["active_backend"] == "xquik"
    assert result.items[0]["source_id"] == "777"


def test_collector_dry_run(settings):
    result = TwitterCollector().collect(settings=settings, dry_run=True)
    assert result.items_collected == 0
