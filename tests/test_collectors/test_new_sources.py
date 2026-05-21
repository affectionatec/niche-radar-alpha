"""Unit tests for P1 new collectors: Product Hunt, Stack Overflow, Twitter, G2.

All HTTP calls are mocked. Tests verify normalization, dry-run, and error handling.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from niche_radar.config import Settings


@pytest.fixture
def settings():
    return Settings()


# ── Stack Overflow ─────────────────────────────────────────────────────────────

class TestStackOverflowCollector:
    def _make_question(self, qid, title, score=15, has_accepted=False, tag="automation"):
        return {
            "question_id": qid,
            "title": title,
            "body": f"<p>This is the body of question {qid}</p>",
            "link": f"https://stackoverflow.com/q/{qid}",
            "score": score,
            "answer_count": 2,
            "view_count": 1000,
            "accepted_answer_id": 999 if has_accepted else None,
            "creation_date": int(datetime.now(timezone.utc).timestamp()) - 3600,
            "tags": [tag],
            "owner": {"display_name": "testuser"},
        }

    def _mock_so_response(self, questions):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"items": questions, "quota_remaining": 290}
        return resp

    def test_collect_returns_unanswered_questions(self, settings, tmp_path):
        from niche_radar.collectors.stack_overflow import StackOverflowCollector
        from niche_radar.storage.database import get_db
        db = get_db(f"sqlite:///{tmp_path / 'test.db'}")

        questions = [
            self._make_question(1, "How to automate X?"),
            self._make_question(2, "Already answered Q", has_accepted=True),
        ]
        with patch("requests.get", return_value=self._mock_so_response(questions)):
            result = StackOverflowCollector().collect(settings=settings, db=db)

        ids = [it["source_id"] for it in result.items]
        assert "1" in ids
        assert "2" not in ids  # has accepted answer — should be filtered out

    def test_collect_dry_run(self, settings):
        from niche_radar.collectors.stack_overflow import StackOverflowCollector
        result = StackOverflowCollector().collect(settings=settings, dry_run=True)
        assert result.items_collected == 0

    def test_credential_schema_has_api_key(self):
        from niche_radar.collectors.stack_overflow import StackOverflowCollector
        keys = {f["key"] for f in StackOverflowCollector.CREDENTIAL_SCHEMA}
        assert "api_key" in keys


# ── Twitter ────────────────────────────────────────────────────────────────────

class TestTwitterCollector:
    def _make_tweet(self, tid, text):
        tweet = MagicMock()
        tweet.id = tid
        tweet.text = text
        tweet.created_at = datetime.now(timezone.utc)
        tweet.public_metrics = {"like_count": 5, "retweet_count": 2, "reply_count": 1, "quote_count": 0}
        return tweet

    def test_collect_missing_bearer_token_raises(self, settings, tmp_path):
        from niche_radar.collectors.twitter import TwitterCollector
        from niche_radar.storage.database import get_db
        db = get_db(f"sqlite:///{tmp_path / 'test.db'}")

        result = TwitterCollector().collect(settings=settings, db=db)
        assert result.status == "failed"
        # Error message should mention bearer_token OR be an unavailability error
        error = (result.error_message or "").lower()
        assert "bearer_token" in error or "not configured" in error or "credentials" in error

    def test_collect_with_bearer_token(self, settings, tmp_path):
        from niche_radar.collectors.twitter import TwitterCollector
        from niche_radar.storage.database import get_db
        from niche_radar.storage.repository import set_source_credential
        db = get_db(f"sqlite:///{tmp_path / 'test.db'}")
        set_source_credential(db, "twitter", "bearer_token", "fake-token")

        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.data = [self._make_tweet(111, "I wish there was a better tool for CI")]
        mock_client.search_recent_tweets.return_value = mock_resp

        with patch("tweepy.Client", return_value=mock_client):
            result = TwitterCollector().collect(settings=settings, db=db)

        assert result.items_collected > 0
        assert result.items[0]["source_id"] == "111"

    def test_collect_dry_run(self, settings):
        from niche_radar.collectors.twitter import TwitterCollector
        result = TwitterCollector().collect(settings=settings, dry_run=True)
        assert result.items_collected == 0


# ── Product Hunt ───────────────────────────────────────────────────────────────

class TestProductHuntCollector:
    def test_collect_dry_run(self, settings):
        from niche_radar.collectors.product_hunt import ProductHuntCollector
        result = ProductHuntCollector().collect(settings=settings, dry_run=True)
        assert result.items_collected == 0
        assert result.status == "completed"

    def test_collect_http_error_returns_failed(self, settings, tmp_path):
        from niche_radar.collectors.product_hunt import ProductHuntCollector
        from niche_radar.storage.database import get_db
        db = get_db(f"sqlite:///{tmp_path / 'test.db'}")

        bad_resp = MagicMock()
        bad_resp.status_code = 403
        bad_resp.text = "Forbidden"
        with patch("requests.get", return_value=bad_resp):
            result = ProductHuntCollector().collect(settings=settings, db=db)

        assert result.status in ("failed", "partial")


# ── G2 Reviews ────────────────────────────────────────────────────────────────

class TestG2ReviewsCollector:
    def test_collect_dry_run(self, settings):
        from niche_radar.collectors.g2_reviews import G2ReviewsCollector
        result = G2ReviewsCollector().collect(settings=settings, dry_run=True)
        assert result.items_collected == 0

    def test_cloudflare_block_returns_partial_not_crash(self, settings, tmp_path):
        from niche_radar.collectors.g2_reviews import G2ReviewsCollector
        from niche_radar.storage.database import get_db
        db = get_db(f"sqlite:///{tmp_path / 'test.db'}")

        blocked_resp = MagicMock()
        blocked_resp.status_code = 403

        # Use patch on requests inside the module to intercept Session creation
        with patch("niche_radar.collectors.g2_reviews.requests") as mock_requests:
            mock_sess = MagicMock()
            mock_sess.get.return_value = blocked_resp
            mock_requests.Session.return_value = mock_sess
            mock_requests.Session.return_value.__enter__ = lambda s: s
            mock_requests.Session.return_value.__exit__ = MagicMock(return_value=False)
            result = G2ReviewsCollector().collect(settings=settings, db=db)

        # Must not crash — should return partial/failed gracefully
        assert result.status in ("failed", "partial")
        assert result.items_collected == 0


# ── Dispatcher roundtrip ───────────────────────────────────────────────────────

def test_dispatch_new_sources_dont_crash_on_import():
    """All new source slugs must resolve to a collector without import errors."""
    from niche_radar.collectors import _get_collector
    for slug in ("product_hunt", "stack_overflow", "twitter", "g2_reviews"):
        collector = _get_collector(slug)
        assert collector is not None
        assert collector.source_name == slug
