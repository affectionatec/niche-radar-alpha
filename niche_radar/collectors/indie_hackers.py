"""Indie Hackers collector — validated niche signals from revenue-generating products.

Scrapes indiehackers.com/products sorted by revenue. Each product entry validates
that a niche has paying customers — useful for the web validation pipeline.
"""

from __future__ import annotations

import hashlib
import time
from datetime import datetime, timezone
from typing import ClassVar

import structlog
from tenacity import Retrying, stop_after_attempt, wait_exponential

from niche_radar.collectors.base import BaseCollector, CollectorResult, CollectorUnavailableError

logger = structlog.get_logger()

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml",
}


class IndieHackersCollector(BaseCollector):
    source_name = "indie_hackers"

    CREDENTIAL_SCHEMA: ClassVar[list[dict]] = []
    # No credentials needed — public scrape.

    @classmethod
    def test_connection(cls, db, settings) -> tuple[bool, str]:
        import requests
        try:
            resp = requests.get("https://www.indiehackers.com/products", headers=_HEADERS, timeout=10)
            if resp.status_code == 200:
                return True, "Indie Hackers reachable"
            return False, f"HTTP {resp.status_code}"
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
                wait=wait_exponential(multiplier=2, min=3, max=60),
                reraise=True,
            )
            for attempt in retryer:
                with attempt:
                    resp = requests.get(
                        "https://www.indiehackers.com/products?sortBy=revenue&revenueVerification=stripe",
                        headers=_HEADERS, timeout=20,
                    )
                    if resp.status_code != 200:
                        raise CollectorUnavailableError(f"IH returned {resp.status_code}")

            soup = BeautifulSoup(resp.text, "html.parser")
            items: list[dict] = []

            # IH product cards — structure varies; grab all links containing /product/
            product_links = []
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if "/product/" in href and href not in product_links:
                    product_links.append(href)
            product_links = product_links[:30]

            for path in product_links:
                slug = path.rstrip("/").split("/")[-1]
                full_url = f"https://www.indiehackers.com{path}" if path.startswith("/") else path

                # Find the card context for this product
                card = soup.find("a", href=path)
                if not card:
                    continue
                container = card.find_parent(class_=lambda c: c and ("product" in c.lower() or "card" in c.lower())) or card.parent

                name = ""
                description = ""
                revenue_text = ""

                if container:
                    h_el = container.find(["h2", "h3", "h4"])
                    name = h_el.get_text(strip=True) if h_el else slug
                    p_el = container.find("p")
                    description = p_el.get_text(strip=True) if p_el else ""
                    # Revenue — look for $ amount near the card
                    import re
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
                    "score": 0,  # revenue as metadata, not score
                    "comment_count": None,
                    "posted_at": datetime.now(timezone.utc).isoformat(),
                    "metadata": {
                        "product_slug": slug,
                        "revenue_text": revenue_text,
                        "validated_paying_customers": True,
                    },
                })

            return CollectorResult(
                source=self.source_name, items=items, run_id="",
                status="completed", items_collected=len(items),
                duration_seconds=time.perf_counter() - start,
            )
        except Exception as exc:
            logger.exception("indie_hackers_collect_failed", error=str(exc))
            return CollectorResult(
                source=self.source_name, items=[], run_id="", status="failed",
                items_collected=0, error_message=str(exc),
                duration_seconds=time.perf_counter() - start,
            )
