"""LLM-powered entity extraction from raw items."""

from __future__ import annotations

import structlog

from string import Template

from niche_radar.entities.models import EntityExtractionResult, ExtractedEntity
from niche_radar.entities.prompts import ENTITY_EXTRACTION_SYSTEM, ENTITY_EXTRACTION_USER
from niche_radar.llm.base import LLMClient

logger = structlog.get_logger()

_VALID_TYPES = {"company", "product", "technology", "person", "category"}
_VALID_SENTIMENTS = {"positive", "negative", "neutral"}


class EntityExtractor:
    """Extracts named entities from text using an LLM."""

    def __init__(self, llm: LLMClient, min_text_length: int = 30):
        self._llm = llm
        self._min_text_length = min_text_length

    def extract(self, title: str, body: str) -> EntityExtractionResult:
        """Extract entities from a raw item's title and body text."""
        combined = f"{title} {body}".strip()

        if len(combined) < self._min_text_length:
            return EntityExtractionResult(entities=[])

        user_prompt = Template(ENTITY_EXTRACTION_USER).substitute(
            title=title or "(no title)",
            body=body or "(no body)",
        )

        try:
            raw = self._llm.complete_structured(
                system=ENTITY_EXTRACTION_SYSTEM,
                user=user_prompt,
                temperature=0.1,
            )
        except Exception:
            logger.exception("entity_extraction_llm_failed")
            return EntityExtractionResult(entities=[])

        return self._parse_response(raw)

    def _parse_response(self, raw: dict) -> EntityExtractionResult:
        """Parse LLM response, dropping invalid entities silently."""
        raw_entities = raw.get("entities", [])
        if not isinstance(raw_entities, list):
            return EntityExtractionResult(entities=[])

        valid_entities = []
        for item in raw_entities:
            try:
                entity = self._validate_entity(item)
                if entity:
                    valid_entities.append(entity)
            except Exception:
                continue

        return EntityExtractionResult(entities=valid_entities)

    def _validate_entity(self, item: dict) -> ExtractedEntity | None:
        """Validate and clean a single extracted entity dict. Returns None if invalid."""
        name = str(item.get("name", "")).strip()
        if not name:
            return None

        etype = str(item.get("type", "")).strip()
        if etype not in _VALID_TYPES:
            return None

        sentiment = str(item.get("sentiment", "neutral")).strip()
        if sentiment not in _VALID_SENTIMENTS:
            sentiment = "neutral"

        try:
            relevance = float(item.get("relevance", 1.0))
            relevance = max(0.0, min(1.0, relevance))
        except (ValueError, TypeError):
            relevance = 1.0

        aliases = item.get("aliases", [])
        if not isinstance(aliases, list):
            aliases = []
        aliases = [str(a).strip() for a in aliases if str(a).strip()]

        return ExtractedEntity(
            name=name,
            type=etype,
            sentiment=sentiment,
            relevance=relevance,
            aliases=aliases,
        )
