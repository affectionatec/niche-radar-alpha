"""TikTok collector — ScrapeCreators keyword search.

Pulls video captions matching pain-point phrases. Ported from
last30days lib/tiktok.py (keyword-search path).
"""

from __future__ import annotations

from niche_radar.collectors._scrapecreators import SC_BASE, ScrapeCreatorsCollector


class TikTokCollector(ScrapeCreatorsCollector):
    source_name = "tiktok"
    platform = "tiktok"

    def endpoint(self) -> str:
        return f"{SC_BASE}/v1/tiktok/search/keyword"

    def query_params(self, query: str) -> dict:
        return {"query": query, "sort_by": "relevance"}

    def extract_raw(self, data: dict) -> list[dict]:
        entries = data.get("search_item_list") or data.get("data") or []
        out = []
        for entry in entries:
            if isinstance(entry, dict):
                out.append(entry.get("aweme_info", entry))
        return out

    def parse_item(self, raw: dict, query: str) -> dict | None:
        video_id = raw.get("aweme_id")
        stats = raw.get("statistics") if isinstance(raw.get("statistics"), dict) else {}
        author_raw = raw.get("author")
        author = author_raw.get("unique_id", "") if isinstance(author_raw, dict) else (author_raw or "")
        url = (raw.get("share_url") or "").split("?")[0]
        if not url and author and video_id:
            url = f"https://www.tiktok.com/@{author}/video/{video_id}"
        likes = stats.get("digg_count") or 0
        shares = stats.get("share_count") or 0
        return self._item(
            source_id=video_id,
            text=raw.get("desc", ""),
            url=url,
            score=likes + shares,
            comments=stats.get("comment_count") or 0,
            posted_raw=raw.get("create_time"),
            author=author,
            query=query,
        )
