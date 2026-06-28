"""Xiaohongshu (小红书) data collector — Jina Reader relay for pain-point discovery.

Per ADR-007: Agent-Reach's cookie/CLI recipe (OpenCLI/xiaohongshu-mcp/xhs-cli) is
rejected — these are desktop/interactive tools incompatible with an unattended
pipeline.  Instead, this collector reads 小红书 search-result pages through
r.jina.ai, the same relay pattern proven in M1 (G2/Indie Hackers) and M2 (Reddit).

The collector is a ``MultiBackendCollector`` whose single backend is a composed
``JinaReaderBackend``.  This leaves the door open for a TikHub or cookie-based
backend to be added as a higher-priority tier later without refactoring the
collector class.

Opt-in only: the Jina tier never fires unless explicitly enabled (per-source
``jina_fallback`` credential or ``JINA_READER_ENABLED`` env var).  When disabled,
the source silently skips in unattended runs.
"""

from __future__ import annotations

import json
import sqlite3
from typing import ClassVar

from niche_radar.collectors._jina import is_enabled
from niche_radar.collectors.backends.jina import JinaReaderBackend
from niche_radar.collectors.multi_backend import MultiBackendCollector, SourceBackend
from niche_radar.storage.repository import get_source_credential

_XHS_SEARCH = "https://www.xiaohongshu.com/search_result"

DEFAULT_QUERIES = [
    "有没有工具",
    "求推荐好用的",
    "找了好久找不到",
    "手动操作太麻烦",
    "有没有替代品",
    "吐槽这个软件",
    "痛点解决方案",
    "效率太低怎么办",
]


def _xhs_search_urls(settings, db: sqlite3.Connection | None) -> list[str]:
    """Build 小红书 search-result URLs for each pain-point query."""
    raw = get_source_credential(db, "xiaohongshu", "search_queries", None) if db else None
    queries: list[str] = json.loads(raw) if raw else DEFAULT_QUERIES
    from urllib.parse import quote

    return [f"{_XHS_SEARCH}?keyword={quote(q)}" for q in queries]


class XiaohongshuCollector(MultiBackendCollector):
    source_name = "xiaohongshu"

    CREDENTIAL_SCHEMA: ClassVar[list[dict]] = [
        {
            "key": "jina_fallback",
            "label": "Enable Jina Reader for 小红书",
            "secret": False,
            "optional": True,
            "help": "Set to 'true' to enable 小红书 pain-point discovery via Jina Reader (r.jina.ai). Without this the source is skipped. Get a Jina API key at jina.ai/reader for higher rate limits.",
        },
        {
            "key": "jina_api_key",
            "label": "Jina Reader API key (optional)",
            "secret": True,
            "optional": True,
            "help": "Optional — raises Jina rate limits.",
        },
        {
            "key": "search_queries",
            "label": "Search queries (JSON array)",
            "secret": False,
            "optional": True,
            "help": 'Chinese pain-point phrases, e.g. ["有没有工具","求推荐好用的"]',
        },
    ]

    def build_backends(self) -> list[SourceBackend]:
        return [JinaReaderBackend("xiaohongshu", _xhs_search_urls)]

    @classmethod
    def test_connection(cls, db: sqlite3.Connection, settings) -> tuple[bool, str]:
        if is_enabled(settings, db, "xiaohongshu"):
            return True, "小红书: Jina Reader enabled — will search for pain-point signals"
        return (
            True,
            "小红书: Jina Reader not enabled — source is skipped. Enable the jina_fallback credential in Settings → Data Sources.",
        )
