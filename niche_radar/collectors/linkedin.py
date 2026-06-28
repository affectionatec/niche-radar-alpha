"""LinkedIn data collector — pain-point discovery from professional content.

Per ADR-008: Agent-Reach's linkedin-mcp recipe is rejected — it's an MCP server
requiring a running browser + login session, incompatible with an unattended
pipeline.  Instead, this collector walks an ordered chain:

    1. public_search — LinkedIn public search (keyless, always available);
                        queries the public search endpoint directly.  LinkedIn's
                        public pages are JS-heavy, so this backend may return
                        zero items and fall through (expected behavior).

    2. jina_reader    — opt-in r.jina.ai fallback that reads the same search
                        pages with JS rendering, yielding real content.

The Jina tier is opt-in (per-source ``jina_fallback`` credential or
``JINA_READER_ENABLED`` env var).  When both backends are unavailable or return
nothing, the source degrades to partial/failed without crashing.
"""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone
from typing import ClassVar

import requests
import structlog

from niche_radar.collectors._http import get_json, USER_AGENT
from niche_radar.collectors._jina import is_enabled
from niche_radar.collectors.backends.jina import JinaReaderBackend
from niche_radar.collectors.multi_backend import MultiBackendCollector, SourceBackend
from niche_radar.storage.repository import get_source_credential

logger = structlog.get_logger()

_LINKEDIN_SEARCH = "https://www.linkedin.com/search/results/content/"

DEFAULT_QUERIES = [
    "I wish there was a tool for",
    "looking for an alternative to",
    "we still use spreadsheets for",
    "is there software that automates",
    "this manual workflow is painful",
    "frustrating that there's no tool",
    "anyone built something to automate",
]

_HEADERS = {"User-Agent": USER_AGENT}


def _queries(db: sqlite3.Connection | None) -> list[str]:
    raw = get_source_credential(db, "linkedin", "search_queries", None) if db else None
    return json.loads(raw) if raw else DEFAULT_QUERIES


def _linkedin_search_urls(settings, db: sqlite3.Connection | None) -> list[str]:
    """Build LinkedIn content-search URLs for each pain-point query."""
    from urllib.parse import quote

    return [f"{_LINKEDIN_SEARCH}?keywords={quote(q)}" for q in _queries(db)]


class LinkedInPublicSearchBackend(SourceBackend):
    """LinkedIn public search — keyless, always available.

    Note: LinkedIn's public pages are heavily JS-rendered.  A plain HTTP GET
    will return the initial HTML shell but not the dynamically-loaded search
    results.  This backend is a nominal first attempt — it may legitimately
    return zero items, in which case the chain falls through to the Jina
    reader (which renders JS and captures actual content).
    """

    name = "public_search"

    def is_available(self, settings, db: sqlite3.Connection | None) -> bool:
        return True  # always try — keyless

    def fetch(self, settings, db: sqlite3.Connection | None) -> list[dict]:
        queries = _queries(db)
        items: dict[str, dict] = {}
        errors: list[str] = []

        for query in queries:
            try:
                resp = requests.get(
                    _LINKEDIN_SEARCH,
                    params={"keywords": query},
                    headers=_HEADERS,
                    timeout=15,
                )
                if resp.status_code != 200:
                    errors.append(f"query '{query}': HTTP {resp.status_code}")
                    continue

                html = resp.text
                # LinkedIn's public HTML is mostly JS — attempt to extract any
                # static content that happens to be in the initial payload.
                # This is a best-effort; the Jina tier is the real capture path.
                if not html or len(html) < 500:
                    errors.append(f"query '{query}': empty or trivial response")
                    continue

                # Generate a single document item for this query result.
                sid = f"li-{hash(query) & 0x7FFFFFFF}"
                items[sid] = {
                    "source_id": sid,
                    "title": f"LinkedIn search: {query}",
                    "body": None,
                    "url": f"{_LINKEDIN_SEARCH}?keywords={query.replace(' ', '+')}",
                    "score": 0,
                    "comment_count": 0,
                    "posted_at": datetime.now(timezone.utc).isoformat(),
                    "metadata": {
                        "matched_query": query,
                        "capture": "public_search",
                    },
                }
            except Exception as exc:
                logger.warning("linkedin_public_search_failed", query=query, error=str(exc))
                errors.append(f"query '{query}': {exc}")

        if not items and errors:
            raise RuntimeError("; ".join(errors))
        return list(items.values())


class LinkedInCollector(MultiBackendCollector):
    source_name = "linkedin"

    CREDENTIAL_SCHEMA: ClassVar[list[dict]] = [
        {
            "key": "jina_fallback",
            "label": "Enable Jina Reader for LinkedIn",
            "secret": False,
            "optional": True,
            "help": "Set to 'true' to add the Jina Reader resilience tier for LinkedIn (reads search results with JS rendering). Without this, only the basic public search is attempted (limited content from JS-heavy pages).",
        },
        {
            "key": "jina_api_key",
            "label": "Jina Reader API key (optional)",
            "secret": True,
            "optional": True,
            "help": "Optional — raises Jina rate limits. Get one at jina.ai/reader.",
        },
        {
            "key": "search_queries",
            "label": "Search queries (JSON array)",
            "secret": False,
            "optional": True,
            "help": 'Pain-point phrases to search, e.g. ["looking for an alternative to","I wish there was a tool"]',
        },
    ]

    def build_backends(self) -> list[SourceBackend]:
        return [
            LinkedInPublicSearchBackend(),
            JinaReaderBackend("linkedin", _linkedin_search_urls),
        ]

    @classmethod
    def test_connection(cls, db: sqlite3.Connection, settings) -> tuple[bool, str]:
        if is_enabled(settings, db, "linkedin"):
            return True, "LinkedIn: public search (keyless) + Jina Reader enabled"
        return True, "LinkedIn: public search (keyless) — enable Jina Reader fallback in Settings for richer results"
