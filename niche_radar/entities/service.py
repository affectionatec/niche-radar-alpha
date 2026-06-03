"""EntityService — orchestrates extraction, dedup, and storage for the entity pipeline."""

from __future__ import annotations

import random

import structlog

from niche_radar.entities.dedup import resolve_entity_name
from niche_radar.entities.extractor import EntityExtractor
from niche_radar.entities.repository import (
    get_existing_entities_for_dedup,
    link_mention,
    upsert_entity,
)
from niche_radar.llm.base import LLMClient

logger = structlog.get_logger()


class EntityService:
    """Orchestrates entity extraction → dedup → storage for raw items."""

    def __init__(
        self,
        llm: LLMClient,
        db,
        sample_rate: float = 0.2,
        min_text_length: int = 30,
    ):
        self._extractor = EntityExtractor(llm, min_text_length=min_text_length)
        self._db = db
        self._sample_rate = sample_rate
        self._min_text_length = min_text_length

    def process_item(self, item_id: str) -> list[str]:
        """Extract entities from a raw item, dedup, and store. Returns list of entity IDs."""
        row = self._db.execute(
            "SELECT title, body, source FROM raw_items WHERE id=?",
            (item_id,),
        ).fetchone()

        if not row:
            logger.warning("entity_service_item_not_found", item_id=item_id)
            return []

        title = row["title"] or ""
        body = row["body"] or ""
        source = row["source"]

        combined = f"{title} {body}".strip()
        if len(combined) < self._min_text_length:
            return []

        if random.random() > self._sample_rate:
            return []

        result = self._extractor.extract(title=title, body=body)

        if not result.entities:
            return []

        existing = get_existing_entities_for_dedup(self._db)
        entity_ids = []

        for extracted in result.entities:
            canonical, _matched_id = resolve_entity_name(extracted.name, existing)

            entity_id = upsert_entity(
                self._db,
                canonical_name=canonical,
                entity_type=extracted.type,
                aliases=extracted.aliases,
                source=source,
            )

            link_mention(
                self._db,
                entity_id=entity_id,
                raw_item_id=item_id,
                sentiment=extracted.sentiment,
                relevance=extracted.relevance,
            )

            entity_ids.append(entity_id)

            existing.append({
                "id": entity_id,
                "canonical_name": canonical,
                "aliases": extracted.aliases,
            })

        return entity_ids
