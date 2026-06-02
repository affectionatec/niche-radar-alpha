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
    def test_test_connection_reports_cookie_backend(self, settings, tmp_path):
        """With only cookies set, test_connection reports the graphql_cookie backend."""
        from niche_radar.collectors.twitter import TwitterCollector
        from niche_radar.storage.database import get_db
        from niche_radar.storage.repository import set_source_credential
        db = get_db(f"sqlite:///{tmp_path / 'test.db'}")
        set_source_credential(db, "twitter", "ct0", "fake-ct0")
        set_source_credential(db, "twitter", "auth_token", "fake-auth")

        ok, message = TwitterCollector.test_connection(db, settings)
        assert ok is True
        assert "graphql_cookie" in message

    def test_test_connection_fails_without_any_backend(self, settings, tmp_path):
        """No credentials at all → test_connection reports no backend."""
        from niche_radar.collectors.twitter import TwitterCollector
        from niche_radar.storage.database import get_db
        db = get_db(f"sqlite:///{tmp_path / 'test.db'}")
        ok, message = TwitterCollector.test_connection(db, settings)
        assert ok is False
        assert "No X backend" in message

    def test_collect_missing_cookies_returns_failed(self, settings, tmp_path):
        """No credentials configured → no backend available → failed result."""
        from niche_radar.collectors.twitter import TwitterCollector
        from niche_radar.storage.database import get_db
        db = get_db(f"sqlite:///{tmp_path / 'test.db'}")

        result = TwitterCollector().collect(settings=settings, db=db)
        assert result.status == "failed"

    def test_collect_with_cookies_calls_graphql_endpoint(self, settings, tmp_path):
        """When ct0+auth_token set (and no API key), collector hits SearchTimeline."""
        from niche_radar.collectors.twitter import TwitterCollector
        from niche_radar.collectors.x_backends.graphql_cookie import GraphQLCookieBackend
        from niche_radar.storage.database import get_db
        from niche_radar.storage.repository import set_source_credential
        from datetime import datetime, timezone, timedelta as td
        db = get_db(f"sqlite:///{tmp_path / 'test.db'}")
        set_source_credential(db, "twitter", "ct0", "fake-ct0")
        set_source_credential(db, "twitter", "auth_token", "fake-auth")
        # Single query keeps the test fast (avoids per-query pacing sleeps).
        set_source_credential(db, "twitter", "search_queries", '["I wish there was"]')
        recent_ts = (datetime.now(timezone.utc) - td(hours=1)).strftime("%a %b %d %H:%M:%S +0000 %Y")

        fake_response = {
            "data": {
                "search_by_raw_query": {
                    "search_timeline": {
                        "timeline": {
                            "instructions": [{
                                "type": "TimelineAddEntries",
                                "entries": [{
                                    "content": {
                                        "itemContent": {
                                            "tweet_results": {
                                                "result": {
                                                    "rest_id": "99999",
                                                    "legacy": {
                                                        "full_text": "I wish there was a better tool for CI",
                                                        "created_at": recent_ts,
                                                        "favorite_count": 10,
                                                        "retweet_count": 2,
                                                        "reply_count": 1,
                                                    },
                                                    "core": {
                                                        "user_results": {
                                                            "result": {
                                                                "legacy": {"screen_name": "testuser"}
                                                            }
                                                        }
                                                    },
                                                }
                                            }
                                        }
                                    }
                                }]
                            }]
                        }
                    }
                }
            }
        }
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = fake_response

        with (
            patch.object(GraphQLCookieBackend, "_resolve_query_id", return_value="mock-qid"),
            patch.object(GraphQLCookieBackend, "_transaction_id", return_value="mock-tid"),
            patch("niche_radar.collectors.x_backends.graphql_cookie.requests.get", return_value=mock_resp) as mock_get,
        ):
            result = TwitterCollector().collect(settings=settings, db=db)

        called_url = mock_get.call_args.args[0] if mock_get.call_args.args else mock_get.call_args.kwargs.get("url", "")
        assert called_url.startswith("https://x.com/")
        assert "graphql" in called_url and "SearchTimeline" in called_url
        assert result.items_collected > 0
        assert result.items[0]["source_id"] == "99999"
        assert result.items[0]["metadata"]["auth_mode"] == "graphql_cookie"

    def test_parse_tweets_handles_visibility_wrapper(self):
        """TweetWithVisibilityResults wrapper should be unwrapped correctly."""
        from niche_radar.collectors.x_backends.graphql_cookie import _parse_tweets
        response = {
            "data": {
                "search_by_raw_query": {
                    "search_timeline": {
                        "timeline": {
                            "instructions": [{
                                "type": "TimelineAddEntries",
                                "entries": [{
                                    "content": {
                                        "itemContent": {
                                            "tweet_results": {
                                                "result": {
                                                    "__typename": "TweetWithVisibilityResults",
                                                    "tweet": {
                                                        "rest_id": "12345",
                                                        "legacy": {
                                                            "full_text": "wrapped tweet text",
                                                            "created_at": "Wed Oct 10 20:19:24 +0000 2018",
                                                            "favorite_count": 5,
                                                            "retweet_count": 1,
                                                            "reply_count": 0,
                                                        },
                                                        "core": {
                                                            "user_results": {
                                                                "result": {
                                                                    "legacy": {"screen_name": "wrappeduser"}
                                                                }
                                                            }
                                                        },
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }]
                            }]
                        }
                    }
                }
            }
        }
        tweets = _parse_tweets(response)
        assert len(tweets) == 1
        assert tweets[0].id == "12345"
        assert tweets[0].author == "wrappeduser"
        assert tweets[0].text == "wrapped tweet text"

    def test_collect_dry_run(self, settings):
        from niche_radar.collectors.twitter import TwitterCollector
        result = TwitterCollector().collect(settings=settings, dry_run=True)
        assert result.items_collected == 0

    def test_credential_schema_has_cookie_fields(self):
        from niche_radar.collectors.twitter import TwitterCollector
        keys = {f["key"] for f in TwitterCollector.CREDENTIAL_SCHEMA}
        assert "ct0" in keys
        assert "auth_token" in keys
        assert "graphql_query_id" in keys


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
