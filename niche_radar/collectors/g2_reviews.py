"""G2 review collector — 1-2 star reviews as competitor-complaint signals.

Resilient multi-backend source (ADR-002). Capture walks an ordered chain:

    1. direct_scrape  — g2.com/products/{slug}/reviews with rating filters
    2. jina_reader    — opt-in r.jina.ai fallback when the direct scrape is
                        Cloudflare-blocked (captures the readable reviews page)

G2 uses Cloudflare, so the direct path is brittle; enable the Jina fallback
(``jina_fallback`` / ``jina_api_key``) from Settings → Data Sources → G2 to keep
the source alive when direct scraping is blocked. The collector never crashes
the run — a fully blocked source returns status partial/failed.

Product slugs are configurable via /settings/sources/g2_reviews (JSON array).
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
from datetime import datetime, timezone
from typing import ClassVar

import requests
import structlog
from tenacity import Retrying, stop_after_attempt, wait_exponential

from niche_radar.collectors.backends import JinaReaderBackend
from niche_radar.collectors.base import CollectorUnavailableError
from niche_radar.collectors.multi_backend import MultiBackendCollector, SourceBackend
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

_JINA_CREDENTIALS: list[dict] = [
    {"key": "jina_fallback", "label": "Enable Jina Reader fallback", "secret": False, "optional": True,
     "help": "When the direct G2 scrape is Cloudflare-blocked, read pages via r.jina.ai. Set to 'true' to enable."},
    {"key": "jina_api_key", "label": "Jina Reader API key (optional)", "secret": True, "optional": True,
     "help": "Optional — raises Jina rate limits and enables the fallback on its own. Get one at jina.ai/reader."},
]


def _slugs(db: sqlite3.Connection | None) -> list[str]:
    raw = get_source_credential(db, "g2_reviews", "product_slugs", None) if db else None
    return json.loads(raw) if raw else DEFAULT_PRODUCT_SLUGS


def _review_url(slug: str) -> str:
    return (
        f"https://www.g2.com/products/{slug}/reviews"
        "?filters%5Brating%5D%5B%5D=1&filters%5Brating%5D%5B%5D=2"
    )


class G2DirectScrapeBackend(SourceBackend):
    """Primary path — direct HTML scrape of G2 review pages (Cloudflare-brittle)."""

    name = "direct_scrape"

    def is_available(self, settings, db: sqlite3.Connection | None) -> bool:
        return True  # keyless; degrades to fallthrough when blocked

    def fetch(self, settings, db: sqlite3.Connection | None) -> list[dict]:
        from bs4 import BeautifulSoup

        slugs = _slugs(db)
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
                url = _review_url(slug)
                for attempt in retryer:
                    with attempt:
                        resp = session.get(url, timeout=20)
                        if resp.status_code == 403:
                            raise CollectorUnavailableError(f"G2 Cloudflare block for {slug}")
                        if resp.status_code != 200:
                            raise CollectorUnavailableError(f"G2 returned {resp.status_code} for {slug}")

                soup = BeautifulSoup(resp.text, "html.parser")
                review_containers = (
                    soup.find_all(class_=re.compile(r"review", re.I)) or
                    soup.find_all("div", attrs={"itemprop": "review"})
                )

                for container in review_containers[:20]:
                    h_el = container.find(["h3", "h4", "h2"])
                    headline = h_el.get_text(strip=True) if h_el else ""
                    p_els = container.find_all("p")
                    body = " ".join(p.get_text(strip=True) for p in p_els if len(p.get_text(strip=True)) > 20)
                    if not body:
                        continue
                    time_el = container.find("time") or container.find(class_=re.compile(r"date|time", re.I))
                    posted_raw = time_el.get("datetime") or time_el.get_text(strip=True) if time_el else None
                    posted_at = posted_raw or datetime.now(timezone.utc).isoformat()
                    source_id = f"g2-{slug}-" + hashlib.md5(body[:100].encode()).hexdigest()[:8]
                    items.append({
                        "source_id": source_id,
                        "title": headline or f"1-2 star review of {slug}",
                        "body": body[:2000],
                        "url": url,
                        "score": 1,
                        "comment_count": None,
                        "posted_at": posted_at,
                        "metadata": {"product_slug": slug, "review_type": "negative", "g2_url": url},
                    })
                time.sleep(1.0)  # polite delay between products
            except CollectorUnavailableError as exc:
                logger.warning("g2_scrape_blocked", slug=slug, error=str(exc))
                errors.append(str(exc))
            except Exception as exc:
                logger.warning("g2_product_failed", slug=slug, error=str(exc))
                errors.append(f"{slug}: {exc}")

        # Nothing captured and the page actively blocked us → signal failure so
        # the chain falls through to the Jina fallback (if enabled).
        if not items and errors:
            raise CollectorUnavailableError("; ".join(errors))
        return items


class G2ReviewsCollector(MultiBackendCollector):
    source_name = "g2_reviews"

    CREDENTIAL_SCHEMA: ClassVar[list[dict]] = [
        {"key": "product_slugs", "label": "Product slugs (JSON array)", "secret": False, "optional": True,
         "help": 'From g2.com URLs, e.g. ["notion","airtable"]. Keep 5-20 slugs max.'},
        *_JINA_CREDENTIALS,
    ]

    def build_backends(self) -> list[SourceBackend]:
        return [
            G2DirectScrapeBackend(),
            JinaReaderBackend("g2_reviews", lambda settings, db: [_review_url(s) for s in _slugs(db)]),
        ]

    @classmethod
    def test_connection(cls, db: sqlite3.Connection, settings) -> tuple[bool, str]:
        try:
            resp = requests.get("https://www.g2.com", headers=_HEADERS, timeout=10)
            if resp.status_code == 200:
                return True, "G2 reachable (direct scrape)"
            if resp.status_code == 403:
                from niche_radar.collectors import _jina
                if _jina.is_enabled(settings, db, "g2_reviews"):
                    return True, "G2 blocked by Cloudflare (403) — Jina Reader fallback is enabled"
                return False, "G2 blocked by Cloudflare (403) — enable the Jina Reader fallback to keep this source alive"
            return False, f"HTTP {resp.status_code}"
        except Exception as exc:
            return False, str(exc)
