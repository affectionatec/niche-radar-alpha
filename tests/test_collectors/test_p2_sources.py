"""Tests for P2 collectors: Indie Hackers, App Store, Play Store."""

import pytest
from niche_radar.config import Settings


@pytest.fixture
def settings():
    return Settings()


def test_indie_hackers_dry_run(settings):
    from niche_radar.collectors.indie_hackers import IndieHackersCollector
    result = IndieHackersCollector().collect(settings=settings, dry_run=True)
    assert result.items_collected == 0
    assert result.status == "completed"


def test_app_store_dry_run(settings):
    from niche_radar.collectors.app_store import AppStoreCollector
    result = AppStoreCollector().collect(settings=settings, dry_run=True)
    assert result.items_collected == 0


def test_play_store_dry_run(settings):
    from niche_radar.collectors.play_store import PlayStoreCollector
    result = PlayStoreCollector().collect(settings=settings, dry_run=True)
    assert result.items_collected == 0


def test_app_store_without_app_ids_returns_failed(settings, tmp_path):
    from niche_radar.collectors.app_store import AppStoreCollector
    from niche_radar.storage.database import get_db
    db = get_db(f"sqlite:///{tmp_path / 'test.db'}")
    result = AppStoreCollector().collect(settings=settings, db=db)
    assert result.status == "failed"
    assert result.error_message is not None


def test_play_store_without_app_ids_returns_failed(settings, tmp_path):
    from niche_radar.collectors.play_store import PlayStoreCollector
    from niche_radar.storage.database import get_db
    db = get_db(f"sqlite:///{tmp_path / 'test.db'}")
    result = PlayStoreCollector().collect(settings=settings, db=db)
    assert result.status == "failed"


def test_all_p2_sources_importable():
    from niche_radar.collectors import _get_collector
    for slug in ("indie_hackers", "app_store", "play_store"):
        c = _get_collector(slug)
        assert c.source_name == slug
        assert hasattr(c, "CREDENTIAL_SCHEMA")
