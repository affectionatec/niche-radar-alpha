"""Indie Hackers collector — validated niche signals from revenue-generating products.

Resilient multi-backend source (ADR-002). Capture walks an ordered chain:

    1. direct_scrape  — indiehackers.com/products sorted by revenue
    2. jina_reader    — opt-in r.jina.ai fallback when the direct scrape is
                        blocked (captures the readable products page)

Each product entry validates that a niche has paying customers — useful for the
web validation pipeline. The collector never crashes the run; a fully blocked
source returns status partial/failed. Enable the Jina fallback
(``jina_fallback`` / ``jina_api_key``) from Settings → Data Sources.
"""

from __future__ import annotations

import hashlib
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

logger = structlog.get_logger()

_PRODUCTS_URL = "https://www.indiehackers.com/products?sortBy=revenue&revenueVerification=stripe"

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml",
}

_JINA_CREDENTIALS: list[dict] = [
    {"key": "jina_fallback", "label": "Enable Jina Reader fallback", "secret": False, "optional": True,
     "help": "When the direct Indie Hackers scrape is blocked, read pages via r.jina.ai. Set to 'true' to enable."},
    {"key": "jina_api_key", "label": "Jina Reader API key (optional)", "secret": True, "optional": True,
     "help": "Optional — raises Jina rate limits and enables the fallback on its own. Get one at jina.ai/reader."},
]


class IndieHackersDirectScrapeBackend(SourceBackend):
    """Primary path — direct HTML scrape of the Indie Hackers products page."""

    name = "direct_scrape"

    def is_available(self, settings, db: sqlite3.Connection | None) -> bool:
        return True  # keyless; degrades to fallthrough when blocked

    def fetch(self, settings, db: sqlite3.Connection | None) -> list[dict]:
        from bs4 import BeautifulSoup

        retryer = Retrying(
            stop=stop_after_attempt(max(1, int(settings.max_retries or 1))),
            wait=wait_exponential(multiplier=2, min=3, max=60),
            reraise=True,
        )
        for attempt in retryer:
            with attempt:
                resp = requests.get(_PRODUCTS_URL, headers=_HEADERS, timeout=20)
                if resp.status_code != 200:
                    raise CollectorUnavailableError(f"IH returned {resp.status_code}")

        soup = BeautifulSoup(resp.text, "html.parser")
        items: list[dict] = []

        product_links: list[str] = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/product/" in href and href not in product_links:
                product_links.append(href)
        product_links = product_links[:30]

        for path in product_links:
            slug = path.rstrip("/").split("/")[-1]
            full_url = f"https://www.indiehackers.com{path}" if path.startswith("/") else path

            card = soup.find("a", href=path)
            if not card:
                continue
            container = card.find_parent(
                class_=lambda c: c and ("product" in c.lower() or "card" in c.lower())
            ) or card.parent

            name = ""
            description = ""
            revenue_text = ""
            if container:
                h_el = container.find(["h2", "h3", "h4"])
                name = h_el.get_text(strip=True) if h_el else slug
                p_el = container.find("p")
                description = p_el.get_text(strip=True) if p_el else ""
                money_texts = re.findall(r"\$[\d,.]+[kKmM]?(?:/mo)?", container.get_text())
                revenue_text = money_texts[0] if money_texts else ""
            if not name:
                name = slug

            uid = hashlib.md5(slug.encode()).hexdigest()[:8]
            items.append({
                "source_id": f"ih-{uid}",
                "title": name,
                "body": description,
                "url": full_url,
                "score": 0,
                "comment_count": None,
                "posted_at": datetime.now(timezone.utc).isoformat(),
                "metadata": {
                    "product_slug": slug,
                    "revenue_text": revenue_text,
                    "validated_paying_customers": True,
                },
            })
        return items


class IndieHackersCollector(MultiBackendCollector):
    source_name = "indie_hackers"

    CREDENTIAL_SCHEMA: ClassVar[list[dict]] = [*_JINA_CREDENTIALS]

    def build_backends(self) -> list[SourceBackend]:
        return [
            IndieHackersDirectScrapeBackend(),
            JinaReaderBackend("indie_hackers", lambda settings, db: [_PRODUCTS_URL]),
        ]

    @classmethod
    def test_connection(cls, db, settings) -> tuple[bool, str]:
        try:
            resp = requests.get("https://www.indiehackers.com/products", headers=_HEADERS, timeout=10)
            if resp.status_code == 200:
                return True, "Indie Hackers reachable (direct scrape)"
            from niche_radar.collectors import _jina
            if _jina.is_enabled(settings, db, "indie_hackers"):
                return True, f"Direct scrape HTTP {resp.status_code} — Jina Reader fallback is enabled"
            return False, f"HTTP {resp.status_code} — enable the Jina Reader fallback to keep this source alive"
        except Exception as exc:
            return False, str(exc)
