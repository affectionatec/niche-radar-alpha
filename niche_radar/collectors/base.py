"""Base collector interface and shared types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


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


class CollectorUnavailableError(Exception):
    """Raised when a source is unreachable after retries."""


class BaseCollector(ABC):
    """Abstract base class for data source collectors."""

    source_name: str = ""

    @abstractmethod
    def collect(self, settings, dry_run: bool = False) -> CollectorResult:
        """Fetch data from the source and return a CollectorResult."""
        ...
