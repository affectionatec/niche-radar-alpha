"""GitHub trending data collector."""

from __future__ import annotations

import re
import sqlite3
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
from niche_radar.storage.repository import get_source_credential

logger = structlog.get_logger()


def _to_int(text: str | None) -> int:
    return int(re.sub(r"[^\d]", "", text or "") or 0)


class GitHubTrendingCollector(BaseCollector):
    source_name = "github"

    CREDENTIAL_SCHEMA: ClassVar[list[dict]] = [
        {"key": "token", "label": "GitHub Token (optional)", "secret": True, "optional": True, "help": "Increases API rate limits. Create at github.com/settings/tokens"},
    ]

    @classmethod
    def test_connection(cls, db: sqlite3.Connection, settings) -> tuple[bool, str]:
        import requests
        token = get_source_credential(db, "github", "token", settings.github_token)
        headers = {"User-Agent": "NicheRadar/0.1"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            resp = requests.get("https://github.com/trending", headers=headers, timeout=10)
            if resp.status_code == 200:
                return True, "GitHub Trending reachable"
            return False, f"HTTP {resp.status_code}"
        except Exception as exc:
            return False, str(exc)

    def collect(self, settings, dry_run: bool = False, db: sqlite3.Connection | None = None) -> CollectorResult:
        start = time.perf_counter()
        if dry_run:
            return CollectorResult(self.source_name, [], "", "completed", 0)

        try:
            import requests
            from bs4 import BeautifulSoup

            retryer = Retrying(
                stop=stop_after_attempt(max(1, int(settings.max_retries or 1))),
                wait=wait_exponential(
                    multiplier=1,
                    exp_base=max(2, int(settings.retry_backoff_base or 2)),
                    min=1,
                    max=30,
                ),
                reraise=True,
            )
            session = requests.Session()
            session.headers.update({"User-Agent": "NicheRadar/0.1", "Accept": "text/html,application/json"})
            github_token = get_source_credential(db, "github", "token", settings.github_token) if db else settings.github_token
            if github_token:
                session.headers["Authorization"] = f"Bearer {github_token}"

            errors: list[str] = []
            now_iso = datetime.now(timezone.utc).isoformat()
            try:
                for attempt in retryer:
                    with attempt:
                        response = session.get("https://github.com/trending", timeout=20)
                        if response.status_code != 200:
                            raise CollectorUnavailableError(
                                f"github.com/trending returned {response.status_code}"
                            )
                soup = BeautifulSoup(response.text, "html.parser")
                items = []
                for article in soup.select("article.Box-row"):
                    link = article.select_one("h2 a")
                    if not link:
                        continue
                    repo = "/".join(part.strip() for part in link.get_text(" ", strip=True).split("/") if part.strip())
                    desc = article.select_one("p")
                    today_text = next(
                        (span.get_text(" ", strip=True) for span in article.select("span") if "stars today" in span.get_text(" ", strip=True).lower()),
                        None,
                    )
                    total_stars = _to_int((article.select_one('a[href$="/stargazers"]') or {}).get_text(" ", strip=True) if article.select_one('a[href$="/stargazers"]') else None)
                    forks = _to_int((article.select_one('a[href$="/forks"]') or {}).get_text(" ", strip=True) if article.select_one('a[href$="/forks"]') else None)
                    stars_today = _to_int(today_text)
                    items.append(
                        {
                            "source_id": repo,
                            "title": repo,
                            "body": desc.get_text(" ", strip=True) if desc else None,
                            "url": f"https://github.com/{repo}",
                            "score": stars_today or total_stars,
                            "comment_count": None,
                            # github.com/trending is daily-trending — stamp as fresh now
                            "posted_at": now_iso,
                            "metadata": {
                                "language": (article.select_one('[itemprop="programmingLanguage"]') or {}).get_text(strip=True) if article.select_one('[itemprop="programmingLanguage"]') else None,
                                "stars_today": stars_today,
                                "total_stars": total_stars,
                                "forks": forks,
                                "scraped": True,
                            },
                        }
                    )
                if not items:
                    raise CollectorUnavailableError("No repositories parsed from github.com/trending")
            except Exception as exc:
                logger.warning("github_trending_scrape_failed", error=str(exc))
                errors.append(f"scrape: {exc}")
                for attempt in retryer:
                    with attempt:
                        window_hours = settings.freshness_github_hours
                        since = (datetime.now(timezone.utc) - timedelta(hours=window_hours)).strftime("%Y-%m-%d")
                        response = session.get(
                            "https://api.github.com/search/repositories",
                            params={
                                "q": f"pushed:>{since}",  # active in window, not just newborn
                                "sort": "stars",
                                "order": "desc",
                                "per_page": 50,
                            },
                            timeout=20,
                        )
                        self._check_rate_limit(response)
                        if response.status_code != 200:
                            raise CollectorUnavailableError(
                                f"GitHub REST API returned {response.status_code}"
                            )
                items = [
                    {
                        "source_id": repo["full_name"],
                        "title": repo["full_name"],
                        "body": repo.get("description"),
                        "url": repo.get("html_url"),
                        "score": repo.get("stargazers_count", 0),
                        "comment_count": None,
                        "posted_at": repo.get("pushed_at") or repo.get("created_at"),
                        "metadata": {
                            "language": repo.get("language"),
                            "stars_today": None,
                            "total_stars": repo.get("stargazers_count", 0),
                            "forks": repo.get("forks_count", 0),
                            "topics": repo.get("topics", []),
                            "scraped": False,
                            "api_fallback": True,
                        },
                    }
                    for repo in response.json().get("items", [])
                ]

            status = "completed" if not errors else "partial"
            if not items:
                status = "failed"
            return CollectorResult(
                source=self.source_name,
                items=items,
                run_id="",
                status=status,
                items_collected=len(items),
                error_message="; ".join(errors) or None,
                duration_seconds=time.perf_counter() - start,
            )
        except Exception as exc:
            logger.exception("github_trending_collect_failed", error=str(exc))
            return CollectorResult(
                source=self.source_name,
                items=[],
                run_id="",
                status="failed",
                items_collected=0,
                error_message=str(exc),
                duration_seconds=time.perf_counter() - start,
            )

    def _check_rate_limit(self, response) -> None:
        remaining = response.headers.get("X-RateLimit-Remaining")
        reset_at = response.headers.get("X-RateLimit-Reset")
        if remaining is not None and remaining.isdigit() and int(remaining) <= 0:
            raise CollectorUnavailableError(f"GitHub API rate limit exhausted until {reset_at}")
        if remaining is not None and remaining.isdigit() and int(remaining) < 5:
            logger.warning("github_rate_limit_low", remaining=int(remaining), reset_at=reset_at)
