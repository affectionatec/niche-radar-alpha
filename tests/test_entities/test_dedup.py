"""Tests for entity name deduplication."""
import pytest
from niche_radar.entities.dedup import normalize_name, fuzzy_match, resolve_entity_name


class TestNormalizeName:
    def test_lowercases_and_strips(self):
        assert normalize_name("  Notion  ") == "notion"

    def test_removes_common_suffixes(self):
        assert normalize_name("Notion Inc.") == "notion"
        assert normalize_name("Stripe LLC") == "stripe"
        assert normalize_name("GitHub Ltd") == "github"
        assert normalize_name("Acme Corp.") == "acme"
        assert normalize_name("TechCo Limited") == "techco"

    def test_removes_special_chars(self):
        assert normalize_name("Notion.so") == "notion so"
        assert normalize_name("OpenAI's") == "openai s"


class TestFuzzyMatch:
    def test_exact_normalized_match(self):
        assert fuzzy_match("notion", "notion") is True

    def test_alias_match(self):
        existing_aliases = ["notion.so", "notion app"]
        assert fuzzy_match("notion so", "notion", existing_aliases) is True

    def test_no_match(self):
        assert fuzzy_match("notion", "airtable") is False

    def test_prefix_match(self):
        assert fuzzy_match("gpt4", "gpt4all") is True

    def test_hyphen_vs_space(self):
        assert fuzzy_match("vs code", "vs-code") is True


class TestResolveEntityName:
    def test_new_entity_no_match(self):
        existing = [
            {"canonical_name": "notion", "aliases": '["notion.so"]'},
        ]
        result = resolve_entity_name("airtable", existing)
        assert result == ("airtable", None)

    def test_existing_entity_match_by_name(self):
        existing = [
            {"canonical_name": "notion", "aliases": '["notion.so"]'},
        ]
        result = resolve_entity_name("notion", existing)
        assert result == ("notion", "notion")

    def test_existing_entity_match_by_alias(self):
        existing = [
            {"canonical_name": "notion", "aliases": '["notion.so", "notion app"]'},
        ]
        result = resolve_entity_name("notion so", existing)
        assert result == ("notion", "notion")

    def test_returns_first_match_in_multiple(self):
        existing = [
            {"canonical_name": "stripe", "aliases": "[]"},
            {"canonical_name": "notion", "aliases": '["notion.so"]'},
            {"canonical_name": "airtable", "aliases": "[]"},
        ]
        result = resolve_entity_name("notion.so", existing)
        assert result[1] == "notion"
