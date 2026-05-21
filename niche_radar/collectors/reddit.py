"""Reddit data collector."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import structlog
from tenacity import Retrying, stop_after_attempt, wait_exponential

from niche_radar.collectors.base import (
    BaseCollector,
    CollectorResult,
    CollectorUnavailableError,
)

logger = structlog.get_logger()
SUBREDDITS = [
    "SaaS",
    "selfhosted",
    "webdev",
    "smallbusiness",
    "Entrepreneur",
    "sideproject",
    "macapps",
    "devops",
    "dataengineering",
    "nocode",
]
PAIN_POINT_PHRASES = [
    "is there a tool",
    "i wish there was",
    "alternative to",
    "how do you automate",
    "pricing is crazy",
    "looking for",
    "recommend a",
    "frustrated with",
]


class RedditCollector(BaseCollector):
    source_name = "reddit"

    def collect(self, settings, dry_run: bool = False) -> CollectorResult:
        start = time.perf_counter()
        if dry_run:
            return CollectorResult(self.source_name, [], "", "completed", 0)

        try:
            if not settings.reddit_client_id or not settings.reddit_client_secret:
                raise CollectorUnavailableError("Reddit credentials not configured")

            import praw

            retryer = Retrying(
                stop=stop_after_attempt(max(1, int(settings.max_retries or 1))),
                wait=wait_exponential(
                    multiplier=1,
                    exp_base=max(2, int(settings.retry_backoff_base or 2)),
                    min=1,
                    max=30,
                ),
                reraise=True,
            )
            reddit = praw.Reddit(
                client_id=settings.reddit_client_id,
                client_secret=settings.reddit_client_secret,
                user_agent=settings.reddit_user_agent,
            )
            cutoff = datetime.now(timezone.utc) - timedelta(hours=settings.freshness_reddit_hours)
            items: list[dict] = []
            errors: list[str] = []

            for subreddit_name in SUBREDDITS:
                try:
                    for attempt in retryer:
                        with attempt:
                            submissions = list(reddit.subreddit(subreddit_name).hot(limit=100))
                    kept = 0
                    for submission in submissions:
                        created_at = datetime.fromtimestamp(submission.created_utc, tz=timezone.utc)
                        if created_at < cutoff:
                            continue
                        text = f"{submission.title}\n{submission.selftext or ''}".lower()
                        matches = [phrase for phrase in PAIN_POINT_PHRASES if phrase in text]
                        items.append(
                            {
                                "source_id": str(submission.id),
                                "title": submission.title,
                                "body": submission.selftext or None,
                                "url": f"https://www.reddit.com{submission.permalink}",
                                "score": int(submission.score or 0),
                                "comment_count": int(submission.num_comments or 0),
                                "posted_at": created_at.isoformat(),
                                "metadata": {
                                    "subreddit": subreddit_name,
                                    "author": str(submission.author) if submission.author else None,
                                    "post_flair": submission.link_flair_text,
                                    "created_at": created_at.isoformat(),
                                    "external_url": submission.url,
                                    "matched_phrases": matches,
                                    "has_pain_point_signal": bool(matches),
                                },
                            }
                        )
                        kept += 1
                        if kept >= 50:
                            break
                except Exception as exc:
                    logger.warning(
                        "reddit_subreddit_failed", subreddit=subreddit_name, error=str(exc)
                    )
                    errors.append(f"{subreddit_name}: {exc}")

            status = "completed" if not errors else "partial" if items else "failed"
            return CollectorResult(
                source=self.source_name,
                items=items,
                run_id="",
                status=status,
                items_collected=len(items),
                error_message="; ".join(errors) or None,
                duration_seconds=time.perf_counter() - start,
            )
        except Exception as exc:
            logger.exception("reddit_collect_failed", error=str(exc))
            return CollectorResult(
                source=self.source_name,
                items=[],
                run_id="",
                status="failed",
                items_collected=0,
                error_message=str(exc),
                duration_seconds=time.perf_counter() - start,
            )
