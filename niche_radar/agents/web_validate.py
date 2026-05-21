"""Web validation pipeline — DuckDuckGo HTML scrape to check market existence.

Runs between A3 and A4 in phase C. Zero LLM cost; uses DDG public HTML endpoint.

Three queries:
  1. "<keywords> product hunt"
  2. "<keywords> g2 reviews"
  3. "<keywords> indiehackers revenue"

Heuristic verdict:
  validated_gap      — keywords searched, few/no results on PH/G2/IH
  crowded_market     — many results, many solutions found
  expensive_incumbents — results exist but pricing signals suggest high cost
  unclear            — not enough evidence to decide

Results are cached in-process (LRU by query string) to avoid hitting DDG twice
for the same keywords within one pipeline run.
"""

from __future__ import annotations

import functools
import re
import time
from dataclasses import dataclass, field

import structlog

logger = structlog.get_logger()

DDG_HTML = "https://html.duckduckgo.com/html/"
_TIMEOUT = 8  # seconds

VALIDATION_DOMAINS = frozenset([
    "producthunt.com",
    "g2.com",
    "capterra.com",
    "indiehackers.com",
    "getapp.com",
    "trustradius.com",
])

_PRICE_RE = re.compile(r"\$\d+(?:\.\d+)?(?:/mo|/month|/year|/yr|\/mo|\/month)", re.I)
_HIGH_PRICE_THRESHOLD = 50  # $/mo — if median price > this, "expensive incumbents"

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; NicheRadar/0.1; research bot)",
    "Accept": "text/html",
}


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str


@dataclass
class WebValidationResult:
    verdict: str  # validated_gap | crowded_market | expensive_incumbents | unclear
    queries: list[str]
    evidence: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"verdict": self.verdict, "evidence": self.evidence}


def _extract_prices(text: str) -> list[float]:
    """Extract numeric dollar-per-month values from a text snippet."""
    out: list[float] = []
    for m in _PRICE_RE.finditer(text):
        try:
            out.append(float(re.sub(r"[^\d.]", "", m.group().split("/")[0])))
        except ValueError:
            pass
    return out


# In-process LRU cache — keyed by query string, stores list[SearchResult]
@functools.lru_cache(maxsize=256)
def _cached_search(query: str) -> tuple[SearchResult, ...]:
    """Fetch DDG HTML results for a query. Cached across the process lifetime."""
    import requests
    from bs4 import BeautifulSoup

    try:
        resp = requests.post(
            DDG_HTML,
            data={"q": query, "b": ""},
            headers=_HEADERS,
            timeout=_TIMEOUT,
        )
        if resp.status_code != 200:
            logger.warning("ddg_bad_status", status=resp.status_code, query=query)
            return ()
        soup = BeautifulSoup(resp.text, "html.parser")
        results: list[SearchResult] = []
        for a in soup.select("a.result__a")[:10]:
            href = a.get("href", "")
            title = a.get_text(strip=True)
            # Snippet is in the adjacent .result__snippet element
            snippet_el = a.find_next(class_="result__snippet")
            snippet = snippet_el.get_text(strip=True) if snippet_el else ""
            results.append(SearchResult(title=title, url=href, snippet=snippet))
        return tuple(results)
    except Exception as exc:
        logger.warning("ddg_search_failed", query=query, error=str(exc))
        return ()


class DDGSearcher:
    """Thin wrapper around the DDG HTML endpoint with in-process caching."""

    def search(self, query: str) -> list[SearchResult]:
        return list(_cached_search(query))


def validate_opportunity(
    a2_keywords: list[str],
    a2_what: str | None = None,
    dry_run: bool = False,
) -> WebValidationResult:
    """Run 3 DDG searches for the given keywords and produce a validation verdict.

    In dry_run mode returns an 'unclear' verdict without making any HTTP calls.
    """
    if dry_run or not a2_keywords:
        return WebValidationResult(verdict="unclear", queries=[], evidence=[])

    keyword_str = " ".join(a2_keywords[:3])
    queries = [
        f"{keyword_str} product hunt",
        f"{keyword_str} g2 reviews",
        f"{keyword_str} indiehackers revenue",
    ]
    searcher = DDGSearcher()
    all_results: list[SearchResult] = []
    evidence: list[dict] = []

    for query in queries:
        results = searcher.search(query)
        all_results.extend(results)
        evidence.append({
            "query": query,
            "top_results": [{"title": r.title, "url": r.url, "snippet": r.snippet[:200]} for r in results[:5]],
        })
        time.sleep(0.3)  # polite delay

    # Count how many results are from known validation platforms
    platform_hits = sum(
        1 for r in all_results if any(d in r.url for d in VALIDATION_DOMAINS)
    )

    # Extract price signals
    prices: list[float] = []
    for r in all_results:
        prices.extend(_extract_prices(r.snippet + " " + r.title))

    # Decide verdict
    if platform_hits == 0:
        verdict = "validated_gap"
    elif prices and sum(prices) / len(prices) > _HIGH_PRICE_THRESHOLD:
        verdict = "expensive_incumbents"
    elif platform_hits >= 5:
        verdict = "crowded_market"
    else:
        verdict = "unclear"

    logger.info(
        "web_validation_done",
        keywords=keyword_str,
        platform_hits=platform_hits,
        price_signals=len(prices),
        verdict=verdict,
    )
    return WebValidationResult(verdict=verdict, queries=queries, evidence=evidence)
