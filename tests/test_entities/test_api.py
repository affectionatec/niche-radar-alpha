"""Tests for entity intelligence API endpoints."""
from __future__ import annotations

import os

from niche_radar.entities.repository import (
    upsert_entity,
    link_mention,
    get_entity_by_id,
)
from niche_radar.storage.database import get_db


def _db():
    return get_db(os.environ["DATABASE_URL"])


class TestEntityEndpoints:
    def test_get_entities_empty(self, client):
        response = client.get("/api/entities")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_get_entities_with_data(self, client):
        db = _db()
        upsert_entity(db, canonical_name="Notion", entity_type="product")
        upsert_entity(db, canonical_name="Stripe", entity_type="company")
        db.close()

        response = client.get("/api/entities")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    def test_get_entities_filter_by_type(self, client):
        db = _db()
        upsert_entity(db, canonical_name="Notion", entity_type="product")
        upsert_entity(db, canonical_name="Stripe", entity_type="company")
        db.close()

        response = client.get("/api/entities?type=product")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["canonical_name"] == "Notion"

    def test_get_entities_pagination(self, client):
        db = _db()
        for i in range(5):
            upsert_entity(db, canonical_name=f"PagEntity{i}", entity_type="company")
        db.close()

        response = client.get("/api/entities?limit=2&offset=0")
        data = response.json()
        assert len(data["items"]) == 2
        assert data["total"] >= 5

    def test_get_entity_detail(self, client):
        db = _db()
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
        db.close()

        response = client.get(f"/api/entities/{eid}")
        assert response.status_code == 200
        data = response.json()
        assert data["canonical_name"] == "Notion"
        assert "Notion.so" in data["aliases"]
        assert len(data["recent_mentions"]) >= 1

    def test_get_entity_detail_not_found(self, client):
        response = client.get("/api/entities/nonexistent-id")
        assert response.status_code == 404

    def test_get_trending_entities(self, client):
        db = _db()
        e1 = upsert_entity(db, canonical_name="Hot Topic", entity_type="technology")
        e2 = upsert_entity(db, canonical_name="Cold Topic", entity_type="technology")
        # Bump mention counts to meet the ">= 2" threshold
        upsert_entity(db, canonical_name="Hot Topic", entity_type="technology")
        upsert_entity(db, canonical_name="Cold Topic", entity_type="technology")
        db.execute("UPDATE entities SET velocity_score=? WHERE id=?", (200.0, e1))
        db.execute("UPDATE entities SET velocity_score=? WHERE id=?", (-10.0, e2))
        db.commit()
        db.close()

        response = client.get("/api/entities/trending")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["canonical_name"] == "Hot Topic"

    def test_get_entity_mentions(self, client):
        db = _db()
        eid = upsert_entity(db, canonical_name="TestCo", entity_type="company")
        db.execute(
            "INSERT OR IGNORE INTO raw_items (id, source, source_id, title, body) "
            "VALUES (?, ?, ?, ?, ?)",
            ("item-api-2", "reddit", "src-api-2", "TestCo thing", "A body"),
        )
        db.commit()
        link_mention(db, entity_id=eid, raw_item_id="item-api-2")
        db.close()

        response = client.get(f"/api/entities/{eid}/mentions")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["source"] == "reddit"

    def test_invalid_type_returns_422(self, client):
        response = client.get("/api/entities?type=invalid")
        assert response.status_code == 422

    def test_invalid_trending_type_returns_422(self, client):
        response = client.get("/api/entities/trending?type=invalid")
        assert response.status_code == 422
