"""Tests for the Bluesky collector (AT Protocol pain-point search)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from niche_radar.collectors import bluesky as bsky
from niche_radar.collectors.bluesky import BlueskyCollector
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
def _fast_and_clean(monkeypatch):
    monkeypatch.setattr(bsky, "_INTER_QUERY_DELAY", 0)
    # Reset the module-level session-token cache between tests.
    monkeypatch.setattr(bsky, "_cached_token", None)
    monkeypatch.setattr(bsky, "_token_ts", 0.0)


def _post(uri, text, handle="alice.bsky.social", likes=3, reposts=1, replies=2, when=None):
    return {
        "uri": uri,
        "author": {"handle": handle},
        "record": {"text": text, "createdAt": (when or datetime.now(timezone.utc)).isoformat()},
        "indexedAt": (when or datetime.now(timezone.utc)).isoformat(),
        "likeCount": likes, "repostCount": reposts, "replyCount": replies,
    }


def test_unavailable_without_creds(settings, db):
    assert BlueskyCollector.is_available(db, settings) is False


def test_available_with_creds(settings, db):
    set_source_credential(db, "bluesky", "bsky_handle", "alice.bsky.social")
    set_source_credential(db, "bluesky", "bsky_app_password", "abcd-abcd-abcd-abcd")
    assert BlueskyCollector.is_available(db, settings) is True


def test_credential_schema_fields():
    keys = {f["key"] for f in BlueskyCollector.CREDENTIAL_SCHEMA}
    assert {"bsky_handle", "bsky_app_password"} <= keys


def test_dry_run(settings):
    assert BlueskyCollector().collect(settings=settings, dry_run=True).items_collected == 0


def test_collect_missing_creds_failed(settings, db):
    result = BlueskyCollector().collect(settings=settings, db=db)
    assert result.status == "failed"


def test_collect_normalizes_and_dedupes(settings, db):
    set_source_credential(db, "bluesky", "bsky_handle", "alice.bsky.social")
    set_source_credential(db, "bluesky", "bsky_app_password", "abcd-abcd-abcd-abcd")
    set_source_credential(db, "bluesky", "search_queries", '["I wish there was"]')

    search_resp = {"posts": [
        _post("at://did:plc:x/app.bsky.feed.post/aaa", "I wish there was a budgeting app for freelancers", likes=10, reposts=4, replies=1),
        _post("at://did:plc:x/app.bsky.feed.post/aaa", "dup same uri"),  # deduped
    ]}
    with (
        patch.object(bsky._http, "post_json", return_value={"accessJwt": "tok"}),
        patch.object(bsky._http, "get_json", return_value=search_resp),
    ):
        result = BlueskyCollector().collect(settings=settings, db=db)

    assert result.status == "completed"
    assert len(result.items) == 1
    item = result.items[0]
    assert item["source_id"].endswith("/aaa")
    assert item["score"] == 14  # likes + reposts
    assert item["comment_count"] == 1
    assert item["url"] == "https://bsky.app/profile/alice.bsky.social/post/aaa"
    assert item["metadata"]["auth_mode"] == "bluesky"


def test_collect_drops_stale(settings, db):
    set_source_credential(db, "bluesky", "bsky_handle", "alice.bsky.social")
    set_source_credential(db, "bluesky", "bsky_app_password", "abcd-abcd-abcd-abcd")
    set_source_credential(db, "bluesky", "search_queries", '["I wish there was"]')
    old = datetime(2000, 1, 1, tzinfo=timezone.utc)
    search_resp = {"posts": [_post("at://did:plc:x/app.bsky.feed.post/old", "ancient post", when=old)]}
    with (
        patch.object(bsky._http, "post_json", return_value={"accessJwt": "tok"}),
        patch.object(bsky._http, "get_json", return_value=search_resp),
    ):
        result = BlueskyCollector().collect(settings=settings, db=db)
    assert result.items == []


def test_test_connection_reports_ok(settings, db):
    set_source_credential(db, "bluesky", "bsky_handle", "alice.bsky.social")
    set_source_credential(db, "bluesky", "bsky_app_password", "abcd-abcd-abcd-abcd")
    with patch.object(bsky._http, "post_json", return_value={"accessJwt": "tok"}):
        ok, msg = BlueskyCollector.test_connection(db, settings)
    assert ok is True
    assert "alice.bsky.social" in msg
