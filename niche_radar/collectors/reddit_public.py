"""Keyless Reddit search via the public JSON endpoints.

Fallback for the PRAW-based RedditCollector: when no Reddit API credentials are
configured (or PRAW fails at runtime), Reddit's public ``/search.json`` still
returns the same submissions with only a descriptive User-Agent. Ported in
spirit from last30days' reddit_public path.
"""

from __future__ import annotations

from datetime import datetime, timezone

import structlog

from niche_radar.collectors import _http

logger = structlog.get_logger()

_SEARCH_URL = "https://www.reddit.com/r/{subs}/search.json"
_UA = "niche-radar/0.1 (public-json fallback; +https://github.com/affectionatec/niche-radar-alpha)"


def search_public(
    subreddits: list[str],
    queries: list[str],
    cutoff: datetime,
    limit: int = 100,
) -> tuple[list[dict], list[str]]:
    """Run each query against the public Reddit search JSON across ``subreddits``.

    Returns ``(items, errors)`` where items match the PRAW collector's raw-item
    shape so they flow through the rest of the pipeline unchanged.
    """
    subs = "+".join(subreddits)
    url = _SEARCH_URL.format(subs=subs)
    items: dict[str, dict] = {}
    errors: list[str] = []

    for query in queries:
        try:
            data = _http.get_json(
                url,
                headers={"User-Agent": _UA},
                params={
                    "q": query,
                    "restrict_sr": "1",
                    "sort": "new",
                    "t": "week",
                    "limit": str(limit),
                },
                timeout=20, retries=2,
            )
            for child in (data.get("data", {}).get("children") or []):
                post = child.get("data") or {}
                sid = post.get("id")
                if not sid:
                    continue
                if sid in items:
                    items[sid]["metadata"]["matched_queries"].append(query)
                    continue
                created = datetime.fromtimestamp(post.get("created_utc", 0), tz=timezone.utc)
                if created < cutoff:
                    continue
                permalink = post.get("permalink") or ""
                items[sid] = {
                    "source_id": str(sid),
                    "title": post.get("title") or "",
                    "body": post.get("selftext") or None,
                    "url": f"https://www.reddit.com{permalink}" if permalink else post.get("url"),
                    "score": int(post.get("score") or 0),
                    "comment_count": int(post.get("num_comments") or 0),
                    "posted_at": created.isoformat(),
                    "metadata": {
                        "subreddit": post.get("subreddit"),
                        "author": post.get("author"),
                        "post_flair": post.get("link_flair_text"),
                        "external_url": post.get("url"),
                        "matched_queries": [query],
                        "has_pain_point_signal": True,
                        "auth_mode": "public_json",
                    },
                }
        except Exception as exc:
            logger.warning("reddit_public_query_failed", query=query, error=str(exc))
            errors.append(f"public query '{query}': {exc}")

    return list(items.values()), errors
