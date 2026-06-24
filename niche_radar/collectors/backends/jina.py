"""Jina Reader source backend — a resilient, opt-in page-reading fallback.

Composed per source with a ``urls`` function (which target pages to read) and a
``parse`` function (Markdown → raw items); defaults to one document item per URL
via :func:`niche_radar.collectors._jina.page_to_items`. No per-source subclass
needed — see :mod:`niche_radar.collectors._jina` for the rationale.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable

import structlog

from niche_radar.collectors import _jina
from niche_radar.collectors.multi_backend import SourceBackend

logger = structlog.get_logger()

UrlsFn = Callable[[object, "sqlite3.Connection | None"], list[str]]
ParseFn = Callable[[str, str], list[dict]]


class JinaReaderBackend(SourceBackend):
    """Read a source's target URLs through Jina Reader and normalize the result.

    Availability is opt-in (``_jina.is_enabled``) so it never makes surprise
    outbound calls. ``fetch`` returns partial items if *some* URLs succeed, and
    raises only when it captured nothing *and* hit errors (so the chain records
    the failure and falls through / fails honestly).
    """

    name = "jina_reader"

    def __init__(self, source: str, urls: UrlsFn, parse: ParseFn | None = None):
        self.source = source
        self._urls = urls
        self._parse = parse or (lambda md, url: _jina.page_to_items(md, url, source))

    def is_available(self, settings, db: sqlite3.Connection | None) -> bool:
        return _jina.is_enabled(settings, db, self.source)

    def fetch(self, settings, db: sqlite3.Connection | None) -> list[dict]:
        items: list[dict] = []
        errors: list[str] = []
        for url in self._urls(settings, db):
            try:
                markdown = _jina.read_url(url, settings, db, self.source)
            except Exception as exc:
                logger.warning("jina_read_failed", source=self.source, url=_jina._http.redact(url), error=str(exc))
                errors.append(f"{url}: {exc}")
                continue
            items.extend(self._parse(markdown, url))
        if not items and errors:
            raise RuntimeError("jina_reader captured nothing: " + "; ".join(errors))
        return items
