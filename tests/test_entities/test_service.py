"""Integration tests for the EntityService orchestration layer."""
import json
import pytest
from niche_radar.entities.service import EntityService


class FakeLLM:
    def __init__(self, entities_to_return):
        self._entities = entities_to_return
        self.call_count = 0

    def complete_structured(self, system, user, temperature=None):
        self.call_count += 1
        return {"entities": self._entities}


class TestEntityService:
    def test_process_item_extracts_and_stores(self, db):
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

        notion = db.execute(
            "SELECT * FROM entities WHERE canonical_name='Notion'"
        ).fetchone()
        assert notion is not None
        assert notion["type"] == "product"

        ai_ent = db.execute(
            "SELECT * FROM entities WHERE canonical_name='AI'"
        ).fetchone()
        assert ai_ent is not None

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
