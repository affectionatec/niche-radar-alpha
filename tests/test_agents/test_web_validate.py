"""Unit tests for agents/web_validate.py — DDG search verdict logic."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from niche_radar.agents.web_validate import (
    SearchResult,
    WebValidationResult,
    validate_opportunity,
    _extract_prices,
)


def _make_results(urls: list[str], snippets: list[str] | None = None):
    snippets = snippets or [""] * len(urls)
    return [SearchResult(title=f"T{i}", url=u, snippet=s) for i, (u, s) in enumerate(zip(urls, snippets))]


def test_validated_gap_when_no_platform_hits():
    keywords = ["obscure", "niche", "tool"]
    with patch("niche_radar.agents.web_validate._cached_search", return_value=()):
        result = validate_opportunity(keywords)
    assert result.verdict == "validated_gap"


def test_crowded_market_when_many_platform_results():
    results = _make_results([
        "https://www.producthunt.com/posts/x",
        "https://www.g2.com/products/x/reviews",
        "https://www.producthunt.com/posts/y",
        "https://indiehackers.com/product/x",
        "https://www.capterra.com/x",
        "https://www.g2.com/products/z",
    ])
    with patch("niche_radar.agents.web_validate._cached_search", return_value=tuple(results)):
        result = validate_opportunity(["cloud", "cost", "report"])
    assert result.verdict == "crowded_market"


def test_expensive_incumbents_when_high_prices():
    results = _make_results(
        ["https://www.g2.com/products/x", "https://www.producthunt.com/posts/y"],
        snippets=["pricing starts at $200/mo enterprise plan", "costs $150/month per team"],
    )
    with patch("niche_radar.agents.web_validate._cached_search", return_value=tuple(results)):
        result = validate_opportunity(["cloud", "monitoring"])
    assert result.verdict == "expensive_incumbents"


def test_dry_run_returns_unclear_without_http():
    with patch("niche_radar.agents.web_validate._cached_search") as mock_search:
        result = validate_opportunity(["any", "keywords"], dry_run=True)
    mock_search.assert_not_called()
    assert result.verdict == "unclear"


def test_empty_keywords_returns_unclear():
    result = validate_opportunity([])
    assert result.verdict == "unclear"


def test_evidence_is_populated():
    results = _make_results(["https://example.com/x", "https://g2.com/y"])
    with patch("niche_radar.agents.web_validate._cached_search", return_value=tuple(results)):
        result = validate_opportunity(["test", "keywords"])
    assert len(result.evidence) == 3  # one per query
    assert all("query" in e for e in result.evidence)


def test_extract_prices_finds_dollar_amounts():
    prices = _extract_prices("starts at $29/mo for teams, up to $99/month for enterprise")
    assert 29.0 in prices
    assert 99.0 in prices


def test_extract_prices_empty_for_no_prices():
    assert _extract_prices("no pricing mentioned here at all") == []
