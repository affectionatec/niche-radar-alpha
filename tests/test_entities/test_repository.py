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
            "SELECT mention_count FROM entities WHERE id=?",
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
        upsert_entity(db, canonical_name="Hot Thing", entity_type="technology")
        e2 = upsert_entity(db, canonical_name="Cold Thing", entity_type="technology")
        for _ in range(3):
            upsert_entity(db, canonical_name="Hot Thing", entity_type="technology")

        results = get_entities(db, sort_by="mentions")
        assert results[0]["canonical_name"] == "Hot Thing"


class TestGetTrendingEntities:
    def test_returns_top_by_velocity(self, db):
        e1 = upsert_entity(db, canonical_name="Surging", entity_type="technology")
        e2 = upsert_entity(db, canonical_name="Stable", entity_type="technology")
        # Bump mention count so they pass the ">= 2" filter
        upsert_entity(db, canonical_name="Surging", entity_type="technology")
        upsert_entity(db, canonical_name="Stable", entity_type="technology")

        db.execute("UPDATE entities SET velocity_score=? WHERE id=?", (150.0, e1))
        db.execute("UPDATE entities SET velocity_score=? WHERE id=?", (5.0, e2))
        db.commit()

        results = get_trending_entities(db, limit=5)
        assert len(results) >= 1
        assert results[0]["canonical_name"] == "Surging"


class TestGetEntityByID:
    def test_returns_none_for_missing(self, db):
        result = get_entity_by_id(db, "nonexistent")
        assert result is None

    def test_returns_entity_with_mentions(self, db):
        eid = upsert_entity(db, canonical_name="TestCo", entity_type="company")
        db.execute(
            "INSERT OR IGNORE INTO raw_items (id, source, source_id, title, body) "
            "VALUES (?, ?, ?, ?, ?)",
            ("item-detail", "hn", "src-detail", "TestCo news", "Something about TestCo"),
        )
        db.commit()
        link_mention(db, entity_id=eid, raw_item_id="item-detail")

        result = get_entity_by_id(db, eid)
        assert result is not None
        assert result["canonical_name"] == "TestCo"
        assert "recent_mentions" in result
        assert "velocity_history" in result


class TestComputeEntityVelocity:
    def test_computes_velocity_for_entities(self, db):
        entity_id = upsert_entity(db, canonical_name="TestCo", entity_type="company")
        db.execute(
            "INSERT OR IGNORE INTO raw_items (id, source, source_id, title, body) "
            "VALUES (?, ?, ?, ?, ?)",
            ("item-vel-1", "reddit", "src-vel-1", "TestCo news", "TestCo is trending"),
        )
        db.commit()

        link_mention(db, entity_id=entity_id, raw_item_id="item-vel-1")

        # Should run without error and produce a velocity record
        compute_entity_velocity(db)

        row = db.execute(
            "SELECT velocity_score FROM entities WHERE id=?", (entity_id,)
        ).fetchone()
        assert row is not None
        assert isinstance(row["velocity_score"], (int, float))


class TestGetExistingEntitiesForDedup:
    def test_returns_entities_for_dedup(self, db):
        upsert_entity(db, canonical_name="Notion", entity_type="product", aliases=["Notion.so"])
        upsert_entity(db, canonical_name="Stripe", entity_type="company")

        results = get_existing_entities_for_dedup(db)
        assert len(results) == 2
        assert results[0]["canonical_name"] in ("Notion", "Stripe")
