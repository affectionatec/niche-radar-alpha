"""Pydantic models for entity intelligence subsystem."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator


EntityType = Literal["company", "product", "technology", "person", "category"]
Sentiment = Literal["positive", "negative", "neutral"]
VelocityLabel = Literal["surging", "growing", "stable", "declining"]


class ExtractedEntity(BaseModel):
    """A single entity extracted by the LLM from a raw item."""
    model_config = ConfigDict(extra="allow")

    name: str
    type: EntityType
    sentiment: Sentiment = "neutral"
    relevance: float = 1.0
    aliases: list[str] = []

    @field_validator("relevance")
    @classmethod
    def clamp_relevance(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"relevance must be 0.0-1.0, got {v}")
        return v


class EntityExtractionResult(BaseModel):
    """Output from the entity extraction LLM call."""
    model_config = ConfigDict(extra="allow")

    entities: list[ExtractedEntity] = []


class Entity(BaseModel):
    """A tracked entity stored in the database."""
    model_config = ConfigDict(extra="allow")

    id: str
    type: EntityType
    canonical_name: str
    aliases: list[str] = []
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    mention_count: int = 0
    source_diversity: int = 0
    velocity_score: float = 0.0


class EntityMention(BaseModel):
    """Link between an entity and the raw item where it was mentioned."""
    model_config = ConfigDict(extra="allow")

    entity_id: str
    raw_item_id: str
    sentiment: Sentiment = "neutral"
    relevance: float = 1.0
    extracted_at: datetime | None = None


class EntityVelocity(BaseModel):
    """Week-over-week velocity record for an entity."""
    model_config = ConfigDict(extra="allow")

    entity_id: str
    week_start: date
    mention_count: int = 0
    source_count: int = 0
    velocity_label: VelocityLabel = "stable"
    velocity_score: float = 0.0
