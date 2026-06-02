"""Base collector interface and shared types."""

from __future__ import annotations

import sqlite3
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar


@dataclass
class CollectorResult:
    """Normalized result from any data source collector."""

    source: str
    items: list[dict]
    run_id: str
    status: str  # 'completed' | 'partial' | 'failed'
    items_collected: int
    error_message: str | None = None
    duration_seconds: float = 0.0
    # Optional diagnostics (e.g. per-backend outcomes for multi-backend
    # sources). Not persisted as raw-item data; surfaced for observability.
    metadata: dict | None = None


class CollectorUnavailableError(Exception):
    """Raised when a source is unreachable after retries."""


class BaseCollector(ABC):
    """Abstract base class for data source collectors.

    Subclasses must define:
    - `source_name: str`
    - `CREDENTIAL_SCHEMA: list[dict]` — each entry: {key, label, secret, optional, help}
    - `collect(settings, dry_run, db)` — main collection method
    - `test_connection(db, settings)` — classmethod for testing auth (optional override)
    """

    source_name: str = ""

    CREDENTIAL_SCHEMA: ClassVar[list[dict]] = []
    # Each entry: {"key": str, "label": str, "secret": bool, "optional": bool, "help": str}

    @abstractmethod
    def collect(
        self, settings, dry_run: bool = False, db: sqlite3.Connection | None = None
    ) -> CollectorResult:
        """Fetch data from the source and return a CollectorResult."""
        ...

    @classmethod
    def is_available(cls, db: sqlite3.Connection | None, settings) -> bool:
        """Whether this source can run given current credentials / dependencies.

        The collection runner skips (rather than fails) sources that report
        unavailable, so credential-gated sources stay silent until configured.
        Defaults to True — sources that always work (keyless, or that degrade
        gracefully inside ``collect``) need not override this.
        """
        return True

    @classmethod
    def test_connection(
        cls, db: sqlite3.Connection, settings
    ) -> tuple[bool, str]:
        """Test whether credentials are valid. Returns (ok, message)."""
        return True, "no connection test implemented for this source"
