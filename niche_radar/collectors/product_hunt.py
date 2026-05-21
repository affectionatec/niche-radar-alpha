"""Product Hunt collector — scrape feature-request signals from comments.

Targets producthunt.com/posts (sorted by votes) and filters comments containing
phrases that signal unmet needs ("wish", "missing", "should also", "would pay", etc.).
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import ClassVar

import structlog
from tenacity import Retrying, stop_after_attempt, wait_exponential

from niche_radar.collectors.base import (
    BaseCollector,
    CollectorResult,
    CollectorUnavailableError,
)

logger = structlog.get_logger()

PAIN_PHRASES = ["wish", "missing", "should also", "would pay", "doesn't have", "can't do", "no way to", "lacks", "please add"]
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml",
}


class ProductHuntCollector(BaseCollector):
    source_name = "product_hunt"

    CREDENTIAL_SCHEMA: ClassVar[list[dict]] = [
        {"key": "api_token", "label": "PH API Token (optional)", "secret": True, "optional": True,
         "help": "From api.producthunt.com — free 5k calls/day. Anonymous scrape used without it."},
    ]

    @classmethod
    def test_connection(cls, db, settings) -> tuple[bool, str]:
        import requests
        try:
            resp = requests.get("https://www.producthunt.com/posts", headers=_HEADERS, timeout=10)
            if resp.status_code == 200:
                return True, "Product Hunt reachable"
            return False, f"HTTP {resp.status_code} — may be Cloudflare-blocked"
        except Exception as exc:
            return False, str(exc)

    def collect(self, settings, dry_run: bool = False, db=None) -> CollectorResult:
        start = time.perf_counter()
        if dry_run:
            return CollectorResult(self.source_name, [], "", "completed", 0)

        try:
            import requests
            from bs4 import BeautifulSoup

            retryer = Retrying(
                stop=stop_after_attempt(max(1, int(settings.max_retries or 1))),
                wait=wait_exponential(multiplier=1, min=2, max=30),
                reraise=True,
            )
            cutoff = datetime.now(timezone.utc) - timedelta(hours=48)  # PH posts age quickly
            items: list[dict] = []
            errors: list[str] = []

            # Fetch today's trending posts
            for attempt in retryer:
                with attempt:
                    resp = requests.get(
                        "https://www.producthunt.com/posts",
                        headers=_HEADERS,
                        timeout=20,
                    )
                    if resp.status_code != 200:
                        raise CollectorUnavailableError(f"Product Hunt returned {resp.status_code}")

            soup = BeautifulSoup(resp.text, "html.parser")
            # PH renders SSR with product cards; each has a data-test attribute or consistent class
            post_links = []
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if href.startswith("/posts/") and href.count("/") == 2:
                    post_links.append(href)
            post_links = list(dict.fromkeys(post_links))[:20]  # up to 20 posts, deduped

            if not post_links:
                logger.warning("product_hunt_no_posts_found")
                return CollectorResult(
                    source=self.source_name, items=[], run_id="", status="partial",
                    items_collected=0, error_message="No post links parsed from Product Hunt",
                    duration_seconds=time.perf_counter() - start,
                )

            for post_path in post_links:
                try:
                    slug = post_path.rstrip("/").split("/")[-1]
                    post_url = f"https://www.producthunt.com{post_path}"
                    for attempt in retryer:
                        with attempt:
                            post_resp = requests.get(post_url, headers=_HEADERS, timeout=20)
                            if post_resp.status_code != 200:
                                raise CollectorUnavailableError(f"Post page {post_url} returned {post_resp.status_code}")
                    post_soup = BeautifulSoup(post_resp.text, "html.parser")

                    # Extract product name + tagline
                    title_el = post_soup.find("h1")
                    product_name = title_el.get_text(strip=True) if title_el else slug
                    tagline_el = post_soup.find("h2")
                    tagline = tagline_el.get_text(strip=True) if tagline_el else ""

                    # Upvotes — look for a vote button or count text
                    vote_text = ""
                    for el in post_soup.find_all(string=True):
                        import re
                        if re.match(r"^\d{1,5}$", el.strip() or ""):
                            vote_text = el.strip()
                            break
                    upvotes = int(vote_text) if vote_text.isdigit() else 0

                    # Collect matching comments
                    matching_comments: list[str] = []
                    for comment_el in post_soup.find_all(class_=lambda c: c and "comment" in c.lower()):
                        text = comment_el.get_text(" ", strip=True).lower()
                        if any(phrase in text for phrase in PAIN_PHRASES):
                            matching_comments.append(comment_el.get_text(" ", strip=True)[:500])

                    if not matching_comments:
                        continue

                    body = "\n\n".join(matching_comments[:5])
                    items.append({
                        "source_id": slug,
                        "title": product_name,
                        "body": body,
                        "url": post_url,
                        "score": upvotes,
                        "comment_count": len(matching_comments),
                        "posted_at": datetime.now(timezone.utc).isoformat(),
                        "metadata": {
                            "tagline": tagline,
                            "matched_phrases": [p for p in PAIN_PHRASES if p in body.lower()],
                            "comment_count_matched": len(matching_comments),
                        },
                    })
                    time.sleep(0.5)  # polite delay between post page fetches
                except Exception as exc:
                    logger.warning("product_hunt_post_failed", post=post_path, error=str(exc))
                    errors.append(f"{post_path}: {exc}")

            status = "completed" if not errors else "partial" if items else "failed"
            return CollectorResult(
                source=self.source_name, items=items, run_id="",
                status=status, items_collected=len(items),
                error_message="; ".join(errors) or None,
                duration_seconds=time.perf_counter() - start,
            )
        except Exception as exc:
            logger.exception("product_hunt_collect_failed", error=str(exc))
            return CollectorResult(
                source=self.source_name, items=[], run_id="", status="failed",
                items_collected=0, error_message=str(exc),
                duration_seconds=time.perf_counter() - start,
            )
