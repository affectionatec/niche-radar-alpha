"""Shared base for ScrapeCreators-backed collectors (TikTok, Instagram, Threads).

These platforms all sit behind one ScrapeCreators API key and share the same
shape: run pain-point phrases through a per-platform search endpoint, then
normalize captions/posts into raw items. The base owns the credential
resolution, query loop, dedupe, freshness cutoff, and HTTP; subclasses supply
the endpoint, params, and per-item parsing.

Ported from last30days lib/{tiktok,instagram,threads}.py. One key
(``SCRAPECREATORS_API_KEY``) unlocks all three.
"""

from __future__ import annotations

import os
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from typing import ClassVar

import structlog

from niche_radar.collectors import _http
from niche_radar.collectors.base import BaseCollector, CollectorResult
from niche_radar.storage.repository import get_source_credential

logger = structlog.get_logger()

SC_BASE = "https://api.scrapecreators.com"
_PER_QUERY_LIMIT = 20
_INTER_QUERY_DELAY = 0.5

# Pain-point phrases (caption-friendly — no platform-specific operators).
PAIN_QUERIES = [
    "I wish there was an app",
    "someone should build",
    "is there an app that",
    "how do you deal with",
    "biggest struggle with",
]

_KEY_FIELD = "scrapecreators_api_key"


def resolve_api_key(db, source: str) -> str | None:
    """Per-source DB credential → shared ``SCRAPECREATORS_API_KEY`` env var."""
    return (
        (get_source_credential(db, source, _KEY_FIELD, None) if db else None)
        or os.environ.get("SCRAPECREATORS_API_KEY")
    )


def epoch_or_iso(value) -> datetime | None:
    """Parse epoch-seconds or ISO-8601 timestamps to aware UTC."""
    if value is None:
        return None
    # Epoch seconds (int/float/numeric string)
    try:
        ts = float(value)
        if ts > 1_000_000_000:  # ~2001+, distinguishes seconds from small ints
            return datetime.fromtimestamp(ts, tz=timezone.utc)
    except (ValueError, TypeError):
        pass
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


class ScrapeCreatorsCollector(BaseCollector):
    """Base collector for ScrapeCreators platforms. Subclass and override hooks."""

    platform: str = ""           # used for URLs / logging / auth_mode
    freshness_hours_default: int = 168  # 7 days — search results skew recent

    CREDENTIAL_SCHEMA: ClassVar[list[dict]] = [
        {
            "key": _KEY_FIELD,
            "label": "ScrapeCreators API key",
            "secret": True,
            "optional": False,
            "help": "One key (scrapecreators.com) unlocks TikTok, Instagram, and Threads. "
                    "Can also be set once via the SCRAPECREATORS_API_KEY env var.",
        },
        {
            "key": "search_queries",
            "label": "Search queries (JSON array, optional)",
            "secret": False,
            "optional": True,
            "help": 'Caption phrases, e.g. ["I wish there was an app","someone should build"]',
        },
    ]

    # ── hooks for subclasses ────────────────────────────────────────────────
    def endpoint(self) -> str:
        raise NotImplementedError

    def query_params(self, query: str) -> dict:
        raise NotImplementedError

    def extract_raw(self, data: dict) -> list[dict]:
        raise NotImplementedError

    def parse_item(self, raw: dict, query: str) -> dict | None:
        """Return a raw-item dict (without freshness filtering) or None."""
        raise NotImplementedError

    # ── shared machinery ────────────────────────────────────────────────────
    @classmethod
    def is_available(cls, db: sqlite3.Connection | None, settings) -> bool:
        return bool(resolve_api_key(db, cls.source_name))

    @classmethod
    def test_connection(cls, db: sqlite3.Connection, settings) -> tuple[bool, str]:
        token = resolve_api_key(db, cls.source_name)
        if not token:
            return False, "Set scrapecreators_api_key (or SCRAPECREATORS_API_KEY env var)."
        inst = cls()
        try:
            _http.get_json(
                inst.endpoint(),
                headers=_headers(token),
                params=inst.query_params(PAIN_QUERIES[0]),
                timeout=30, retries=1,
            )
            return True, f"✓ ScrapeCreators key OK for {cls.platform}"
        except _http.HTTPError as exc:
            if exc.status_code in (401, 403):
                return False, "ScrapeCreators key rejected (401/403)."
            return True, f"Key accepted but endpoint returned HTTP {exc.status_code}"
        except Exception as exc:
            return False, f"ScrapeCreators error: {exc}"

    def collect(
        self, settings, dry_run: bool = False, db: sqlite3.Connection | None = None
    ) -> CollectorResult:
        start = time.perf_counter()
        if dry_run:
            return CollectorResult(self.source_name, [], "", "completed", 0)

        token = resolve_api_key(db, self.source_name)
        if not token:
            return CollectorResult(
                self.source_name, [], "", "failed", 0,
                error_message="ScrapeCreators API key not configured.",
                duration_seconds=time.perf_counter() - start,
            )

        queries = self._queries(db)
        cutoff = datetime.now(timezone.utc) - timedelta(
            hours=getattr(settings, f"freshness_{self.source_name}_hours", self.freshness_hours_default)
        )
        by_id: dict[str, dict] = {}
        errors: list[str] = []

        for i, query in enumerate(queries):
            try:
                data = _http.get_json(
                    self.endpoint(),
                    headers=_headers(token),
                    params=self.query_params(query),
                    timeout=30, retries=2,
                )
                for raw in self.extract_raw(data)[:_PER_QUERY_LIMIT]:
                    item = self.parse_item(raw, query)
                    if not item:
                        continue
                    posted = item.get("posted_at")
                    if posted:
                        dt = epoch_or_iso(posted)
                        if dt and dt < cutoff:
                            continue
                        item["posted_at"] = dt.isoformat() if dt else None
                    sid = item["source_id"]
                    if sid in by_id:
                        by_id[sid]["metadata"]["matched_queries"].append(query)
                    else:
                        by_id[sid] = item
            except Exception as exc:
                logger.warning("scrapecreators_query_failed", platform=self.platform, query=query, error=str(exc))
                errors.append(f"query '{query}': {exc}")
            if i < len(queries) - 1:
                time.sleep(_INTER_QUERY_DELAY)

        items = list(by_id.values())
        status = "completed" if items else ("partial" if not errors else "failed")
        return CollectorResult(
            source=self.source_name, items=items, run_id="",
            status=status, items_collected=len(items),
            error_message="; ".join(errors) or None,
            duration_seconds=time.perf_counter() - start,
        )

    def _queries(self, db) -> list[str]:
        import json
        raw = get_source_credential(db, self.source_name, "search_queries", None) if db else None
        if raw:
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list) and parsed:
                    return [str(q) for q in parsed]
            except (ValueError, TypeError):
                pass
        return PAIN_QUERIES

    def _item(self, source_id, text, url, score, comments, posted_raw, author, query) -> dict | None:
        """Helper for subclasses to build the normalized raw-item dict."""
        text = (text or "").strip()
        if not (source_id and text and url):
            return None
        return {
            "source_id": str(source_id),
            "title": text[:140],
            "body": text,
            "url": url,
            "score": int(score or 0),
            "comment_count": int(comments or 0),
            "posted_at": posted_raw,  # raw timestamp; collect() converts/filters
            "metadata": {
                "matched_queries": [query],
                "author": author,
                "auth_mode": f"scrapecreators_{self.platform}",
            },
        }


def _headers(token: str) -> dict:
    return {"x-api-key": token, "Content-Type": "application/json"}
