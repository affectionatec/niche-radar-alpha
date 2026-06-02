"""Twitter / X collector — a resilient multi-backend fallback chain.

X capture is no longer a single brittle path. ``TwitterCollector`` walks an
ordered chain of interchangeable backends and uses the first one that is
configured and returns posts:

    1. xAI live X search      (XAI_API_KEY — no cookies, no scraping)
    2. Xquik REST API         (XQUIK_API_KEY — full engagement metrics)
    3. Internal GraphQL       (ct0 + auth_token cookies — legacy last resort)

Configure any one (or several) from Settings → Data Sources → Twitter / X.
With an API-key backend set, X works with zero cookie/scraping dependency; the
fragile cookie path only runs when no API backend is available.

Backend implementations live in ``niche_radar/collectors/x_backends/``.
"""

from __future__ import annotations

import sqlite3
from typing import ClassVar

from niche_radar.collectors.multi_backend import MultiBackendCollector, SourceBackend
from niche_radar.collectors.x_backends import GraphQLCookieBackend, XaiBackend, XquikBackend


class TwitterCollector(MultiBackendCollector):
    source_name = "twitter"

    CREDENTIAL_SCHEMA: ClassVar[list[dict]] = [
        {
            "key": "xai_api_key",
            "label": "xAI API key (recommended — most stable)",
            "secret": True,
            "optional": True,
            "help": "Get a key at console.x.ai. Uses xAI live X search — no cookies or scraping needed.",
        },
        {
            "key": "xquik_api_key",
            "label": "Xquik API key (alternative — full engagement metrics)",
            "secret": True,
            "optional": True,
            "help": "Get a key at xquik.com. REST API with likes/retweets/replies/views.",
        },
        {
            "key": "ct0",
            "label": "ct0 cookie (fallback — brittle)",
            "secret": True,
            "optional": True,
            "help": "Last-resort path. Log into x.com → DevTools (F12) → Application → Cookies → x.com → copy ct0.",
        },
        {
            "key": "auth_token",
            "label": "auth_token cookie (fallback — brittle)",
            "secret": True,
            "optional": True,
            "help": "Same Cookies panel → copy auth_token. Both ct0 + auth_token are required for the cookie path.",
        },
        {
            "key": "graphql_query_id",
            "label": "SearchTimeline Query ID (optional — auto-discovered if blank)",
            "secret": False,
            "optional": True,
            "help": "Cookie path only. Leave blank for auto-discovery; set manually if discovery 404s.",
        },
        {
            "key": "search_queries",
            "label": "Search queries (JSON array, optional)",
            "secret": False,
            "optional": True,
            "help": 'Pain-point phrases, e.g. ["I wish there was","is there a tool that"]',
        },
    ]

    def build_backends(self) -> list[SourceBackend]:
        return [XaiBackend(), XquikBackend(), GraphQLCookieBackend()]

    @classmethod
    def test_connection(cls, db: sqlite3.Connection, settings) -> tuple[bool, str]:
        """Report which backend would serve X capture, in priority order."""
        for backend in cls().build_backends():
            try:
                if backend.is_available(settings, db):
                    return True, f"✓ X capture will use the '{backend.name}' backend"
            except Exception:
                continue
        return False, (
            "No X backend configured. Add an xAI key (recommended), an Xquik key, "
            "or ct0 + auth_token cookies."
        )
