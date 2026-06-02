"""Pluggable web-search backends for market validation (Phase 4).

Removes the hard dependency on a single search provider. A :class:`ChainSearcher`
tries configured API backends in priority order (Brave → Serper → …) and falls
back to a keyless terminal searcher (DuckDuckGo HTML, see ``web_validate``) when
none are configured or all error out. Mirrors last30days' grounding layer.

Keys are read from the environment so callers need no signature changes:
``BRAVE_API_KEY``, ``SERPER_API_KEY``. Adding Exa/Parallel is a new backend
class plus one line in :func:`get_searcher`.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Protocol

import structlog

from niche_radar.collectors import _http

logger = structlog.get_logger()


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str


class _Searcher(Protocol):
    def search(self, query: str) -> list[SearchResult]: ...


class WebSearchBackend(ABC):
    name: str = ""

    @abstractmethod
    def is_available(self) -> bool: ...

    @abstractmethod
    def search(self, query: str) -> list[SearchResult]: ...


class BraveBackend(WebSearchBackend):
    name = "brave"
    URL = "https://api.search.brave.com/res/v1/web/search"

    def _key(self) -> str | None:
        return os.environ.get("BRAVE_API_KEY")

    def is_available(self) -> bool:
        return bool(self._key())

    def search(self, query: str) -> list[SearchResult]:
        key = self._key()
        if not key:
            return []
        data = _http.get_json(
            self.URL,
            headers={"X-Subscription-Token": key, "Accept": "application/json"},
            params={"q": query, "count": 10},
            timeout=10, retries=2,
        )
        results = (data.get("web") or {}).get("results") or []
        return [
            SearchResult(title=r.get("title", ""), url=r.get("url", ""), snippet=r.get("description", ""))
            for r in results if r.get("url")
        ]


class SerperBackend(WebSearchBackend):
    name = "serper"
    URL = "https://google.serper.dev/search"

    def _key(self) -> str | None:
        return os.environ.get("SERPER_API_KEY")

    def is_available(self) -> bool:
        return bool(self._key())

    def search(self, query: str) -> list[SearchResult]:
        key = self._key()
        if not key:
            return []
        data = _http.post_json(
            self.URL,
            headers={"X-API-KEY": key, "Content-Type": "application/json"},
            json_body={"q": query, "num": 10},
            timeout=10, retries=2,
        )
        results = data.get("organic") or []
        return [
            SearchResult(title=r.get("title", ""), url=r.get("link", ""), snippet=r.get("snippet", ""))
            for r in results if r.get("link")
        ]


class ChainSearcher:
    """Try API backends in order, then a keyless fallback searcher."""

    def __init__(self, backends: list[WebSearchBackend], fallback: _Searcher | None = None):
        self._backends = backends
        self._fallback = fallback

    def search(self, query: str) -> list[SearchResult]:
        for backend in self._backends:
            try:
                if not backend.is_available():
                    continue
                results = backend.search(query)
                if results:
                    return results
            except Exception as exc:
                logger.warning("web_search_backend_failed", backend=backend.name, error=str(exc))
        if self._fallback is not None:
            return self._fallback.search(query)
        return []

    @property
    def active_backend(self) -> str:
        for backend in self._backends:
            try:
                if backend.is_available():
                    return backend.name
            except Exception:
                continue
        return "duckduckgo"


def get_searcher(ddg_fallback: _Searcher | None = None) -> ChainSearcher:
    """Build the validation searcher: API backends → keyless DDG fallback."""
    return ChainSearcher([BraveBackend(), SerperBackend()], fallback=ddg_fallback)
