"""Stack Overflow collector — unsolved developer pain points via the official API.

Targets questions with no accepted answer, high score, and at least one of the
configured tags (automation, devops, cloud, etc.). These represent real, unsolved
developer friction points.
"""

from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from typing import ClassVar

import requests
import structlog
from tenacity import Retrying, stop_after_attempt, wait_exponential

from niche_radar.collectors.base import BaseCollector, CollectorResult
from niche_radar.storage.repository import get_source_credential

logger = structlog.get_logger()

SO_API = "https://api.stackexchange.com/2.3/questions"
DEFAULT_TAGS = ["automation", "devops", "cloud", "saas", "api", "workflow"]
DEFAULT_MIN_SCORE = 10
DEFAULT_PAGE_SIZE = 50


class StackOverflowCollector(BaseCollector):
    source_name = "stack_overflow"

    CREDENTIAL_SCHEMA: ClassVar[list[dict]] = [
        {"key": "api_key", "label": "Stack Exchange API Key (optional)", "secret": True, "optional": True,
         "help": "Free key at stackapps.com raises quota from 300 to 10000 calls/day"},
        {"key": "tags", "label": "Tags to monitor (JSON array)", "secret": False, "optional": True,
         "help": 'e.g. ["automation","devops","cloud"]'},
        {"key": "min_score", "label": "Minimum question score", "secret": False, "optional": True,
         "help": "Filter questions below this upvote count (default 10)"},
    ]

    @classmethod
    def test_connection(cls, db: sqlite3.Connection, settings) -> tuple[bool, str]:
        api_key = get_source_credential(db, "stack_overflow", "api_key", None)
        params = {"site": "stackoverflow", "pagesize": 1}
        if api_key:
            params["key"] = api_key
        try:
            resp = requests.get(SO_API, params=params, timeout=10)
            if resp.status_code == 200:
                quota = resp.json().get("quota_remaining", "?")
                return True, f"Stack Overflow API OK (quota remaining: {quota})"
            return False, f"HTTP {resp.status_code}"
        except Exception as exc:
            return False, str(exc)

    def collect(
        self, settings, dry_run: bool = False, db: sqlite3.Connection | None = None
    ) -> CollectorResult:
        start = time.perf_counter()
        if dry_run:
            return CollectorResult(self.source_name, [], "", "completed", 0)

        try:
            api_key = get_source_credential(db, "stack_overflow", "api_key", None) if db else None

            raw_tags = (get_source_credential(db, "stack_overflow", "tags", None) if db else None)
            tags: list[str] = json.loads(raw_tags) if raw_tags else DEFAULT_TAGS

            min_score = int(
                (get_source_credential(db, "stack_overflow", "min_score", None) if db else None)
                or DEFAULT_MIN_SCORE
            )

            retryer = Retrying(
                stop=stop_after_attempt(max(1, int(settings.max_retries or 1))),
                wait=wait_exponential(multiplier=1, min=1, max=30),
                reraise=True,
            )
            cutoff = datetime.now(timezone.utc) - timedelta(hours=getattr(settings, "freshness_so_hours", 168))
            items: dict[str, dict] = {}
            errors: list[str] = []

            for tag in tags:
                try:
                    params = {
                        "site": "stackoverflow",
                        "tagged": tag,
                        "order": "desc",
                        "sort": "votes",
                        "filter": "withbody",
                        "pagesize": DEFAULT_PAGE_SIZE,
                        "min": min_score,
                    }
                    if api_key:
                        params["key"] = api_key

                    for attempt in retryer:
                        with attempt:
                            resp = requests.get(SO_API, params=params, timeout=20)
                            if resp.status_code != 200:
                                raise ConnectionError(f"SO API returned {resp.status_code}")
                            data = resp.json()

                    for q in data.get("items", []):
                        # Only unsolved pain: no accepted answer
                        if q.get("accepted_answer_id"):
                            continue
                        q_id = str(q["question_id"])
                        posted_dt = datetime.fromtimestamp(q["creation_date"], tz=timezone.utc)
                        if posted_dt < cutoff:
                            continue
                        if q_id in items:
                            items[q_id]["metadata"]["tags"].extend(t for t in q.get("tags", []) if t not in items[q_id]["metadata"]["tags"])
                            continue

                        import html as html_lib
                        body_html = q.get("body") or ""
                        # Strip HTML tags for body
                        import re
                        body_text = re.sub(r"<[^>]+>", " ", body_html).strip()
                        body_text = html_lib.unescape(body_text)

                        items[q_id] = {
                            "source_id": q_id,
                            "title": q.get("title", ""),
                            "body": body_text[:2000],
                            "url": q.get("link", f"https://stackoverflow.com/q/{q_id}"),
                            "score": q.get("score", 0),
                            "comment_count": q.get("answer_count", 0),
                            "posted_at": posted_dt.isoformat(),
                            "metadata": {
                                "tags": q.get("tags", []),
                                "answer_count": q.get("answer_count", 0),
                                "view_count": q.get("view_count", 0),
                                "owner": q.get("owner", {}).get("display_name"),
                                "is_unanswered": True,
                            },
                        }
                    # Respect SO quota: brief pause between tag queries
                    time.sleep(0.2)
                except Exception as exc:
                    logger.warning("so_tag_failed", tag=tag, error=str(exc))
                    errors.append(f"tag '{tag}': {exc}")

            collected = list(items.values())
            status = "completed" if not errors else "partial" if collected else "failed"
            return CollectorResult(
                source=self.source_name, items=collected, run_id="",
                status=status, items_collected=len(collected),
                error_message="; ".join(errors) or None,
                duration_seconds=time.perf_counter() - start,
            )
        except Exception as exc:
            logger.exception("so_collect_failed", error=str(exc))
            return CollectorResult(
                source=self.source_name, items=[], run_id="", status="failed",
                items_collected=0, error_message=str(exc),
                duration_seconds=time.perf_counter() - start,
            )
