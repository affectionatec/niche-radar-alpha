"""Tests for the rewritten HN collector — Algolia API based."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from niche_radar.collectors.hackernews import HackerNewsCollector
from niche_radar.config import Settings

_NOW_TS = int(datetime.now(timezone.utc).timestamp())


def _hit(object_id, title, created_at_i=None, points=20, num_comments=10, text=None):
    return {
        "objectID": str(object_id),
        "title": title,
        "story_text": text,
        "url": f"https://example.com/{object_id}",
        "points": points,
        "num_comments": num_comments,
        "created_at_i": created_at_i or (_NOW_TS - 3600),
        "author": "tester",
    }


@pytest.fixture
def settings():
    return Settings()


def _mock_get(hits):
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {"hits": hits}
    return response


def test_collect_calls_algolia_for_each_query(settings, tmp_path):
    from niche_radar.storage.database import get_db
    db = get_db(f"sqlite:///{tmp_path / 'test.db'}")

    mock_response = _mock_get([_hit("1", "Ask HN: I wish there was a tool")])
    with patch("requests.get", return_value=mock_response) as mock_get:
        result = HackerNewsCollector().collect(settings=settings, dry_run=False, db=db)

    # Should have called requests.get at least as many times as there are default queries
    assert mock_get.call_count >= 1
    # All calls should target the Algolia endpoint
    for call in mock_get.call_args_list:
        url = call.args[0] if call.args else call.kwargs.get("url", "")
        assert "algolia" in url or "hn.algolia" in url


def test_collect_dedupes_hits_across_queries(settings, tmp_path):
    from niche_radar.storage.database import get_db
    db = get_db(f"sqlite:///{tmp_path / 'test.db'}")

    same_hit = _hit("dup", "I wish there was a better tool")
    mock_response = _mock_get([same_hit])
    with patch("requests.get", return_value=mock_response):
        result = HackerNewsCollector().collect(settings=settings, dry_run=False, db=db)

    ids = [it["source_id"] for it in result.items]
    assert ids.count("dup") == 1


def test_collect_filters_stale_items(settings, tmp_path):
    from niche_radar.storage.database import get_db
    db = get_db(f"sqlite:///{tmp_path / 'test.db'}")

    stale_ts = _NOW_TS - (7 * 24 * 3600 + 3600)  # older than 72h freshness window
    fresh_ts = _NOW_TS - 3600
    hits = [_hit("stale", "old post", created_at_i=stale_ts), _hit("fresh", "new post", created_at_i=fresh_ts)]
    with patch("requests.get", return_value=_mock_get(hits)):
        result = HackerNewsCollector().collect(settings=settings, dry_run=False, db=db)

    ids = [it["source_id"] for it in result.items]
    assert "fresh" in ids
    assert "stale" not in ids


def test_collect_db_overrides_search_queries(settings, tmp_path):
    from niche_radar.storage.database import get_db
    from niche_radar.storage.repository import set_source_credential
    db = get_db(f"sqlite:///{tmp_path / 'test.db'}")
    set_source_credential(db, "hn", "search_queries", json.dumps(["custom query only"]))

    mock_response = _mock_get([_hit("q1", "custom query result")])
    with patch("requests.get", return_value=mock_response) as mock_get:
        HackerNewsCollector().collect(settings=settings, dry_run=False, db=db)

    # Should be called exactly once (one custom query)
    assert mock_get.call_count == 1
    called_url = mock_get.call_args.args[0] if mock_get.call_args.args else ""
    assert "custom+query+only" in called_url or "custom query only" in str(mock_get.call_args)


def test_collect_dry_run_returns_empty(settings):
    result = HackerNewsCollector().collect(settings=settings, dry_run=True)
    assert result.items_collected == 0
