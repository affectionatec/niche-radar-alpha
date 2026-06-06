"""Tests for the EntityExtractor."""
import json
import pytest
from niche_radar.entities.extractor import EntityExtractor


class FakeLLMClient:
    """Stub LLMClient that returns a controlled JSON response."""
    def __init__(self, response: dict):
        self._response = response
        self._last_prompt = ""

    def complete(self, prompt: str) -> str:
        self._last_prompt = prompt
        return json.dumps(self._response)

    def complete_json(self, prompt: str) -> dict:
        self._last_prompt = prompt
        return self._response

    def complete_structured(self, system: str, user: str, temperature: float | None = None) -> dict:
        self._last_prompt = user
        return self._response


class TestEntityExtractor:
    def test_extract_returns_empty_for_empty_text(self):
        client = FakeLLMClient({"entities": []})
        extractor = EntityExtractor(client)
        result = extractor.extract(title="", body="")
        assert result.entities == []

    def test_extract_parses_entities(self):
        client = FakeLLMClient({
            "entities": [
                {"name": "Notion", "type": "product", "sentiment": "positive",
                 "relevance": 0.9, "aliases": ["Notion.so"]},
                {"name": "AI", "type": "technology", "sentiment": "neutral",
                 "relevance": 0.7, "aliases": []},
            ]
        })
        extractor = EntityExtractor(client)
        result = extractor.extract(
            title="Notion AI is amazing",
            body="I use Notion for everything. The AI features are incredible."
        )
        assert len(result.entities) == 2
        notion = result.entities[0]
        assert notion.name == "Notion"
        assert notion.type == "product"
        assert notion.sentiment == "positive"
        assert "Notion.so" in notion.aliases

    def test_extract_skips_short_text(self):
        client = FakeLLMClient({"entities": []})
        extractor = EntityExtractor(client, min_text_length=50)
        result = extractor.extract(title="Hi", body="Short")
        assert result.entities == []
        assert client._last_prompt == ""

    def test_extract_handles_malformed_llm_response(self):
        client = FakeLLMClient({"wrong_key": []})
        extractor = EntityExtractor(client)
        result = extractor.extract(title="Test", body="Test body content here for testing")
        assert result.entities == []

    def test_extract_handles_llm_json_error(self):
        class BrokenClient:
            def complete_structured(self, system, user, temperature=None):
                raise RuntimeError("LLM timeout")
        extractor = EntityExtractor(BrokenClient())
        result = extractor.extract(title="Test", body="Test body content")
        assert result.entities == []

    def test_entity_types_are_validated(self):
        client = FakeLLMClient({
            "entities": [
                {"name": "TestCo", "type": "company", "sentiment": "neutral", "relevance": 0.5},
                {"name": "TestApp", "type": "product", "sentiment": "positive", "relevance": 0.8},
                {"name": "Python", "type": "technology", "sentiment": "neutral", "relevance": 0.9},
                {"name": "John Doe", "type": "person", "sentiment": "neutral", "relevance": 0.6},
                {"name": "DevTools", "type": "category", "sentiment": "positive", "relevance": 0.7},
            ]
        })
        extractor = EntityExtractor(client)
        result = extractor.extract(title="Test", body="Test body content here for entity type checking")
        assert len(result.entities) == 5
        valid_types = {"company", "product", "technology", "person", "category"}
        for e in result.entities:
            assert e.type in valid_types

    def test_extract_drops_invalid_entities(self):
        client = FakeLLMClient({
            "entities": [
                {"name": "ValidCo", "type": "company", "sentiment": "neutral", "relevance": 0.5},
                {"name": "Bad One", "type": "invalid_xyz", "sentiment": "neutral", "relevance": 0.5},
                {"name": "", "type": "company", "sentiment": "neutral", "relevance": 0.5},
                {"name": "GoodApp", "type": "product", "sentiment": "neutral", "relevance": 0.5},
            ]
        })
        extractor = EntityExtractor(client)
        result = extractor.extract(title="Test", body="Testing body content for invalid entity filtering")
        assert len(result.entities) == 2
        names = {e.name for e in result.entities}
        assert names == {"ValidCo", "GoodApp"}
