"""Instagram collector — ScrapeCreators reels search.

Pulls reel captions matching pain-point phrases. Ported from
last30days lib/instagram.py (v2 reels-search path).
"""

from __future__ import annotations

from niche_radar.collectors._scrapecreators import SC_BASE, ScrapeCreatorsCollector


class InstagramCollector(ScrapeCreatorsCollector):
    source_name = "instagram"
    platform = "instagram"

    def endpoint(self) -> str:
        return f"{SC_BASE}/v2/instagram/reels/search"

    def query_params(self, query: str) -> dict:
        return {"query": query}

    def extract_raw(self, data: dict) -> list[dict]:
        return data.get("reels") or data.get("items") or data.get("data") or []

    def parse_item(self, raw: dict, query: str) -> dict | None:
        if not isinstance(raw, dict):
            return None
        reel_pk = raw.get("id") or raw.get("pk")
        shortcode = raw.get("shortcode") or raw.get("code") or ""
        caption = raw.get("caption", "")
        if isinstance(caption, dict):
            text = caption.get("text", "")
        elif isinstance(caption, str):
            text = caption
        else:
            text = raw.get("desc") or raw.get("text") or ""
        owner = raw.get("owner") or raw.get("user")
        author = owner.get("username", "") if isinstance(owner, dict) else (owner or "")
        url = raw.get("url", "")
        if not url and shortcode:
            url = f"https://www.instagram.com/reel/{shortcode}"
        return self._item(
            source_id=reel_pk or shortcode,
            text=text,
            url=url,
            score=raw.get("like_count") or 0,
            comments=raw.get("comment_count") or 0,
            posted_raw=raw.get("taken_at") or raw.get("device_timestamp"),
            author=author,
            query=query,
        )
