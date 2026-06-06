"""Entity intelligence subsystem — extraction, dedup, storage, and velocity tracking."""
from niche_radar.entities.models import (
    Entity,
    EntityMention,
    EntityExtractionResult,
    ExtractedEntity,
    EntityVelocity,
    EntityType,
)
from niche_radar.entities.extractor import EntityExtractor
from niche_radar.entities.service import EntityService

__all__ = [
    "Entity",
    "EntityMention",
    "EntityExtractionResult",
    "ExtractedEntity",
    "EntityVelocity",
    "EntityType",
    "EntityExtractor",
    "EntityService",
]
