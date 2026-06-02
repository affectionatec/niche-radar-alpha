"""X / Twitter capture backends — an ordered, interchangeable fallback chain.

Each backend is a :class:`~niche_radar.collectors.multi_backend.SourceBackend`
that searches X a different way:

- :class:`~niche_radar.collectors.x_backends.xai.XaiBackend` — xAI live X
  search (API key, zero scraping, most stable).
- :class:`~niche_radar.collectors.x_backends.xquik.XquikBackend` — Xquik REST
  API (API key, full engagement metrics).
- :class:`~niche_radar.collectors.x_backends.graphql_cookie.GraphQLCookieBackend`
  — the legacy internal-GraphQL path with cookie auth, demoted to last resort.

``TwitterCollector`` wires them into a :class:`MultiBackendCollector` so one
broken path no longer takes the whole source down.
"""

from niche_radar.collectors.x_backends.base import (
    DEFAULT_SEARCH_QUERIES,
    ParsedTweet,
    XBackend,
)
from niche_radar.collectors.x_backends.graphql_cookie import GraphQLCookieBackend
from niche_radar.collectors.x_backends.xai import XaiBackend
from niche_radar.collectors.x_backends.xquik import XquikBackend

__all__ = [
    "DEFAULT_SEARCH_QUERIES",
    "ParsedTweet",
    "XBackend",
    "XaiBackend",
    "XquikBackend",
    "GraphQLCookieBackend",
]
