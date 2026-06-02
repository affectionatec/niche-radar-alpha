"""Multi-backend collector base — an availability-gated fallback chain.

Generalises the ``last30days`` engine's per-source backend selection
(``env.get_x_source`` picks xAI → Bird → xurl in priority order) so that *any*
Niche Radar source can be served by an ordered list of interchangeable
backends. The collector walks the chain in priority order, using the first
backend that is *available* (has its credentials / binaries) and returns a
non-empty result; if a backend is unavailable, errors, or returns nothing, it
falls through to the next.

This is what turns a single brittle capture path (today's X collector) into a
resilient source: one backend breaking no longer takes the whole source down.
"""

from __future__ import annotations

import sqlite3
import time
from abc import ABC, abstractmethod

import structlog

from niche_radar.collectors.base import BaseCollector, CollectorResult

logger = structlog.get_logger()


class SourceBackend(ABC):
    """One interchangeable capture path for a source.

    Implementations should be cheap to construct and must not raise from
    :meth:`is_available`. :meth:`fetch` returns normalized raw-item dicts (the
    same shape collectors hand to ``upsert_raw_item``) and may return an empty
    list to signal "available but nothing found" — that triggers fallthrough to
    the next backend.
    """

    name: str = ""

    @abstractmethod
    def is_available(self, settings, db: sqlite3.Connection | None) -> bool:
        """Return True when this backend's credentials / dependencies are present."""
        ...

    @abstractmethod
    def fetch(self, settings, db: sqlite3.Connection | None) -> list[dict]:
        """Capture items. Return [] for 'nothing found'; raise to signal failure."""
        ...


class MultiBackendCollector(BaseCollector):
    """A collector backed by an ordered chain of :class:`SourceBackend`.

    Subclasses set ``source_name`` and provide ``build_backends()`` returning
    the priority-ordered backend instances. The first available backend that
    yields items wins; per-backend outcomes are recorded in
    ``CollectorResult.metadata['backends']`` for dashboard observability.
    """

    def build_backends(self) -> list[SourceBackend]:
        """Return the priority-ordered backend chain. Override in subclasses."""
        raise NotImplementedError

    @classmethod
    def is_available(cls, db: sqlite3.Connection | None, settings) -> bool:
        """True when at least one backend in the chain is available."""
        try:
            inst = cls()
            return any(b.is_available(settings, db) for b in inst.build_backends())
        except Exception:
            return False

    def collect(
        self, settings, dry_run: bool = False, db: sqlite3.Connection | None = None
    ) -> CollectorResult:
        start = time.perf_counter()
        if dry_run:
            return CollectorResult(self.source_name, [], "", "completed", 0)

        backends = self.build_backends()
        attempts: list[dict] = []
        errors: list[str] = []

        for backend in backends:
            available = False
            try:
                available = backend.is_available(settings, db)
            except Exception as exc:  # is_available must never blow up the chain
                logger.warning("backend_availability_check_failed", source=self.source_name,
                               backend=backend.name, error=str(exc))
            if not available:
                attempts.append({"backend": backend.name, "status": "unavailable"})
                continue

            try:
                items = backend.fetch(settings, db)
            except Exception as exc:
                logger.warning("backend_fetch_failed", source=self.source_name,
                               backend=backend.name, error=str(exc))
                errors.append(f"{backend.name}: {exc}")
                attempts.append({"backend": backend.name, "status": "error", "error": str(exc)})
                continue

            attempts.append({"backend": backend.name, "status": "ok", "items": len(items)})
            if items:
                logger.info("backend_succeeded", source=self.source_name,
                            backend=backend.name, items=len(items))
                return CollectorResult(
                    source=self.source_name, items=items, run_id="",
                    status="completed", items_collected=len(items),
                    error_message="; ".join(errors) or None,
                    duration_seconds=time.perf_counter() - start,
                    metadata={"backends": attempts, "active_backend": backend.name},
                )

        # No backend produced items.
        any_available = any(a["status"] != "unavailable" for a in attempts)
        status = "partial" if any_available else "failed"
        message = (
            "; ".join(errors)
            or ("all backends returned no items" if any_available
                else "no backend available — configure credentials in Settings → Data Sources")
        )
        return CollectorResult(
            source=self.source_name, items=[], run_id="", status=status,
            items_collected=0, error_message=message,
            duration_seconds=time.perf_counter() - start,
            metadata={"backends": attempts, "active_backend": None},
        )
