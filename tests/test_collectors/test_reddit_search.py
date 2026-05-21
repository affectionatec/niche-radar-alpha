"""Tests for the refactored Reddit collector — search-based, DB-configurable."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from niche_radar.collectors.reddit import RedditCollector, DEFAULT_SUBREDDITS, DEFAULT_SEARCH_QUERIES
from niche_radar.config import Settings


@pytest.fixture
def settings():
    return Settings(reddit_client_id="cid", reddit_client_secret="csecret", reddit_user_agent="test/0.1")


def _make_submission(sid, title, body, score, created_utc):
    """Minimal mock praw Submission."""
    sub = MagicMock()
    sub.id = sid
    sub.title = title
    sub.selftext = body
    sub.permalink = f"/r/SaaS/comments/{sid}/test"
    sub.score = score
    sub.num_comments = 5
    sub.created_utc = created_utc
    sub.subreddit.display_name = "SaaS"
    sub.author = MagicMock()
    sub.author.__str__ = lambda s: "testuser"
    sub.link_flair_text = None
    sub.url = f"https://reddit.com/r/SaaS/comments/{sid}"
    return sub


def test_collect_uses_search_not_hot(settings, tmp_path):
    """Collector must call subreddit.search(), not .hot()."""
    db_path = tmp_path / "test.db"
    from niche_radar.storage.database import get_db
    db = get_db(f"sqlite:///{db_path}")

    import time
    recent_utc = time.time() - 3600  # 1 hour ago — within the freshness window

    mock_reddit = MagicMock()
    sub_mock = mock_reddit.subreddit.return_value
    sub_mock.search.return_value = [_make_submission("abc", "I wish there was a tool", "", 50, recent_utc)]

    with patch("praw.Reddit", return_value=mock_reddit):
        result = RedditCollector().collect(settings=settings, dry_run=False, db=db)

    # .search() must have been called at least once; .hot() must NOT have been called
    assert sub_mock.search.called, "search() was never called"
    assert not sub_mock.hot.called, "hot() should not be called in the new implementation"
    assert result.items_collected > 0


def test_collect_dedupes_across_queries(settings, tmp_path):
    """Same submission returned by two queries must appear only once in items."""
    db_path = tmp_path / "test.db"
    from niche_radar.storage.database import get_db
    db = get_db(f"sqlite:///{db_path}")

    import time
    recent_utc = time.time() - 3600
    same_submission = _make_submission("dup", "I wish there was a better tool", "", 40, recent_utc)

    mock_reddit = MagicMock()
    mock_reddit.subreddit.return_value.search.return_value = [same_submission]

    with patch("praw.Reddit", return_value=mock_reddit):
        result = RedditCollector().collect(settings=settings, dry_run=False, db=db)

    ids = [it["source_id"] for it in result.items]
    assert ids.count("dup") == 1, f"Expected 1, got {ids.count('dup')}"


def test_collect_db_overrides_default_subreddits(settings, tmp_path):
    """Subreddits from DB must replace the DEFAULT_SUBREDDITS."""
    from niche_radar.storage.database import get_db
    from niche_radar.storage.repository import set_source_credential
    db = get_db(f"sqlite:///{tmp_path / 'test.db'}")
    set_source_credential(db, "reddit", "subreddits", json.dumps(["CustomSub"]))

    import time
    recent_utc = time.time() - 3600

    mock_reddit = MagicMock()
    mock_reddit.subreddit.return_value.search.return_value = [
        _make_submission("x", "custom sub result", "", 10, recent_utc)
    ]

    with patch("praw.Reddit", return_value=mock_reddit):
        RedditCollector().collect(settings=settings, dry_run=False, db=db)

    # subreddit() must have been called with exactly "CustomSub" (the joined string)
    call_args = mock_reddit.subreddit.call_args_list
    assert any("CustomSub" in str(c) for c in call_args), f"Expected CustomSub in subreddit call: {call_args}"


def test_collect_dry_run_returns_empty(settings):
    result = RedditCollector().collect(settings=settings, dry_run=True)
    assert result.items_collected == 0
    assert result.status == "completed"


def test_credential_schema_covers_required_fields():
    schema_keys = {f["key"] for f in RedditCollector.CREDENTIAL_SCHEMA}
    assert "client_id" in schema_keys
    assert "client_secret" in schema_keys
    assert "search_queries" in schema_keys
