"""Xiaoyuzhou (小宇宙) podcast collector — Jina Reader relay for pain-point discovery.

Per ADR-009: Agent-Reach's Whisper transcription recipe is rejected — Whisper is a
heavy dependency (~2 GB model, ffmpeg, audio storage) incompatible with the
project's unattended, dependency-light pipeline.  Instead, this collector reads
小宇宙 web pages through r.jina.ai, capturing podcast titles, show notes, and
episode descriptions as raw items.

小宇宙 is a JS-rendered SPA (every path returns the same 42 KB JS shell).
Jina Reader renders the JS and extracts the rendered page content — the same
pattern proven on Reddit (ADR-006), 小红书 (ADR-007), and LinkedIn (ADR-008).

Whisper transcription is deferred — it can be added as a ``SourceBackend``
inserted above the Jina tier later without refactoring the collector.

Opt-in only: the Jina tier never fires unless explicitly enabled (per-source
``jina_fallback`` credential or ``JINA_READER_ENABLED`` env var).
"""

from __future__ import annotations

import json
import sqlite3
from typing import ClassVar

from niche_radar.collectors._jina import is_enabled
from niche_radar.collectors.backends.jina import JinaReaderBackend
from niche_radar.collectors.multi_backend import MultiBackendCollector, SourceBackend
from niche_radar.storage.repository import get_source_credential

_XIAOYUZHOU = "https://www.xiaoyuzhoufm.com"

DEFAULT_QUERIES = [
    "创业",
    "效率工具",
    "副业",
    "独立开发者",
    "自动化",
    "出海",
    "SaaS",
    "AI 工具",
]


def _xiaoyuzhou_urls(settings, db: sqlite3.Connection | None) -> list[str]:
    """Build 小宇宙 search / discover URLs.

    Because 小宇宙 is an SPA, every path returns the same JS shell — Jina
    Reader renders the JS and extracts whatever content is visible for the
    given route.  We use:
      1. The homepage (trending podcasts)
      2. Pain-point search queries (the SPA resolves these client-side)
    """
    raw = get_source_credential(db, "xiaoyuzhou", "search_queries", None) if db else None
    queries: list[str] = json.loads(raw) if raw else DEFAULT_QUERIES
    from urllib.parse import quote

    urls = [_XIAOYUZHOU]
    for q in queries:
        urls.append(f"{_XIAOYUZHOU}/search?q={quote(q)}")
    return urls


class XiaoyuzhouCollector(MultiBackendCollector):
    source_name = "xiaoyuzhou"

    CREDENTIAL_SCHEMA: ClassVar[list[dict]] = [
        {
            "key": "jina_fallback",
            "label": "Enable Jina Reader for 小宇宙",
            "secret": False,
            "optional": True,
            "help": "Set to 'true' to enable 小宇宙 podcast discovery via Jina Reader (r.jina.ai). Without this the source is skipped. 小宇宙 is a JS SPA — Jina renders the JS to extract podcast titles and show notes.",
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
            "help": 'Chinese podcast search terms, e.g. ["创业","效率工具","副业"]',
        },
    ]

    def build_backends(self) -> list[SourceBackend]:
        return [JinaReaderBackend("xiaoyuzhou", _xiaoyuzhou_urls)]

    @classmethod
    def test_connection(cls, db: sqlite3.Connection, settings) -> tuple[bool, str]:
        if is_enabled(settings, db, "xiaoyuzhou"):
            return True, "小宇宙: Jina Reader enabled — will capture podcast metadata (titles, show notes, descriptions)"
        return (
            True,
            "小宇宙: Jina Reader not enabled — source is skipped. Enable the jina_fallback credential in Settings → Data Sources to capture Chinese podcast content.",
        )
