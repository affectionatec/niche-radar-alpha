"""Exa global-search collector — semantic web discovery for pain-point signals.

Exa (api.exa.ai) is a neural search engine that returns semantically-matched
web results with extracted text.  When an API key is present, the collector
runs configurable pain-point queries and maps each result to a raw item.

Requires an Exa API key (exa.ai).  The collector is silently skipped when no
key is configured, matching the credential-gated source pattern.
"""

from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from typing import ClassVar

import structlog

from niche_radar.collectors._http import post_json
from niche_radar.collectors.base import BaseCollector, CollectorResult
from niche_radar.storage.repository import get_source_credential

logger = structlog.get_logger()

_EXA_SEARCH = "https://api.exa.ai/search"
_DEFAULT_FRESHNESS_DAYS = 7

DEFAULT_QUERIES = [
    "I wish there was a tool that",
    "is there software that can automatically",
    "we do this manually with spreadsheets",
    "looking for an alternative to",
    "this product is too expensive",
    "painful workflow that needs automation",
    "frustrating that there is no tool for",
]


def _api_key(settings, db: sqlite3.Connection | None) -> str | None:
    val = get_source_credential(db, "exa", "api_key", None) if db else None
    return val or getattr(settings, "exa_api_key", None) or None


def _queries(db: sqlite3.Connection | None) -> list[str]:
    raw = get_source_credential(db, "exa", "search_queries", None) if db else None
    return json.loads(raw) if raw else DEFAULT_QUERIES


def _normalize(hit: dict, query: str) -> dict | None:
    """Map an Exa result to a normalized raw item."""
    url = hit.get("url") or ""
    if not url:
        return None
    source_id = url  # URL is the stable identifier for web results

    published = hit.get("publishedDate") or ""
    posted_dt: datetime | None = None
    if published:
        try:
            posted_dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
        except ValueError:
            pass
    if posted_dt is None:
        posted_dt = datetime.now(timezone.utc)

    title = (hit.get("title") or "").strip()
    body = (hit.get("text") or hit.get("highlights") or "")
    if isinstance(body, list):
        body = " … ".join(body)
    body = body.strip() or None

    return {
        "source_id": source_id,
        "title": title or url,
        "body": body,
        "url": url,
        "score": int(round((hit.get("score") or 0) * 100)),  # normalize 0-1 → 0-100
        "comment_count": 0,
        "posted_at": posted_dt.isoformat(),
        "metadata": {
            "matched_query": query,
            "exa_score": hit.get("score"),
            "author": hit.get("author") or None,
        },
    }


class ExaCollector(BaseCollector):
    source_name = "exa"

    CREDENTIAL_SCHEMA: ClassVar[list[dict]] = [
        {
            "key": "api_key",
            "label": "Exa API Key",
            "secret": True,
            "optional": False,
            "help": "API key from exa.ai. Required to run this source.",
        },
        {
            "key": "search_queries",
            "label": "Search queries (JSON array)",
            "secret": False,
            "optional": True,
            "help": 'Pain-point phrases to search. e.g. ["I wish there was a tool","we do this manually"]',
        },
    ]

    @classmethod
    def is_available(cls, db: sqlite3.Connection | None, settings) -> bool:
        return bool(_api_key(settings, db))

    @classmethod
    def test_connection(cls, db: sqlite3.Connection, settings) -> tuple[bool, str]:
        key = _api_key(settings, db)
        if not key:
            return False, "Exa API key not configured"
        try:
            result = post_json(
                _EXA_SEARCH,
                headers={"x-api-key": key},
                json_body={"query": "test", "numResults": 1},
            )
            if isinstance(result, dict) and "results" in result:
                return True, "Exa API key valid"
            return False, f"Unexpected Exa response: {str(result)[:100]}"
        except Exception as exc:
            return False, str(exc)

    def collect(
        self, settings, dry_run: bool = False, db: sqlite3.Connection | None = None
    ) -> CollectorResult:
        start = time.perf_counter()
        if dry_run:
            return CollectorResult(self.source_name, [], "", "completed", 0)

        key = _api_key(settings, db)
        if not key:
            return CollectorResult(
                source=self.source_name, items=[], run_id="",
                status="failed", items_collected=0,
                error_message="Exa API key not configured",
                duration_seconds=time.perf_counter() - start,
            )

        queries = _queries(db)
        freshness_days = _DEFAULT_FRESHNESS_DAYS
        start_date = (
            datetime.now(timezone.utc) - timedelta(days=freshness_days)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")

        items: dict[str, dict] = {}
        errors: list[str] = []
        headers = {"x-api-key": key}

        for query in queries:
            try:
                data = post_json(
                    _EXA_SEARCH,
                    headers=headers,
                    json_body={
                        "query": query,
                        "numResults": 10,
                        "startPublishedDate": start_date,
                        "contents": {"text": True},
                    },
                )
                for hit in (data.get("results") or []):
                    item = _normalize(hit, query)
                    if item and item["source_id"] not in items:
                        items[item["source_id"]] = item
            except Exception as exc:
                logger.warning("exa_query_failed", query=query[:40], error=str(exc))
                errors.append(f"query '{query[:40]}': {exc}")

        collected = list(items.values())
        status = "completed" if collected else ("partial" if errors else "failed")
        return CollectorResult(
            source=self.source_name, items=collected, run_id="",
            status=status, items_collected=len(collected),
            error_message="; ".join(errors) or None,
            duration_seconds=time.perf_counter() - start,
        )
