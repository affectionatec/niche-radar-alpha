"""Cross-source capture backends (reusable across collectors).

Unlike ``x_backends/`` (Twitter-specific), these backends are generic capture
paths any source can compose into its :class:`MultiBackendCollector` chain.
"""

from __future__ import annotations

from niche_radar.collectors.backends.jina import JinaReaderBackend
from niche_radar.collectors.backends.ytdlp import YtDlpBackend

__all__ = ["JinaReaderBackend", "YtDlpBackend"]
