"""Tests for the multi-backend Reddit collector: praw → public_json → jina.

All network/PRAW is mocked — fully offline. The Jina tier is opt-in, so it never
makes surprise outbound calls unless a test explicitly enables it.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from niche_radar.collectors import _http, reddit_public
from niche_radar.collectors.reddit import RedditCollector
from niche_radar.config import Settings


@pytest.fixture
def cred_settings():
    s = Settings(reddit_client_id="cid", reddit_client_secret="sec", reddit_user_agent="t/0.1")
    s.max_retries = 1
    return s


@pytest.fixture
def no_cred_settings():
    s = Settings()
    s.reddit_client_id = None
    s.reddit_client_secret = None
    s.max_retries = 1
    return s


def _submission(sid, title, created_utc):
    sub = MagicMock()
    sub.id = sid
    sub.title = title
    sub.selftext = ""
    sub.permalink = f"/r/SaaS/comments/{sid}/x"
    sub.score = 10
    sub.num_comments = 2
    sub.created_utc = created_utc
    sub.subreddit.display_name = "SaaS"
    sub.author = None
    sub.link_flair_text = None
    sub.url = "https://example.com"
    return sub


def test_praw_wins_when_creds_present(cred_settings):
    mock_reddit = MagicMock()
    mock_reddit.subreddit.return_value.search.return_value = [
        _submission("a", "I wish there was a tool", time.time() - 3600)
    ]
    with patch("praw.Reddit", return_value=mock_reddit):
        result = RedditCollector().collect(settings=cred_settings)
    assert result.status == "completed"
    assert result.metadata["active_backend"] == "praw"
    assert result.items[0]["source_id"] == "a"


def test_falls_through_to_public_json_without_creds(no_cred_settings, monkeypatch):
    monkeypatch.setattr(
        reddit_public, "search_public",
        lambda subs, queries, cutoff: ([{"source_id": "pj1", "title": "t", "metadata": {}}], []),
    )
    result = RedditCollector().collect(settings=no_cred_settings)
    assert result.status == "completed"
    assert result.metadata["active_backend"] == "public_json"
    assert result.items[0]["source_id"] == "pj1"


def test_falls_through_to_jina_when_public_blocked(no_cred_settings, monkeypatch):
    # public JSON 403s (no items + errors) → backend raises → chain falls through
    monkeypatch.setattr(
        reddit_public, "search_public",
        lambda subs, queries, cutoff: ([], ["public query 'x': HTTP 403"]),
    )
    monkeypatch.setenv("JINA_READER_ENABLED", "1")
    monkeypatch.setattr(_http, "request", lambda *a, **k: "# r/SaaS search\n\nI wish there was a tool for X")
    result = RedditCollector().collect(settings=no_cred_settings)
    assert result.status == "completed"
    assert result.metadata["active_backend"] == "jina_reader"
    assert result.items[0]["metadata"]["capture"] == "jina_reader"


def test_jina_off_by_default_makes_no_calls(no_cred_settings, monkeypatch):
    monkeypatch.delenv("JINA_READER_ENABLED", raising=False)
    monkeypatch.delenv("JINA_API_KEY", raising=False)
    monkeypatch.setattr(
        reddit_public, "search_public",
        lambda subs, queries, cutoff: ([], ["public query 'x': HTTP 403"]),
    )

    def must_not_call(*a, **k):
        raise AssertionError("Jina must not be called when disabled")

    monkeypatch.setattr(_http, "request", must_not_call)
    result = RedditCollector().collect(settings=no_cred_settings)
    names = [b["backend"] for b in result.metadata["backends"]]
    assert "jina_reader" in names  # present in the chain, but unavailable
    assert result.status in ("partial", "failed")  # degrades, never raises
