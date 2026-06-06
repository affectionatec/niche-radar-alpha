"""Tests for entity Pydantic models."""
import json
import pytest
from niche_radar.entities.models import (
    Entity,
    EntityMention,
    EntityExtractionResult,
    ExtractedEntity,
    EntityVelocity,
)


class TestExtractedEntity:
    def test_valid_entity_types(self):
        for etype in ["company", "product", "technology", "person", "category"]:
            entity = ExtractedEntity(
                name="Test",
                type=etype,
                sentiment="neutral",
                relevance=0.8,
            )
            assert entity.type == etype

    def test_invalid_type_raises(self):
        with pytest.raises(ValueError):
            ExtractedEntity(
                name="Test",
                type="invalid_type",
                sentiment="neutral",
                relevance=0.8,
            )

    def test_invalid_sentiment_raises(self):
        with pytest.raises(ValueError):
            ExtractedEntity(
                name="Test",
                type="company",
                sentiment="angry",
                relevance=0.8,
            )

    def test_relevance_clamped(self):
        with pytest.raises(ValueError):
            ExtractedEntity(
                name="Test",
                type="company",
                sentiment="neutral",
                relevance=1.5,
            )

    def test_defaults(self):
        entity = ExtractedEntity(name="Test", type="company")
        assert entity.sentiment == "neutral"
        assert entity.relevance == 1.0
        assert entity.aliases == []


class TestEntityExtractionResult:
    def test_parses_entities_list(self):
        result = EntityExtractionResult(
            entities=[
                ExtractedEntity(
                    name="Notion",
                    type="product",
                    sentiment="positive",
                    relevance=0.9,
                    aliases=["Notion.so"],
                ),
                ExtractedEntity(
                    name="AI",
                    type="technology",
                    sentiment="neutral",
                    relevance=0.7,
                ),
            ]
        )
        assert len(result.entities) == 2
        assert result.entities[0].name == "Notion"
        assert result.entities[0].aliases == ["Notion.so"]

    def test_empty_entities(self):
        result = EntityExtractionResult(entities=[])
        assert result.entities == []


class TestEntity:
    def test_create_entity(self):
        entity = Entity(
            id="ent-001",
            type="product",
            canonical_name="Notion",
            aliases=["Notion.so", "notion.com"],
            mention_count=5,
            source_diversity=2,
            velocity_score=75.0,
        )
        assert entity.canonical_name == "Notion"
        assert len(entity.aliases) == 2

    def test_serialize_aliases(self):
        entity = Entity(
            id="ent-001",
            type="company",
            canonical_name="OpenAI",
            aliases=["OpenAI Inc", "ChatGPT"],
            mention_count=10,
            source_diversity=3,
            velocity_score=120.0,
        )
        data = entity.model_dump()
        assert isinstance(data["aliases"], list)
        assert "ChatGPT" in data["aliases"]


class TestEntityMention:
    def test_create_mention(self):
        mention = EntityMention(
            entity_id="ent-001",
            raw_item_id="item-abc",
            sentiment="positive",
            relevance=0.85,
        )
        assert mention.entity_id == "ent-001"
        assert mention.relevance == 0.85


class TestEntityVelocity:
    def test_velocity_labels(self):
        for label in ["surging", "growing", "stable", "declining"]:
            vel = EntityVelocity(
                entity_id="ent-001",
                week_start="2026-05-26",
                mention_count=10,
                source_count=3,
                velocity_label=label,
                velocity_score=50.0,
            )
            assert vel.velocity_label == label
