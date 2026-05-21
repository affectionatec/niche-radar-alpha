"""G2 review collector — 1-2 star reviews as competitor complaint signals.

Scrapes g2.com/products/{slug}/reviews with rating filters. G2 uses Cloudflare;
this collector will return status=partial/failed when blocked and logs the error —
it never crashes the run.

Product slugs are configurable via /settings/sources/g2_reviews (JSON array).
"""

from __future__ import annotations

import json
import re
import sqlite3
import time
from datetime import datetime, timezone
from typing import ClassVar

import requests
import structlog
from tenacity import Retrying, stop_after_attempt, wait_exponential

from niche_radar.collectors.base import BaseCollector, CollectorResult, CollectorUnavailableError
from niche_radar.storage.repository import get_source_credential

logger = structlog.get_logger()

DEFAULT_PRODUCT_SLUGS = [
    "notion",
    "airtable",
    "zapier",
    "monday-com",
    "asana",
]

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


class G2ReviewsCollector(BaseCollector):
    source_name = "g2_reviews"

    CREDENTIAL_SCHEMA: ClassVar[list[dict]] = [
        {"key": "product_slugs", "label": "Product slugs (JSON array)", "secret": False, "optional": True,
         "help": 'From g2.com URLs, e.g. ["notion","airtable"]. Keep 5-20 slugs max.'},
    ]

    @classmethod
    def test_connection(cls, db: sqlite3.Connection, settings) -> tuple[bool, str]:
        import requests
        try:
            resp = requests.get("https://www.g2.com", headers=_HEADERS, timeout=10)
            if resp.status_code == 200:
                return True, "G2 reachable"
            if resp.status_code == 403:
                return False, "G2 blocked by Cloudflare (403) — scraping may fail"
            return False, f"HTTP {resp.status_code}"
        except Exception as exc:
            return False, str(exc)

    def collect(
        self, settings, dry_run: bool = False, db: sqlite3.Connection | None = None
    ) -> CollectorResult:
        start = time.perf_counter()
        if dry_run:
            return CollectorResult(self.source_name, [], "", "completed", 0)

        try:
            from bs4 import BeautifulSoup

            raw_slugs = (get_source_credential(db, "g2_reviews", "product_slugs", None) if db else None)
            slugs: list[str] = json.loads(raw_slugs) if raw_slugs else DEFAULT_PRODUCT_SLUGS

            retryer = Retrying(
                stop=stop_after_attempt(max(1, int(settings.max_retries or 1))),
                wait=wait_exponential(multiplier=2, min=3, max=60),
                reraise=True,
            )
            session = requests.Session()
            session.headers.update(_HEADERS)
            items: list[dict] = []
            errors: list[str] = []

            for slug in slugs:
                try:
                    url = (
                        f"https://www.g2.com/products/{slug}/reviews"
                        "?filters%5Brating%5D%5B%5D=1&filters%5Brating%5D%5B%5D=2"
                    )
                    for attempt in retryer:
                        with attempt:
                            resp = session.get(url, timeout=20)
                            if resp.status_code == 403:
                                raise CollectorUnavailableError(f"G2 Cloudflare block for {slug}")
                            if resp.status_code != 200:
                                raise CollectorUnavailableError(f"G2 returned {resp.status_code} for {slug}")

                    soup = BeautifulSoup(resp.text, "html.parser")

                    # G2 review cards vary in structure; try to find review containers
                    review_containers = (
                        soup.find_all(class_=re.compile(r"review", re.I)) or
                        soup.find_all("div", attrs={"itemprop": "review"})
                    )

                    for container in review_containers[:20]:
                        # Title
                        h_el = container.find(["h3", "h4", "h2"])
                        headline = h_el.get_text(strip=True) if h_el else ""

                        # Body text
                        p_els = container.find_all("p")
                        body = " ".join(p.get_text(strip=True) for p in p_els if len(p.get_text(strip=True)) > 20)
                        if not body:
                            continue

                        # Try to find a date
                        time_el = container.find("time") or container.find(class_=re.compile(r"date|time", re.I))
                        posted_raw = time_el.get("datetime") or time_el.get_text(strip=True) if time_el else None
                        posted_at = posted_raw or datetime.now(timezone.utc).isoformat()

                        # Unique ID from text hash
                        import hashlib
                        source_id = f"g2-{slug}-" + hashlib.md5(body[:100].encode()).hexdigest()[:8]

                        items.append({
                            "source_id": source_id,
                            "title": headline or f"1-2 star review of {slug}",
                            "body": body[:2000],
                            "url": url,
                            "score": 1,  # 1-2 star reviews
                            "comment_count": None,
                            "posted_at": posted_at,
                            "metadata": {
                                "product_slug": slug,
                                "review_type": "negative",
                                "g2_url": url,
                            },
                        })
                    time.sleep(1.0)  # polite delay between products
                except CollectorUnavailableError as exc:
                    logger.warning("g2_scrape_blocked", slug=slug, error=str(exc))
                    errors.append(str(exc))
                except Exception as exc:
                    logger.warning("g2_product_failed", slug=slug, error=str(exc))
                    errors.append(f"{slug}: {exc}")

            status = "completed" if not errors else "partial" if items else "failed"
            return CollectorResult(
                source=self.source_name, items=items, run_id="",
                status=status, items_collected=len(items),
                error_message="; ".join(errors) or None,
                duration_seconds=time.perf_counter() - start,
            )
        except Exception as exc:
            logger.exception("g2_collect_failed", error=str(exc))
            return CollectorResult(
                source=self.source_name, items=[], run_id="", status="failed",
                items_collected=0, error_message=str(exc),
                duration_seconds=time.perf_counter() - start,
            )
