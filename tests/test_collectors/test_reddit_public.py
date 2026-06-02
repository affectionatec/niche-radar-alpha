"""Tests for the keyless Reddit public-JSON fallback (Phase 5)."""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from niche_radar.collectors import reddit_public
from niche_radar.collectors.reddit import RedditCollector
from niche_radar.config import Settings
from niche_radar.storage.database import get_db


@pytest.fixture
def db(tmp_path):
    return get_db(f"sqlite:///{tmp_path / 'test.db'}")


def _listing(posts):
    return {"data": {"children": [{"kind": "t3", "data": p} for p in posts]}}


def _post(pid, title, created=None, score=12, comments=3):
    return {
        "id": pid, "title": title, "selftext": "body text",
        "permalink": f"/r/SaaS/comments/{pid}/x", "score": score,
        "num_comments": comments, "created_utc": created or (time.time() - 3600),
        "subreddit": "SaaS", "author": "tester", "link_flair_text": None,
        "url": f"https://reddit.com/r/SaaS/comments/{pid}",
    }


# ── public search helper ────────────────────────────────────────────────────

def test_search_public_normalizes(monkeypatch):
    from datetime import datetime, timedelta, timezone
    cutoff = datetime.now(timezone.utc) - timedelta(hours=72)
    resp = _listing([_post("p1", "I wish there was a tool for invoicing")])
    with patch.object(reddit_public._http, "get_json", return_value=resp):
        items, errors = reddit_public.search_public(["SaaS"], ["I wish there was"], cutoff)
    assert errors == []
    assert len(items) == 1
    item = items[0]
    assert item["source_id"] == "p1"
    assert item["url"] == "https://www.reddit.com/r/SaaS/comments/p1/x"
    assert item["metadata"]["auth_mode"] == "public_json"
    assert item["score"] == 12


def test_search_public_drops_stale(monkeypatch):
    from datetime import datetime, timedelta, timezone
    cutoff = datetime.now(timezone.utc) - timedelta(hours=72)
    old = time.time() - 100 * 3600  # ~4 days ago, outside 72h window
    resp = _listing([_post("old", "stale", created=old)])
    with patch.object(reddit_public._http, "get_json", return_value=resp):
        items, _ = reddit_public.search_public(["SaaS"], ["q"], cutoff)
    assert items == []


def test_search_public_dedupes_across_queries():
    from datetime import datetime, timedelta, timezone
    cutoff = datetime.now(timezone.utc) - timedelta(hours=72)
    resp = _listing([_post("dup", "shared result")])
    with patch.object(reddit_public._http, "get_json", return_value=resp):
        items, _ = reddit_public.search_public(["SaaS"], ["q1", "q2"], cutoff)
    assert len(items) == 1
    assert sorted(items[0]["metadata"]["matched_queries"]) == ["q1", "q2"]


# ── collector integration: no-credential path uses public fallback ──────────

def test_collector_without_creds_uses_public(db):
    settings = Settings(reddit_client_id="", reddit_client_secret="")
    resp = _listing([_post("pub1", "someone should build a thing")])
    with patch.object(reddit_public._http, "get_json", return_value=resp):
        result = RedditCollector().collect(settings=settings, db=db)
    assert result.status == "completed"
    assert result.items_collected == 1
    assert result.items[0]["metadata"]["auth_mode"] == "public_json"


def test_collector_praw_failure_falls_back_to_public(db):
    settings = Settings(reddit_client_id="cid", reddit_client_secret="csecret")
    resp = _listing([_post("fb1", "fallback result")])
    # PRAW raises on every query; public fallback should rescue the run.
    with (
        patch("praw.Reddit", side_effect=RuntimeError("praw down")),
        patch.object(reddit_public._http, "get_json", return_value=resp),
    ):
        result = RedditCollector().collect(settings=settings, db=db)
    assert result.items_collected == 1
    assert result.items[0]["source_id"] == "fb1"
