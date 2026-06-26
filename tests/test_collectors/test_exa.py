"""Tests for the Exa semantic-search collector — all network is mocked (fully offline)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from niche_radar.collectors._http import HTTPError
from niche_radar.collectors.exa import ExaCollector, _normalize
from niche_radar.config import Settings


@pytest.fixture
def s_no_key():
    s = Settings()
    s.exa_api_key = ""
    return s


@pytest.fixture
def s_with_key():
    s = Settings()
    s.exa_api_key = "exa-key-test-abc"
    return s


# ── availability ─────────────────────────────────────────────────────────────


def test_unavailable_without_key(s_no_key):
    assert ExaCollector.is_available(None, s_no_key) is False


def test_available_with_key(s_with_key):
    assert ExaCollector.is_available(None, s_with_key) is True


# ── _normalize helper ────────────────────────────────────────────────────────


def test_normalize_maps_hit_to_raw_item():
    hit = {
        "url": "https://example.com/post/123",
        "title": "We still do this manually with spreadsheets",
        "text": "Our team uses Excel to track everything, it's a pain.",
        "publishedDate": "2026-06-20T12:00:00Z",
        "score": 0.87,
        "author": "Jane Doe",
    }
    item = _normalize(hit, "we do this manually")
    assert item is not None
    assert item["source_id"] == "https://example.com/post/123"
    assert item["title"] == "We still do this manually with spreadsheets"
    assert item["score"] == 87  # 0.87 * 100, rounded
    assert item["metadata"]["matched_query"] == "we do this manually"
    assert item["metadata"]["author"] == "Jane Doe"


def test_normalize_returns_none_for_missing_url():
    hit = {"title": "no url here", "score": 0.5}
    assert _normalize(hit, "test") is None


def test_normalize_joins_highlight_list():
    hit = {
        "url": "https://example.com",
        "highlights": ["pain point A", "pain point B"],
        "score": 0.6,
    }
    item = _normalize(hit, "q")
    assert item is not None
    assert "pain point A" in (item["body"] or "")
    assert "pain point B" in (item["body"] or "")


def test_normalize_handles_missing_published_date():
    hit = {"url": "https://example.com/x", "title": "t", "score": 0.5}
    item = _normalize(hit, "q")
    assert item is not None
    assert item["posted_at"]  # falls back to now()


# ── collect integration ──────────────────────────────────────────────────────


def _exa_response(urls: list[str]):
    return {
        "results": [
            {
                "url": u,
                "title": f"Title for {u}",
                "text": "Some pain-point text.",
                "publishedDate": "2026-06-20T10:00:00Z",
                "score": 0.75,
            }
            for u in urls
        ]
    }


def test_collect_returns_failed_without_key(s_no_key):
    result = ExaCollector().collect(settings=s_no_key)
    assert result.status == "failed"
    assert "not configured" in (result.error_message or "").lower()


def test_collect_maps_search_results_to_items(s_with_key):
    call_count = {"n": 0}

    def mock_post(url, **kw):
        call_count["n"] += 1
        return _exa_response([f"https://example.com/{call_count['n']}"])

    with patch("niche_radar.collectors.exa.post_json", side_effect=mock_post):
        result = ExaCollector().collect(settings=s_with_key)

    assert result.status == "completed"
    assert len(result.items) == call_count["n"]
    assert result.items[0]["score"] == 75


def test_collect_deduplicates_same_url_across_queries(s_with_key):
    """Same URL returned for multiple queries → deduplicated in output."""
    shared_url = "https://shared.com/article"

    with patch(
        "niche_radar.collectors.exa.post_json",
        return_value=_exa_response([shared_url]),
    ):
        result = ExaCollector().collect(settings=s_with_key)

    urls = [i["source_id"] for i in result.items]
    assert urls.count(shared_url) == 1


def test_collect_partial_when_some_queries_fail(s_with_key):
    call_count = {"n": 0}

    def sometimes_fail(url, **kw):
        call_count["n"] += 1
        if call_count["n"] % 2 == 0:
            raise HTTPError("quota", 429)
        return _exa_response([f"https://example.com/{call_count['n']}"])

    with patch("niche_radar.collectors.exa.post_json", side_effect=sometimes_fail):
        result = ExaCollector().collect(settings=s_with_key)

    assert result.status in ("completed", "partial")
    assert len(result.items) > 0


def test_collect_dry_run_returns_empty(s_with_key):
    result = ExaCollector().collect(settings=s_with_key, dry_run=True)
    assert result.status == "completed"
    assert result.items == []
