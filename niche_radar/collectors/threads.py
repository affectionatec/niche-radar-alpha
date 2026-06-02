"""Threads collector — ScrapeCreators search.

Pulls Threads posts matching pain-point phrases. Threads is text-first, so it
is the strongest pain-point fit of the ScrapeCreators family. Ported from
last30days lib/threads.py.
"""

from __future__ import annotations

from niche_radar.collectors._scrapecreators import SC_BASE, ScrapeCreatorsCollector


class ThreadsCollector(ScrapeCreatorsCollector):
    source_name = "threads"
    platform = "threads"

    def endpoint(self) -> str:
        return f"{SC_BASE}/v1/threads/search"

    def query_params(self, query: str) -> dict:
        return {"keyword": query}

    def extract_raw(self, data: dict) -> list[dict]:
        return (
            data.get("items") or data.get("data") or data.get("threads")
            or data.get("posts") or data.get("search_results") or []
        )

    def parse_item(self, raw: dict, query: str) -> dict | None:
        if not isinstance(raw, dict):
            return None
        post_id = raw.get("id") or raw.get("pk") or raw.get("code")
        text = raw.get("text") or raw.get("caption") or raw.get("content") or ""
        if isinstance(text, dict):
            text = text.get("text", "")
        user = raw.get("user") or raw.get("author") or {}
        author = (user.get("username") or user.get("handle") or "") if isinstance(user, dict) else (user or "")
        code = raw.get("code") or raw.get("shortcode") or ""
        url = raw.get("url") or raw.get("share_url") or ""
        if not url and code:
            url = f"https://www.threads.net/post/{code}"
        elif not url and author and post_id:
            url = f"https://www.threads.net/@{author}/post/{post_id}"
        likes = raw.get("like_count") or raw.get("likes") or 0
        reposts = raw.get("repost_count") or raw.get("reposts") or 0
        return self._item(
            source_id=post_id,
            text=text,
            url=url,
            score=likes + reposts,
            comments=raw.get("reply_count") or raw.get("replies") or 0,
            posted_raw=raw.get("taken_at") or raw.get("published_on") or raw.get("created_at"),
            author=author,
            query=query,
        )
