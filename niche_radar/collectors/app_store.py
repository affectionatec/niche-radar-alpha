"""App Store review collector — 1-2 star reviews as pain-point signals.

Uses the `app_store_scraper` PyPI package (pure Python, no auth required).
App IDs are configured per source: source.app_store.app_ids (JSON array).
"""

from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime, timezone
from typing import ClassVar

import structlog

from niche_radar.collectors.base import BaseCollector, CollectorResult, CollectorUnavailableError
from niche_radar.storage.repository import get_source_credential

logger = structlog.get_logger()

DEFAULT_APP_IDS: list[str] = []  # Must be configured via /settings/sources/app_store


class AppStoreCollector(BaseCollector):
    source_name = "app_store"

    CREDENTIAL_SCHEMA: ClassVar[list[dict]] = [
        {"key": "app_ids", "label": "App IDs (JSON array)", "secret": False, "optional": False,
         "help": 'Numeric App Store IDs, e.g. ["284882215","310633997"]. Find in the App Store URL.'},
        {"key": "country", "label": "Country code", "secret": False, "optional": True,
         "help": "ISO country code for reviews (default: us)"},
    ]

    @classmethod
    def test_connection(cls, db: sqlite3.Connection, settings) -> tuple[bool, str]:
        try:
            from app_store_scraper import AppStore  # noqa: F401
            return True, "app_store_scraper available"
        except ImportError:
            return False, "app_store_scraper not installed (pip install app-store-scraper)"

    def collect(
        self, settings, dry_run: bool = False, db: sqlite3.Connection | None = None
    ) -> CollectorResult:
        start = time.perf_counter()
        if dry_run:
            return CollectorResult(self.source_name, [], "", "completed", 0)

        try:
            from app_store_scraper import AppStore

            raw_ids = get_source_credential(db, "app_store", "app_ids", None) if db else None
            if not raw_ids:
                raise CollectorUnavailableError("app_store.app_ids not configured")
            app_ids: list[str] = json.loads(raw_ids)
            country = (get_source_credential(db, "app_store", "country", None) if db else None) or "us"

            items: list[dict] = []
            errors: list[str] = []

            for app_id in app_ids:
                try:
                    app = AppStore(country=country, app_name=f"app-{app_id}", app_id=int(app_id))
                    app.review(how_many=50, sleep=0.5)
                    for review in (app.reviews or []):
                        rating = review.get("rating", 5)
                        if rating > 2:
                            continue  # only 1-2 star reviews
                        rev_id = str(review.get("reviewId") or review.get("id") or f"{app_id}-{hash(review.get('review',''))}")
                        items.append({
                            "source_id": f"appstore-{rev_id}",
                            "title": review.get("title") or f"⭐{'⭐' * (rating-1)} review",
                            "body": review.get("review") or "",
                            "url": f"https://apps.apple.com/{country}/app/id{app_id}",
                            "score": rating,
                            "comment_count": None,
                            "posted_at": (review.get("date") or datetime.now(timezone.utc)).isoformat()
                            if not isinstance(review.get("date"), str) else review.get("date"),
                            "metadata": {
                                "app_id": app_id,
                                "country": country,
                                "rating": rating,
                                "username": review.get("userName"),
                            },
                        })
                    time.sleep(1.0)
                except Exception as exc:
                    logger.warning("app_store_app_failed", app_id=app_id, error=str(exc))
                    errors.append(f"app {app_id}: {exc}")

            status = "completed" if not errors else "partial" if items else "failed"
            return CollectorResult(
                source=self.source_name, items=items, run_id="",
                status=status, items_collected=len(items),
                error_message="; ".join(errors) or None,
                duration_seconds=time.perf_counter() - start,
            )
        except Exception as exc:
            logger.exception("app_store_collect_failed", error=str(exc))
            return CollectorResult(
                source=self.source_name, items=[], run_id="", status="failed",
                items_collected=0, error_message=str(exc),
                duration_seconds=time.perf_counter() - start,
            )
