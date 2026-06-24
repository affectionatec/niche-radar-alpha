"""Jina Reader capture helper — a resilient, keyless page-reading fallback.

[Jina Reader](https://jina.ai/reader/) (`https://r.jina.ai/<url>`) fetches a web
page through a relay that renders it and returns clean Markdown — bypassing the
brittle, Cloudflare-blockable direct HTML scraping that fragile sources (G2,
Indie Hackers, …) rely on. It is the resilient *fallback* backend those sources
fall through to when their primary direct-scrape path is blocked.

Design notes:
- **Opt-in.** Reaching a third-party relay is the operator's choice, so the
  fallback is only *available* when explicitly enabled — per source via a
  ``jina_fallback`` credential (or a configured ``jina_api_key``), or globally
  via the ``JINA_READER_ENABLED`` env var. This keeps unattended runs (and the
  test-suite) from making surprise outbound calls.
- **No bespoke HTTP.** Reads go through :mod:`niche_radar.collectors._http`, so
  they inherit retries, 429 handling, and secret redaction.
- **Honest fallback.** When a structured scrape is blocked, the readable page
  content is captured as a *single document* raw item per URL (title + Markdown
  body) for the A1/A2 agents to mine — rather than fabricating per-review
  structure from generic Markdown.
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
from datetime import datetime, timezone

import structlog

from niche_radar.collectors import _http

logger = structlog.get_logger()

JINA_READER_BASE = "https://r.jina.ai/"
_TRUTHY = {"1", "true", "yes", "on"}


def _get_credential(db: sqlite3.Connection | None, source: str, key: str):
    """Read a per-source credential without hard-importing storage at module load."""
    if db is None or not source:
        return None
    try:
        from niche_radar.storage.repository import get_source_credential

        return get_source_credential(db, source, key, None)
    except Exception:  # storage shape varies in tests; never break availability
        return None


def api_key(db: sqlite3.Connection | None, source: str) -> str | None:
    """Optional Jina API key (raises rate limits); None means keyless access."""
    return _get_credential(db, source, "jina_api_key") or os.getenv("JINA_API_KEY") or None


def is_enabled(settings, db: sqlite3.Connection | None, source: str) -> bool:
    """Whether the Jina fallback is opted into for ``source``.

    Never raises — availability checks must not break the collector chain.
    """
    try:
        flag = _get_credential(db, source, "jina_fallback")
        if isinstance(flag, str) and flag.strip().lower() in _TRUTHY:
            return True
        if flag is True:
            return True
        if api_key(db, source):
            return True
        return os.getenv("JINA_READER_ENABLED", "").strip().lower() in _TRUTHY
    except Exception:
        return False


def read_url(
    target_url: str,
    settings=None,
    db: sqlite3.Connection | None = None,
    source: str = "",
    *,
    timeout: int = _http.DEFAULT_TIMEOUT,
) -> str:
    """Fetch ``target_url`` through Jina Reader, returning Markdown text.

    Raises :class:`niche_radar.collectors._http.HTTPError` on failure so the
    caller can record it and fall through.
    """
    headers = {"Accept": "text/markdown", "X-Return-Format": "markdown"}
    key = api_key(db, source)
    if key:
        headers["Authorization"] = f"Bearer {key}"
    return _http.request(
        "GET", JINA_READER_BASE + target_url, headers=headers, raw=True, timeout=timeout
    )


def _first_heading(markdown: str) -> str | None:
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
        if stripped.lower().startswith("title:"):
            return stripped.split(":", 1)[1].strip()
    return None


def page_to_items(markdown: str, url: str, source: str, *, max_body: int = 4000) -> list[dict]:
    """Normalize a Jina Markdown page into a single document raw item.

    Returns ``[]`` for an empty page (triggers fallthrough). The ``source_id`` is
    deterministic (hash of URL + content head) so re-ingestion dedupes.
    """
    text = (markdown or "").strip()
    if not text:
        return []
    title = _first_heading(text) or f"{source} page"
    digest = hashlib.md5((url + text[:200]).encode()).hexdigest()[:10]
    return [
        {
            "source_id": f"{source}-jina-{digest}",
            "title": title[:200],
            "body": text[:max_body],
            "url": url,
            "score": 0,
            "comment_count": None,
            "posted_at": datetime.now(timezone.utc).isoformat(),
            "metadata": {"capture": "jina_reader", "source_url": url},
        }
    ]
