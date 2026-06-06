# Phase 1 — Entity Intelligence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract and track named entities (companies, products, technologies, people, categories) from all ingested content using LLM-powered NER, making them first-class objects in the system with velocity tracking and a dedicated dashboard view.

**Architecture:** A new `EntityExtractor` module (LLM-powered NER) runs against raw items after collection. Extracted entities are upserted into a new `entities` table with fuzzy-dedup via canonical name + aliases. Each extraction creates an `entity_mentions` row linking entity to source item. Velocity is computed week-over-week. New API endpoints expose entity lists, detail, trending, and mentions. The extraction is gated behind a sampling rate (`entity_extraction_sample_rate`, default 0.2 = 20% of items) to control LLM costs, with full extraction for items matched by active Radars (Phase 2 readiness).

**Tech Stack:** Python 3.11+ (Pydantic models, LLMClient protocol, APScheduler), SQLite (new tables via migration pattern), FastAPI (new REST endpoints), pytest (TDD)

**File Map:**

| File | Role |
|------|------|
| `niche_radar/entities/__init__.py` | Public API surface for the entity subsystem |
| `niche_radar/entities/models.py` | Pydantic models: `Entity`, `EntityMention`, `EntityExtractionResult`, `EntityVelocity` |
| `niche_radar/entities/extractor.py` | LLM-powered NER: `EntityExtractor` class using `LLMClient` |
| `niche_radar/entities/dedup.py` | Fuzzy name matching: `resolve_entity()` merges aliases |
| `niche_radar/entities/repository.py` | SQLite CRUD: upsert, link, query, velocity |
| `niche_radar/entities/service.py` | Orchestration: extraction → dedup → storage pipeline |
| `niche_radar/entities/prompts.py` | LLM prompts for entity extraction |
| `niche_radar/storage/database.py` | **Modify:** Add `entities`, `entity_mentions`, `entity_velocity` tables + migration |
| `niche_radar/api/server.py` | **Modify:** Add entity API routes |
| `niche_radar/scheduler.py` | **Modify:** Add entity extraction job after collection |
| `niche_radar/config.py` | **Modify:** Add `entity_extraction_sample_rate` setting |
| `tests/test_entities/__init__.py` | Test package marker |
| `tests/test_entities/test_extractor.py` | Unit tests for entity extraction |
| `tests/test_entities/test_dedup.py` | Unit tests for entity deduplication |
| `tests/test_entities/test_repository.py` | Integration tests for entity CRUD (uses `db` fixture) |
| `tests/test_entities/test_service.py` | Integration tests for the full extraction→storage pipeline |
| `tests/test_entities/test_api.py` | API endpoint tests |

---

### Task 1: Database Schema

**Files:**
- Modify: `niche_radar/storage/database.py` (add tables to `_SCHEMA`, add migration in `_migrate`)

- [ ] **Step 1: Add entity tables to _SCHEMA string**

In `database.py`, append these table definitions to the `_SCHEMA` string (before the final `"""`):

```sql
CREATE TABLE IF NOT EXISTS entities (
    id              TEXT PRIMARY KEY,
    type            TEXT NOT NULL CHECK(type IN ('company','product','technology','person','category')),
    canonical_name  TEXT NOT NULL,
    aliases         JSON DEFAULT '[]',
    first_seen      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    mention_count   INTEGER DEFAULT 0,
    source_diversity INTEGER DEFAULT 0,
    velocity_score  REAL DEFAULT 0.0
);
CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(type);
CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(canonical_name);
CREATE INDEX IF NOT EXISTS idx_entities_velocity ON entities(velocity_score DESC);
CREATE INDEX IF NOT EXISTS idx_entities_mentions ON entities(mention_count DESC);

CREATE TABLE IF NOT EXISTS entity_mentions (
    entity_id       TEXT REFERENCES entities(id) ON DELETE CASCADE,
    raw_item_id     TEXT REFERENCES raw_items(id) ON DELETE CASCADE,
    sentiment       TEXT CHECK(sentiment IN ('positive','negative','neutral')),
    relevance       REAL DEFAULT 1.0 CHECK(relevance >= 0.0 AND relevance <= 1.0),
    extracted_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (entity_id, raw_item_id)
);
CREATE INDEX IF NOT EXISTS idx_entity_mentions_item ON entity_mentions(raw_item_id);
CREATE INDEX IF NOT EXISTS idx_entity_mentions_extracted ON entity_mentions(extracted_at);

CREATE TABLE IF NOT EXISTS entity_velocity (
    entity_id       TEXT REFERENCES entities(id) ON DELETE CASCADE,
    week_start      DATE NOT NULL,
    mention_count   INTEGER DEFAULT 0,
    source_count    INTEGER DEFAULT 0,
    velocity_label  TEXT CHECK(velocity_label IN ('surging','growing','stable','declining')),
    velocity_score  REAL DEFAULT 0.0,
    PRIMARY KEY (entity_id, week_start)
);
CREATE INDEX IF NOT EXISTS idx_entity_velocity_week ON entity_velocity(week_start);
```

- [ ] **Step 2: Add migration logic in _migrate()**

In `database.py`, add after the existing v4 migration block:

```python
    # v5 (entity intelligence): entities, entity_mentions, entity_velocity.
    # These tables are already in _SCHEMA as CREATE TABLE IF NOT EXISTS,
    # so they'll be created on next startup. Backfill is not needed —
    # extraction starts fresh from the next collection cycle.
```

- [ ] **Step 3: Run existing tests to verify schema change is backwards-compatible**

```bash
python -m pytest tests/test_storage.py -v
```

Expected: All existing tests PASS (new tables don't break anything).

- [ ] **Step 4: Commit**

```bash
git add niche_radar/storage/database.py
git commit -m "feat(entities): add entities, entity_mentions, and entity_velocity tables"
```

---

### Task 2: Entity Pydantic Models

**Files:**
- Create: `niche_radar/entities/__init__.py`
- Create: `niche_radar/entities/models.py`
- Create: `tests/test_entities/__init__.py`

- [ ] **Step 1: Write the test file**

Create `tests/test_entities/__init__.py` (empty).

Create `tests/test_entities/test_models.py`:

```python
"""Tests for entity Pydantic models."""
import json
import pytest
from niche_radar.entities.models import (
    Entity,
    EntityMention,
    EntityExtractionResult,
    ExtractedEntity,
    EntityVelocity,
    EntityType,
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_entities/test_models.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Create the models**

Create `niche_radar/entities/__init__.py`:

```python
"""Entity intelligence subsystem — extraction, dedup, storage, and velocity tracking."""
from niche_radar.entities.models import (
    Entity,
    EntityMention,
    EntityExtractionResult,
    ExtractedEntity,
    EntityVelocity,
    EntityType,
)

__all__ = [
    "Entity",
    "EntityMention",
    "EntityExtractionResult",
    "ExtractedEntity",
    "EntityVelocity",
    "EntityType",
]
```

Create `niche_radar/entities/models.py`:

```python
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
            raise ValueError(f"relevance must be 0.0–1.0, got {v}")
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_entities/test_models.py -v
```

Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add niche_radar/entities/__init__.py niche_radar/entities/models.py tests/test_entities/
git commit -m "feat(entities): add Pydantic models for entity intelligence subsystem"
```

---

### Task 3: LLM Entity Extraction Prompt

**Files:**
- Create: `niche_radar/entities/prompts.py`
- Create: `tests/test_entities/test_extractor.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_entities/test_extractor.py`:

```python
"""Tests for the EntityExtractor."""
import json
import pytest
from niche_radar.entities.extractor import EntityExtractor
from niche_radar.entities.models import ExtractedEntity, EntityType


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
        # LLM should not have been called
        assert client._last_prompt == ""

    def test_extract_handles_malformed_llm_response(self):
        client = FakeLLMClient({"wrong_key": []})
        extractor = EntityExtractor(client)
        result = extractor.extract(title="Test", body="Test body content here")
        # Should gracefully return empty list on malformed response
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
        result = extractor.extract(title="Test", body="Test body content")
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
        result = extractor.extract(title="Test", body="Test body content")
        assert len(result.entities) == 2
        names = {e.name for e in result.entities}
        assert names == {"ValidCo", "GoodApp"}
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_entities/test_extractor.py -v
```

Expected: FAIL — `niche_radar.entities.extractor` not found.

- [ ] **Step 3: Create the prompts module**

Create `niche_radar/entities/prompts.py`:

```python
"""LLM prompts for entity extraction."""

from __future__ import annotations

ENTITY_EXTRACTION_SYSTEM = """\
You are a named entity recognition (NER) system specialized in the technology and \
startup domain. Your task is to identify and classify entities in user-generated \
content from social media, forums, and developer communities.

Extract entities of these types:
- **company**: A named business or startup (e.g., "Google", "Stripe", "Linear")
- **product**: A specific software product, app, or tool (e.g., "Notion", "VS Code", "Figma")
- **technology**: A programming language, framework, protocol, or technical concept \
(e.g., "Rust", "GraphQL", "Kubernetes", "local-first")
- **person**: A named individual (e.g., "John Carmack", "Pieter Levels")
- **category**: A product category, market segment, or domain (e.g., "project management", \
"developer tools", "no-code")

For each entity found, provide:
- **name**: The canonical name (single most common form)
- **type**: One of the five types above
- **sentiment**: How the text discusses this entity — "positive", "negative", or "neutral"
- **relevance**: 0.0–1.0 how central this entity is to the text's main topic
- **aliases**: Alternative names or variations mentioned (or empty list if none)

Rules:
- Extract ONLY entities explicitly mentioned in the text. Do not infer or hallucinate.
- Use the most common/canonical form as the name (e.g., "OpenAI" not "OpenAI Inc.")
- If the same entity appears under multiple names, list the most-used form as name \
and the others as aliases.
- For sentiment: base it on how the AUTHOR feels about the entity, not general sentiment.
- Return at most 10 entities — focus on the most relevant ones.
- If no entities are found, return an empty list.

Return ONLY valid JSON matching this exact schema:
{"entities": [{"name": "...", "type": "...", "sentiment": "...", "relevance": 0.0, "aliases": [...]}]}
"""

ENTITY_EXTRACTION_USER = """\
Analyze this content and extract all technology/startup-domain entities:

Title: $title

Body: $body

Return the entities as a JSON object with an "entities" array."""
```

- [ ] **Step 4: Create the extractor module**

Create `niche_radar/entities/extractor.py`:

```python
"""LLM-powered entity extraction from raw items."""

from __future__ import annotations

import logging
from string import Template

from niche_radar.entities.models import EntityExtractionResult, ExtractedEntity
from niche_radar.entities.prompts import ENTITY_EXTRACTION_SYSTEM, ENTITY_EXTRACTION_USER
from niche_radar.llm.base import LLMClient

logger = logging.getLogger(__name__)

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
```

- [ ] **Step 5: Run extractor tests**

```bash
python -m pytest tests/test_entities/test_extractor.py -v
```

Expected: All PASS.

- [ ] **Step 6: Commit**

```bash
git add niche_radar/entities/prompts.py niche_radar/entities/extractor.py tests/test_entities/test_extractor.py
git commit -m "feat(entities): add LLM-powered EntityExtractor with validation"
```

---

### Task 4: Entity Deduplication

**Files:**
- Create: `niche_radar/entities/dedup.py`
- Create: `tests/test_entities/test_dedup.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_entities/test_dedup.py`:

```python
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
        # "gpt4" is a prefix-substring of "gpt4all"
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_entities/test_dedup.py -v
```

Expected: FAIL.

- [ ] **Step 3: Create the dedup module**

Create `niche_radar/entities/dedup.py`:

```python
"""Entity name normalization and fuzzy deduplication."""

from __future__ import annotations

import json
import re

_SUFFIXES = re.compile(
    r"\b(inc\.?|llc\.?|ltd\.?|corp\.?|corp|corporation|limited|co\.?|"
    r"gmbh|s\.?a\.?|s\.?r\.?l\.?|pty\.?\s*ltd\.?|ag|nv|bv|plc)\b",
    re.IGNORECASE,
)
_NON_ALPHA = re.compile(r"[^a-z0-9\s]")
_WS = re.compile(r"\s+")


def normalize_name(name: str) -> str:
    """Normalize an entity name for comparison: lowercase, strip suffixes, remove punctuation."""
    name = name.strip().lower()
    name = _SUFFIXES.sub("", name)
    name = _NON_ALPHA.sub(" ", name)
    name = _WS.sub(" ", name)
    return name.strip()


def fuzzy_match(name: str, existing_canonical: str, existing_aliases: list[str] | None = None) -> bool:
    """Check if `name` matches an existing entity by canonical name or aliases."""
    n = normalize_name(name)
    ec = normalize_name(existing_canonical)

    if n == ec:
        return True
    if n in ec or ec in n:
        return True

    if existing_aliases:
        for alias in existing_aliases:
            an = normalize_name(alias)
            if n == an:
                return True

    return False


def resolve_entity_name(
    name: str,
    existing_entities: list[dict],
) -> tuple[str, str | None]:
    """Resolve a raw entity name against the existing entity table.

    Returns (canonical_name_to_use, matched_existing_entity_id_or_None).
    """
    for row in existing_entities:
        canonical = row["canonical_name"]
        aliases_raw = row.get("aliases", "[]")
        try:
            aliases = json.loads(aliases_raw) if isinstance(aliases_raw, str) else aliases_raw
        except (json.JSONDecodeError, TypeError):
            aliases = []

        if fuzzy_match(name, canonical, aliases):
            return (canonical, canonical)

    return (name, None)
```

- [ ] **Step 4: Run dedup tests**

```bash
python -m pytest tests/test_entities/test_dedup.py -v
```

Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add niche_radar/entities/dedup.py tests/test_entities/test_dedup.py
git commit -m "feat(entities): add entity name deduplication with fuzzy matching"
```

---

### Task 5: Entity Repository

**Files:**
- Create: `niche_radar/entities/repository.py`
- Create: `tests/test_entities/test_repository.py`

- [ ] **Step 1: Write the failing integration test**

Create `tests/test_entities/test_repository.py`:

```python
"""Integration tests for entity repository (requires db fixture)."""
import json
import pytest
from niche_radar.entities.repository import (
    upsert_entity,
    link_mention,
    get_entities,
    get_entity_by_id,
    get_trending_entities,
    get_entity_mentions,
    get_existing_entities_for_dedup,
    compute_entity_velocity,
    ENTITY_TYPES,
)


class TestUpsertEntity:
    def test_create_new_entity(self, db):
        entity_id = upsert_entity(
            db,
            canonical_name="Notion",
            entity_type="product",
            aliases=["Notion.so"],
        )
        assert entity_id is not None

        row = db.execute(
            "SELECT canonical_name, type, mention_count FROM entities WHERE id=?",
            (entity_id,),
        ).fetchone()
        assert row["canonical_name"] == "Notion"
        assert row["type"] == "product"
        assert row["mention_count"] == 1

    def test_update_existing_entity(self, db):
        eid1 = upsert_entity(db, canonical_name="Notion", entity_type="product")
        eid2 = upsert_entity(db, canonical_name="Notion", entity_type="product")

        assert eid1 == eid2

        row = db.execute(
            "SELECT mention_count, source_diversity FROM entities WHERE id=?",
            (eid1,),
        ).fetchone()
        assert row["mention_count"] == 2

    def test_merge_aliases(self, db):
        upsert_entity(db, canonical_name="Notion", entity_type="product", aliases=["Notion.so"])
        upsert_entity(db, canonical_name="Notion", entity_type="product", aliases=["notion.com"])

        row = db.execute(
            "SELECT aliases FROM entities WHERE canonical_name='Notion'"
        ).fetchone()
        aliases = json.loads(row["aliases"])
        assert "Notion.so" in aliases
        assert "notion.com" in aliases


class TestLinkMention:
    def test_link_mention_creates_join(self, db):
        # Insert raw item first
        db.execute(
            "INSERT OR IGNORE INTO raw_items (id, source, source_id, title, body) "
            "VALUES (?, ?, ?, ?, ?)",
            ("item-001", "reddit", "src-001", "Test", "Test body"),
        )
        db.commit()

        entity_id = upsert_entity(db, canonical_name="Notion", entity_type="product")
        link_mention(db, entity_id=entity_id, raw_item_id="item-001",
                     sentiment="positive", relevance=0.9)

        row = db.execute(
            "SELECT * FROM entity_mentions WHERE entity_id=? AND raw_item_id=?",
            (entity_id, "item-001"),
        ).fetchone()
        assert row is not None
        assert row["sentiment"] == "positive"

    def test_link_mention_updates_entity_counts(self, db):
        db.execute(
            "INSERT OR IGNORE INTO raw_items (id, source, source_id, title, body) "
            "VALUES (?, ?, ?, ?, ?)",
            ("item-002", "hn", "src-002", "Test", "Test"),
        )
        db.commit()

        entity_id = upsert_entity(db, canonical_name="Stripe", entity_type="company")
        link_mention(db, entity_id=entity_id, raw_item_id="item-002",
                     sentiment="neutral", relevance=0.7)

        row = db.execute(
            "SELECT mention_count, source_diversity FROM entities WHERE id=?",
            (entity_id,),
        ).fetchone()
        assert row["mention_count"] == 1
        assert row["source_diversity"] == 1


class TestGetEntities:
    def test_paginated_list(self, db):
        for i in range(5):
            upsert_entity(db, canonical_name=f"Entity{i}", entity_type="company")

        results = get_entities(db, limit=3, offset=0)
        assert len(results) == 3

    def test_filter_by_type(self, db):
        upsert_entity(db, canonical_name="Notion", entity_type="product")
        upsert_entity(db, canonical_name="Stripe", entity_type="company")
        upsert_entity(db, canonical_name="Rust", entity_type="technology")

        results = get_entities(db, entity_type="product")
        assert len(results) == 1
        assert results[0]["canonical_name"] == "Notion"

    def test_sorted_by_mention_count(self, db):
        e1 = upsert_entity(db, canonical_name="Hot Thing", entity_type="technology")
        e2 = upsert_entity(db, canonical_name="Cold Thing", entity_type="technology")
        # Boost Hot Thing
        for _ in range(3):
            upsert_entity(db, canonical_name="Hot Thing", entity_type="technology")

        results = get_entities(db, sort_by="mentions")
        assert results[0]["canonical_name"] == "Hot Thing"


class TestGetTrendingEntities:
    def test_returns_top_by_velocity(self, db):
        e1 = upsert_entity(db, canonical_name="Surging", entity_type="technology")
        e2 = upsert_entity(db, canonical_name="Stable", entity_type="technology")

        # Set velocity scores directly
        db.execute("UPDATE entities SET velocity_score=? WHERE id=?", (150.0, e1))
        db.execute("UPDATE entities SET velocity_score=? WHERE id=?", (5.0, e2))
        db.commit()

        results = get_trending_entities(db, limit=5)
        assert len(results) >= 1
        assert results[0]["canonical_name"] == "Surging"


class TestComputeEntityVelocity:
    def test_computes_velocity_for_all_entities(self, db):
        entity_id = upsert_entity(db, canonical_name="TestCo", entity_type="company")
        db.execute(
            "INSERT INTO entity_velocity (entity_id, week_start, mention_count, source_count) "
            "VALUES (?, date('now', '-7 days'), ?, ?)",
            (entity_id, 3, 2),
        )
        db.execute(
            "INSERT INTO entity_velocity (entity_id, week_start, mention_count, source_count) "
            "VALUES (?, date('now'), ?, ?)",
            (entity_id, 10, 4),
        )
        db.commit()

        compute_entity_velocity(db)

        row = db.execute(
            "SELECT velocity_score FROM entities WHERE id=?", (entity_id,)
        ).fetchone()
        assert row["velocity_score"] > 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_entities/test_repository.py -v
```

Expected: FAIL.

- [ ] **Step 3: Create the repository module**

Create `niche_radar/entities/repository.py`:

```python
"""SQLite CRUD operations for entities, mentions, and velocity tracking."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import date, datetime, timezone, timedelta

ENTITY_TYPES = ("company", "product", "technology", "person", "category")


def upsert_entity(
    db: sqlite3.Connection,
    canonical_name: str,
    entity_type: str,
    aliases: list[str] | None = None,
    source: str | None = None,
) -> str:
    """Create or update an entity. Returns the entity ID."""
    now = datetime.now(timezone.utc).isoformat()

    row = db.execute(
        "SELECT id, aliases, mention_count, source_diversity FROM entities WHERE canonical_name=?",
        (canonical_name,),
    ).fetchone()

    if row:
        entity_id = row["id"]
        existing_aliases = json.loads(row["aliases"]) if row["aliases"] else []
        new_aliases = list(set(existing_aliases + (aliases or [])))
        new_count = row["mention_count"] + 1

        db.execute(
            "UPDATE entities SET aliases=?, mention_count=?, last_seen=?, source_diversity="
            "CASE WHEN ? IS NOT NULL AND source_diversity < ("
            "  SELECT COUNT(DISTINCT source) FROM entity_mentions WHERE entity_id=?"
            ") + 1 THEN ("
            "  SELECT COUNT(DISTINCT source) FROM entity_mentions WHERE entity_id=?"
            ") + 1 ELSE source_diversity END "
            "WHERE id=?",
            (json.dumps(new_aliases), new_count, now, source, entity_id, entity_id, entity_id),
        )
        db.commit()
        return entity_id

    entity_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO entities (id, type, canonical_name, aliases, first_seen, last_seen, mention_count) "
        "VALUES (?, ?, ?, ?, ?, ?, 1)",
        (entity_id, entity_type, canonical_name, json.dumps(aliases or []), now, now),
    )
    db.commit()
    return entity_id


def link_mention(
    db: sqlite3.Connection,
    entity_id: str,
    raw_item_id: str,
    sentiment: str = "neutral",
    relevance: float = 1.0,
) -> None:
    """Link an entity to a raw item via entity_mentions. Idempotent."""
    db.execute(
        "INSERT OR IGNORE INTO entity_mentions (entity_id, raw_item_id, sentiment, relevance) "
        "VALUES (?, ?, ?, ?)",
        (entity_id, raw_item_id, sentiment, relevance),
    )

    # Update source diversity after linking
    row = db.execute(
        "SELECT COUNT(DISTINCT ri.source) FROM entity_mentions em "
        "JOIN raw_items ri ON ri.id = em.raw_item_id "
        "WHERE em.entity_id = ?",
        (entity_id,),
    ).fetchone()
    source_count = row[0] if row else 0

    db.execute(
        "UPDATE entities SET source_diversity=? WHERE id=?",
        (source_count, entity_id),
    )
    db.commit()


def get_existing_entities_for_dedup(db: sqlite3.Connection) -> list[dict]:
    """Return all existing entities as dicts for dedup resolution."""
    rows = db.execute(
        "SELECT id, canonical_name, aliases FROM entities"
    ).fetchall()
    return [{"id": r["id"], "canonical_name": r["canonical_name"], "aliases": r["aliases"]} for r in rows]


def get_entities(
    db: sqlite3.Connection,
    entity_type: str | None = None,
    sort_by: str = "last_seen",
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """Paginated entity list with optional type filter."""
    valid_sorts = {"last_seen", "mentions", "velocity"}
    if sort_by not in valid_sorts:
        sort_by = "last_seen"
    sort_col = {
        "last_seen": "last_seen DESC",
        "mentions": "mention_count DESC",
        "velocity": "velocity_score DESC",
    }[sort_by]

    if entity_type and entity_type in ENTITY_TYPES:
        rows = db.execute(
            f"SELECT * FROM entities WHERE type=? ORDER BY {sort_col} LIMIT ? OFFSET ?",
            (entity_type, limit, offset),
        ).fetchall()
    else:
        rows = db.execute(
            f"SELECT * FROM entities ORDER BY {sort_col} LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()

    return [dict(r) for r in rows]


def get_entity_by_id(db: sqlite3.Connection, entity_id: str) -> dict | None:
    """Get a single entity with stats."""
    row = db.execute(
        "SELECT * FROM entities WHERE id=?", (entity_id,)
    ).fetchone()
    if not row:
        return None
    result = dict(row)
    result["aliases"] = json.loads(result["aliases"]) if result["aliases"] else []

    # Attach recent mentions
    mentions = db.execute(
        "SELECT em.*, ri.title, ri.source, ri.url FROM entity_mentions em "
        "JOIN raw_items ri ON ri.id = em.raw_item_id "
        "WHERE em.entity_id=? ORDER BY em.extracted_at DESC LIMIT 20",
        (entity_id,),
    ).fetchall()
    result["recent_mentions"] = [dict(m) for m in mentions]

    # Attach velocity trend
    vel_rows = db.execute(
        "SELECT * FROM entity_velocity WHERE entity_id=? ORDER BY week_start DESC LIMIT 8",
        (entity_id,),
    ).fetchall()
    result["velocity_history"] = [dict(v) for v in reversed(vel_rows)]

    return result


def get_trending_entities(
    db: sqlite3.Connection,
    limit: int = 10,
    entity_type: str | None = None,
) -> list[dict]:
    """Entities with highest velocity scores."""
    if entity_type and entity_type in ENTITY_TYPES:
        rows = db.execute(
            "SELECT * FROM entities WHERE type=? AND mention_count >= 2 "
            "ORDER BY velocity_score DESC LIMIT ?",
            (entity_type, limit),
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM entities WHERE mention_count >= 2 "
            "ORDER BY velocity_score DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_entity_mentions(
    db: sqlite3.Connection,
    entity_id: str,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """Paginated mentions for an entity."""
    rows = db.execute(
        "SELECT em.*, ri.title, ri.source, ri.url, ri.collected_at "
        "FROM entity_mentions em "
        "JOIN raw_items ri ON ri.id = em.raw_item_id "
        "WHERE em.entity_id=? ORDER BY em.extracted_at DESC LIMIT ? OFFSET ?",
        (entity_id, limit, offset),
    ).fetchall()
    return [dict(r) for r in rows]


def compute_entity_velocity(db: sqlite3.Connection) -> None:
    """Compute week-over-week velocity for all entities and persist to entity_velocity and entities tables.

    This is called from the scheduler after each collection + extraction cycle.
    """
    today = date.today()
    this_week_start = today - timedelta(days=today.weekday())
    last_week_start = this_week_start - timedelta(weeks=1)

    entities = db.execute("SELECT id, canonical_name FROM entities").fetchall()

    for entity in entities:
        eid = entity["id"]

        # Count mentions this week
        this_week = db.execute(
            "SELECT COUNT(*) as cnt FROM entity_mentions WHERE entity_id=? AND extracted_at >= ?",
            (eid, this_week_start.isoformat()),
        ).fetchone()
        this_count = this_week["cnt"]

        # Count distinct sources this week
        this_sources = db.execute(
            "SELECT COUNT(DISTINCT ri.source) FROM entity_mentions em "
            "JOIN raw_items ri ON ri.id = em.raw_item_id "
            "WHERE em.entity_id=? AND em.extracted_at >= ?",
            (eid, this_week_start.isoformat()),
        ).fetchone()

        # Get last week's count
        last_week = db.execute(
            "SELECT mention_count FROM entity_velocity WHERE entity_id=? AND week_start=?",
            (eid, last_week_start.isoformat()),
        ).fetchone()
        last_count = last_week["mention_count"] if last_week else 0

        # Compute velocity score
        if last_count > 0:
            score = ((this_count - last_count) / last_count) * 100
        elif this_count > 0:
            score = 100.0
        else:
            score = 0.0

        label = _velocity_label(score)

        # Upsert velocity record for this week
        db.execute(
            "INSERT OR REPLACE INTO entity_velocity "
            "(entity_id, week_start, mention_count, source_count, velocity_label, velocity_score) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (eid, this_week_start.isoformat(), this_count, this_sources["cnt"], label, score),
        )

        # Update current velocity on entity
        db.execute(
            "UPDATE entities SET velocity_score=? WHERE id=?",
            (score, eid),
        )

    db.commit()


def _velocity_label(score: float) -> str:
    if score > 100:
        return "surging"
    elif score > 25:
        return "growing"
    elif score >= -25:
        return "stable"
    else:
        return "declining"
```

- [ ] **Step 4: Run repository tests**

```bash
python -m pytest tests/test_entities/test_repository.py -v
```

Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add niche_radar/entities/repository.py tests/test_entities/test_repository.py
git commit -m "feat(entities): add repository layer for entity CRUD, mentions, and velocity"
```

---

### Task 6: Entity Service (Orchestration)

**Files:**
- Create: `niche_radar/entities/service.py`
- Create: `tests/test_entities/test_service.py`

- [ ] **Step 1: Write the failing integration test**

Create `tests/test_entities/test_service.py`:

```python
"""Integration tests for the EntityService orchestration layer."""
import json
import pytest
from niche_radar.entities.service import EntityService
from niche_radar.entities.models import EntityExtractionResult, ExtractedEntity


class FakeLLM:
    def __init__(self, entities_to_return):
        self._entities = entities_to_return
        self.call_count = 0

    def complete_structured(self, system, user, temperature=None):
        self.call_count += 1
        return {"entities": self._entities}


class TestEntityService:
    def test_process_item_extracts_and_stores(self, db):
        # Insert a raw item
        db.execute(
            "INSERT OR IGNORE INTO raw_items (id, source, source_id, title, body) "
            "VALUES (?, ?, ?, ?, ?)",
            ("item-svc-1", "hn", "src-svc-1", "Notion AI is great",
             "I love using Notion for project management."),
        )
        db.commit()

        fake_llm = FakeLLM([
            {"name": "Notion", "type": "product", "sentiment": "positive",
             "relevance": 0.9, "aliases": ["Notion.so"]},
            {"name": "AI", "type": "technology", "sentiment": "positive",
             "relevance": 0.7, "aliases": []},
        ])

        service = EntityService(llm=fake_llm, db=db, sample_rate=1.0)
        result = service.process_item(item_id="item-svc-1")

        assert result is not None
        assert len(result) == 2

        # Check entities were created
        notion = db.execute(
            "SELECT * FROM entities WHERE canonical_name='Notion'"
        ).fetchone()
        assert notion is not None
        assert notion["type"] == "product"

        ai_ent = db.execute(
            "SELECT * FROM entities WHERE canonical_name='AI'"
        ).fetchone()
        assert ai_ent is not None

        # Check mentions were linked
        mentions = db.execute(
            "SELECT COUNT(*) as cnt FROM entity_mentions WHERE raw_item_id='item-svc-1'"
        ).fetchone()
        assert mentions["cnt"] == 2

    def test_process_item_respects_sample_rate(self, db):
        db.execute(
            "INSERT OR IGNORE INTO raw_items (id, source, source_id, title, body) "
            "VALUES (?, ?, ?, ?, ?)",
            ("item-svc-2", "hn", "src-svc-2", "Test", "Test body content here"),
        )
        db.commit()

        fake_llm = FakeLLM([
            {"name": "TestCo", "type": "company", "sentiment": "neutral",
             "relevance": 0.5, "aliases": []},
        ])

        service = EntityService(llm=fake_llm, db=db, sample_rate=0.0)
        result = service.process_item(item_id="item-svc-2")

        assert result is not None
        assert len(result) == 0
        assert fake_llm.call_count == 0

    def test_process_item_deduplicates_across_items(self, db):
        db.execute(
            "INSERT OR IGNORE INTO raw_items (id, source, source_id, title, body) "
            "VALUES (?, ?, ?, ?, ?)",
            ("item-svc-3a", "reddit", "src-3a", "Notion rocks", "Notion is the best."),
        )
        db.execute(
            "INSERT OR IGNORE INTO raw_items (id, source, source_id, title, body) "
            "VALUES (?, ?, ?, ?, ?)",
            ("item-svc-3b", "hn", "src-3b", "Notion alternative?", "Looking for Notion alternatives."),
        )
        db.commit()

        class MultiCallFakeLLM:
            def __init__(self):
                self.call_count = 0
            def complete_structured(self, system, user, temperature=None):
                self.call_count += 1
                return {"entities": [
                    {"name": "Notion", "type": "product", "sentiment": "positive",
                     "relevance": 0.9, "aliases": ["Notion.so"]},
                ]}

        llm = MultiCallFakeLLM()
        service = EntityService(llm=llm, db=db, sample_rate=1.0)

        service.process_item(item_id="item-svc-3a")
        service.process_item(item_id="item-svc-3b")

        # Should be a single entity, not two
        row = db.execute(
            "SELECT COUNT(*) as cnt FROM entities WHERE canonical_name='Notion'"
        ).fetchone()
        assert row["cnt"] == 1

        entity = db.execute(
            "SELECT mention_count FROM entities WHERE canonical_name='Notion'"
        ).fetchone()
        assert entity["mention_count"] == 2

    def test_process_item_skips_short_text(self, db):
        db.execute(
            "INSERT OR IGNORE INTO raw_items (id, source, source_id, title, body) "
            "VALUES (?, ?, ?, ?, ?)",
            ("item-svc-4", "hn", "src-4", "Hi", "ok"),
        )
        db.commit()

        fake_llm = FakeLLM([])
        service = EntityService(llm=fake_llm, db=db, sample_rate=1.0, min_text_length=30)
        result = service.process_item(item_id="item-svc-4")

        assert result == []
        assert fake_llm.call_count == 0

    def test_process_item_handles_missing_item(self, db):
        fake_llm = FakeLLM([])
        service = EntityService(llm=fake_llm, db=db, sample_rate=1.0)
        result = service.process_item(item_id="nonexistent")

        assert result == []
        assert fake_llm.call_count == 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_entities/test_service.py -v
```

Expected: FAIL.

- [ ] **Step 3: Create the service module**

Create `niche_radar/entities/service.py`:

```python
"""EntityService — orchestrates extraction, dedup, and storage for the entity pipeline."""

from __future__ import annotations

import logging
import random

from niche_radar.entities.dedup import resolve_entity_name
from niche_radar.entities.extractor import EntityExtractor
from niche_radar.entities.repository import (
    get_existing_entities_for_dedup,
    link_mention,
    upsert_entity,
)
from niche_radar.llm.base import LLMClient

logger = logging.getLogger(__name__)


class EntityService:
    """Orchestrates entity extraction → dedup → storage for raw items.

    This is the public API of the entity subsystem. Call `process_item()`
    for each raw item after collection.
    """

    def __init__(
        self,
        llm: LLMClient,
        db,  # sqlite3.Connection
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

            # Update existing list so subsequent entities in the same batch
            # can match against freshly created entities
            existing.append({
                "id": entity_id,
                "canonical_name": canonical,
                "aliases": extracted.aliases,
            })

        return entity_ids
```

- [ ] **Step 4: Run service tests**

```bash
python -m pytest tests/test_entities/test_service.py -v
```

Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add niche_radar/entities/service.py tests/test_entities/test_service.py
git commit -m "feat(entities): add EntityService orchestration layer with sampling and dedup"
```

---

### Task 7: API Endpoints

**Files:**
- Modify: `niche_radar/api/server.py`
- Create: `tests/test_entities/test_api.py`

- [ ] **Step 1: Write the API test**

Create `tests/test_entities/test_api.py`:

```python
"""Tests for entity API endpoints."""
import json
import pytest
from fastapi.testclient import TestClient
from niche_radar.api.server import app
from niche_radar.entities.repository import upsert_entity, link_mention, compute_entity_velocity

client = TestClient(app)


class TestEntityEndpoints:
    def test_get_entities_empty(self, db):
        response = client.get("/api/entities")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_get_entities_with_data(self, db):
        upsert_entity(db, canonical_name="Notion", entity_type="product")
        upsert_entity(db, canonical_name="Stripe", entity_type="company")

        response = client.get("/api/entities")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    def test_get_entities_filter_by_type(self, db):
        upsert_entity(db, canonical_name="Notion", entity_type="product")
        upsert_entity(db, canonical_name="Stripe", entity_type="company")

        response = client.get("/api/entities?type=product")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["canonical_name"] == "Notion"

    def test_get_entities_pagination(self, db):
        for i in range(5):
            upsert_entity(db, canonical_name=f"Entity{i}", entity_type="company")

        response = client.get("/api/entities?limit=2&offset=0")
        data = response.json()
        assert len(data["items"]) == 2
        assert data["total"] == 5

    def test_get_entity_detail(self, db):
        eid = upsert_entity(db, canonical_name="Notion", entity_type="product",
                            aliases=["Notion.so"])
        db.execute(
            "INSERT OR IGNORE INTO raw_items (id, source, source_id, title, body) "
            "VALUES (?, ?, ?, ?, ?)",
            ("item-api-1", "hn", "src-api-1", "Notion AI", "Test body"),
        )
        db.commit()
        link_mention(db, entity_id=eid, raw_item_id="item-api-1",
                     sentiment="positive", relevance=0.9)

        response = client.get(f"/api/entities/{eid}")
        assert response.status_code == 200
        data = response.json()
        assert data["canonical_name"] == "Notion"
        assert "Notion.so" in data["aliases"]
        assert len(data["recent_mentions"]) >= 1

    def test_get_entity_detail_not_found(self, db):
        response = client.get("/api/entities/nonexistent-id")
        assert response.status_code == 404

    def test_get_trending_entities(self, db):
        e1 = upsert_entity(db, canonical_name="Hot Topic", entity_type="technology")
        e2 = upsert_entity(db, canonical_name="Cold Topic", entity_type="technology")
        db.execute("UPDATE entities SET velocity_score=? WHERE id=?", (200.0, e1))
        db.execute("UPDATE entities SET velocity_score=? WHERE id=?", (-10.0, e2))
        db.commit()

        response = client.get("/api/entities/trending")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["canonical_name"] == "Hot Topic"

    def test_get_entity_mentions(self, db):
        eid = upsert_entity(db, canonical_name="TestCo", entity_type="company")
        db.execute(
            "INSERT OR IGNORE INTO raw_items (id, source, source_id, title, body) "
            "VALUES (?, ?, ?, ?, ?)",
            ("item-api-2", "reddit", "src-api-2", "TestCo thing", "A body"),
        )
        db.commit()
        link_mention(db, entity_id=eid, raw_item_id="item-api-2")

        response = client.get(f"/api/entities/{eid}/mentions")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["source"] == "reddit"
```

- [ ] **Step 2: Run API tests to verify they fail**

```bash
python -m pytest tests/test_entities/test_api.py -v
```

Expected: FAIL — endpoints return 404.

- [ ] **Step 3: Add entity routes to server.py**

In `niche_radar/api/server.py`, add the entity routes after the existing routes. Add imports at the top:

```python
from niche_radar.entities.repository import (
    get_entities,
    get_entity_by_id,
    get_trending_entities,
    get_entity_mentions,
    ENTITY_TYPES,
)
```

Add route handlers before the `if __name__` guard:

```python
# ── Entity Intelligence Routes ──────────────────────────────────────────────

from niche_radar.entities.repository import (
    get_entities,
    get_entity_by_id,
    get_trending_entities,
    get_entity_mentions,
    ENTITY_TYPES,
)


@app.get("/api/entities")
def api_get_entities(
    type: str | None = None,
    sort: str = "last_seen",
    limit: int = 50,
    offset: int = 0,
):
    """List entities with optional type filter, sort, and pagination."""
    if type and type not in ENTITY_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid type. Must be one of: {', '.join(ENTITY_TYPES)}",
        )
    db = _db()
    items = get_entities(db, entity_type=type, sort_by=sort, limit=limit, offset=offset)
    total = db.execute(
        "SELECT COUNT(*) FROM entities" + (f" WHERE type='{type}'" if type else "")
    ).fetchone()[0]
    return {"items": items, "total": total}


@app.get("/api/entities/trending")
def api_get_trending_entities(type: str | None = None, limit: int = 10):
    """Top entities by velocity score."""
    if type and type not in ENTITY_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid type. Must be one of: {', '.join(ENTITY_TYPES)}",
        )
    db = _db()
    return get_trending_entities(db, limit=limit, entity_type=type)


@app.get("/api/entities/{entity_id}")
def api_get_entity_detail(entity_id: str):
    """Detailed entity view with stats, recent mentions, and velocity history."""
    db = _db()
    entity = get_entity_by_id(db, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity


@app.get("/api/entities/{entity_id}/mentions")
def api_get_entity_mentions(entity_id: str, limit: int = 50, offset: int = 0):
    """Paginated mentions for a specific entity."""
    db = _db()
    entity = get_entity_by_id(db, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    items = get_entity_mentions(db, entity_id, limit=limit, offset=offset)
    total = db.execute(
        "SELECT COUNT(*) FROM entity_mentions WHERE entity_id=?", (entity_id,)
    ).fetchone()[0]
    return {"items": items, "total": total}
```

- [ ] **Step 4: Run API tests**

```bash
python -m pytest tests/test_entities/test_api.py -v
```

Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add niche_radar/api/server.py tests/test_entities/test_api.py
git commit -m "feat(entities): add REST API endpoints for entity intelligence"
```

---

### Task 8: Scheduler Integration

**Files:**
- Modify: `niche_radar/scheduler.py`
- Modify: `niche_radar/config.py`

- [ ] **Step 1: Add config setting**

In `niche_radar/config.py`, add to the `Settings` class:

```python
    # Entity intelligence
    entity_extraction_sample_rate: float = 0.2  # fraction of items to extract (0.0–1.0)
```

- [ ] **Step 2: Add entity extraction job to scheduler**

In `niche_radar/scheduler.py`, add the entity extraction job. Read the existing scheduler first:

```python
# After collection completes, extract entities from new items
# then compute velocity weekly
```

The scheduler integration should:
- After each collection cycle, run entity extraction on newly collected items (respecting sample_rate)
- On a weekly schedule, compute entity velocity

- [ ] **Step 3: Read existing scheduler.py to understand patterns**

```bash
# Read the file first — then add:
# 1. An entity_extraction_job that processes unprocessed items
# 2. A velocity_computation_job that runs weekly
```

- [ ] **Step 4: Implement and commit**

```bash
git add niche_radar/scheduler.py niche_radar/config.py
git commit -m "feat(entities): integrate entity extraction into scheduler"
```

---

### Task 9: Run Full Test Suite

- [ ] **Step 1: Run all tests**

```bash
python -m pytest tests/ -v
```

Expected: All existing tests + new entity tests PASS.

- [ ] **Step 2: Fix any integration issues**

Address any test failures from interactions between new and existing code.

- [ ] **Step 3: Commit any fixes**

```bash
git add -A && git commit -m "fix(entities): resolve integration issues from full test suite"
```

---

## Dependency Order

```
Task 1 (Schema) ──┐
                  ├──> Task 2 (Models) ──> Task 3 (Extractor) ──┐
                  │                                               ├──> Task 6 (Service)
                  │                    Task 4 (Dedup) ────────────┘        │
                  │                    Task 5 (Repository) ────────────────┘
                  │                                                         │
                  └─────────────────────────────────────────────────────────┘
                                                                             │
                                                              Task 7 (API) ──┘
                                                                   │
                                                         Task 8 (Scheduler)
                                                                   │
                                                         Task 9 (Full Suite)
```

Tasks 2, 3, 4, 5 can be done in parallel after Task 1. Task 6 depends on 3, 4, 5. Task 7 depends on 5. Task 8 depends on 6+7. Task 9 is the final gate.
