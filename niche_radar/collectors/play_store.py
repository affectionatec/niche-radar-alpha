"""Google Play Store review collector — 1-2 star reviews as pain-point signals.

Uses the `google_play_scraper` PyPI package (pure Python, no auth required).
App IDs are configured per source: source.play_store.app_ids (JSON array).
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


class PlayStoreCollector(BaseCollector):
    source_name = "play_store"

    CREDENTIAL_SCHEMA: ClassVar[list[dict]] = [
        {"key": "app_ids", "label": "Package names (JSON array)", "secret": False, "optional": False,
         "help": 'Android package names, e.g. ["com.notion.id","com.airtable.android"]'},
        {"key": "lang", "label": "Language code", "secret": False, "optional": True,
         "help": "ISO 639-1 language (default: en)"},
        {"key": "country", "label": "Country code", "secret": False, "optional": True,
         "help": "ISO country code (default: us)"},
    ]

    @classmethod
    def test_connection(cls, db: sqlite3.Connection, settings) -> tuple[bool, str]:
        try:
            from google_play_scraper import reviews  # noqa: F401
            return True, "google_play_scraper available"
        except ImportError:
            return False, "google_play_scraper not installed (pip install google-play-scraper)"

    def collect(
        self, settings, dry_run: bool = False, db: sqlite3.Connection | None = None
    ) -> CollectorResult:
        start = time.perf_counter()
        if dry_run:
            return CollectorResult(self.source_name, [], "", "completed", 0)

        try:
            from google_play_scraper import reviews, Sort

            raw_ids = get_source_credential(db, "play_store", "app_ids", None) if db else None
            if not raw_ids:
                raise CollectorUnavailableError("play_store.app_ids not configured")
            app_ids: list[str] = json.loads(raw_ids)
            lang = (get_source_credential(db, "play_store", "lang", None) if db else None) or "en"
            country = (get_source_credential(db, "play_store", "country", None) if db else None) or "us"

            items: list[dict] = []
            errors: list[str] = []

            for pkg in app_ids:
                try:
                    result, _ = reviews(
                        pkg,
                        lang=lang,
                        country=country,
                        sort=Sort.NEWEST,
                        count=50,
                        filter_score_with=None,
                    )
                    for rev in result:
                        score = rev.get("score", 5)
                        if score > 2:
                            continue
                        rev_id = str(rev.get("reviewId") or f"{pkg}-{hash(rev.get('content',''))}")
                        at = rev.get("at")
                        posted_at = at.isoformat() if at else datetime.now(timezone.utc).isoformat()
                        items.append({
                            "source_id": f"play-{rev_id}",
                            "title": f"⭐{'⭐'*(score-1)} Play Store review of {pkg.split('.')[-1]}",
                            "body": rev.get("content") or "",
                            "url": f"https://play.google.com/store/apps/details?id={pkg}",
                            "score": score,
                            "comment_count": rev.get("thumbsUpCount"),
                            "posted_at": posted_at,
                            "metadata": {
                                "app_id": pkg,
                                "lang": lang,
                                "country": country,
                                "score": score,
                                "reply": rev.get("replyContent"),
                            },
                        })
                    time.sleep(1.0)
                except Exception as exc:
                    logger.warning("play_store_app_failed", pkg=pkg, error=str(exc))
                    errors.append(f"pkg {pkg}: {exc}")

            status = "completed" if not errors else "partial" if items else "failed"
            return CollectorResult(
                source=self.source_name, items=items, run_id="",
                status=status, items_collected=len(items),
                error_message="; ".join(errors) or None,
                duration_seconds=time.perf_counter() - start,
            )
        except Exception as exc:
            logger.exception("play_store_collect_failed", error=str(exc))
            return CollectorResult(
                source=self.source_name, items=[], run_id="", status="failed",
                items_collected=0, error_message=str(exc),
                duration_seconds=time.perf_counter() - start,
            )
