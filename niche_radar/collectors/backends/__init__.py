"""Cross-source capture backends (reusable across collectors).

Unlike ``x_backends/`` (Twitter-specific), these backends are generic capture
paths any source can compose into its :class:`MultiBackendCollector` chain.
"""

from __future__ import annotations

from niche_radar.collectors.backends.jina import JinaReaderBackend

__all__ = ["JinaReaderBackend"]
