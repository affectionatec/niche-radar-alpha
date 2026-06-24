"""Tests for the yt-dlp YouTube backend and the multi-backend YouTube collector.

All subprocess/CLI is mocked via the module-level seams (`ytdlp_available`,
`search_videos`, `fetch_transcript`) — these run fully offline and never invoke
the real yt-dlp binary.
"""

from __future__ import annotations

import pytest

from niche_radar.collectors import youtube
from niche_radar.collectors.backends import ytdlp
from niche_radar.config import Settings


@pytest.fixture
def settings():
    s = Settings()
    s.max_retries = 1
    return s


# ── availability ─────────────────────────────────────────────────────────────

def test_ytdlp_available_false_when_binary_absent(monkeypatch, settings):
    monkeypatch.setattr(ytdlp.shutil, "which", lambda *_a, **_k: None)
    assert ytdlp.ytdlp_available() is False
    assert ytdlp.YtDlpBackend().is_available(settings, None) is False


def test_ytdlp_available_true_when_binary_present(monkeypatch, settings):
    monkeypatch.setattr(ytdlp.shutil, "which", lambda *_a, **_k: "/usr/bin/yt-dlp")
    assert ytdlp.ytdlp_available() is True
    assert ytdlp.YtDlpBackend().is_available(settings, None) is True


def test_available_never_raises(monkeypatch):
    def boom(*_a, **_k):
        raise OSError("which exploded")

    monkeypatch.setattr(ytdlp.shutil, "which", boom)
    assert ytdlp.ytdlp_available() is False  # swallowed


# ── vtt parsing ──────────────────────────────────────────────────────────────

def test_vtt_to_text_strips_and_dedupes():
    vtt = (
        "WEBVTT\nKind: captions\nLanguage: en\n\n"
        "00:00:01.000 --> 00:00:03.000\n<c>I wish</c> there was a tool\n\n"
        "00:00:03.000 --> 00:00:05.000\nI wish there was a tool\n\n"
        "2\n00:00:05.000 --> 00:00:07.000\nfor managing feedback\n"
    )
    text = ytdlp.vtt_to_text(vtt)
    assert text == "I wish there was a tool for managing feedback"


# ── normalization ────────────────────────────────────────────────────────────

def test_normalize_folds_transcript_into_body():
    video = {
        "id": "abc123",
        "title": "The tool nobody built",
        "description": "creators keep asking for X",
        "view_count": 4200,
        "channel": "Indie Devs",
        "transcript": "honestly I wish there was an app that did X",
    }
    item = ytdlp.normalize_video(video, "AI tools", cutoff=None)
    assert item["source_id"] == "abc123"
    assert item["score"] == 4200
    assert item["metadata"]["has_transcript"] is True
    assert "Transcript:\nhonestly I wish there was an app" in item["body"]
    assert item["url"] == "https://www.youtube.com/watch?v=abc123"


def test_normalize_drops_stale_video():
    from datetime import datetime, timezone

    cutoff = datetime(2026, 6, 1, tzinfo=timezone.utc)
    stale = {"id": "old", "title": "t", "upload_date": "20240101"}
    assert ytdlp.normalize_video(stale, "q", cutoff) is None


def test_normalize_returns_none_without_id():
    assert ytdlp.normalize_video({"title": "no id"}, "q", None) is None


# ── backend fetch ────────────────────────────────────────────────────────────

def test_fetch_maps_videos_and_enriches_transcripts(monkeypatch, settings):
    def fake_search(query, limit, **kw):
        return [
            {"id": "v1", "title": "AI tool gap", "description": "people want X",
             "view_count": 5000, "transcript": "I wish there was a tool for X"},
            {"id": "v2", "title": "SaaS pain", "description": "billing is hard", "view_count": 1200},
        ]

    monkeypatch.setattr(ytdlp, "search_videos", fake_search)
    monkeypatch.setattr(ytdlp, "fetch_transcript", lambda vid, **k: "auto caption text" if vid == "v2" else "")

    items = ytdlp.YtDlpBackend(["q1", "q2"]).fetch(settings, None)
    by_id = {i["source_id"]: i for i in items}
    assert set(by_id) == {"v1", "v2"}
    # v1 carried an inline transcript; v2 was enriched via fetch_transcript
    assert "Transcript:\nI wish there was a tool for X" in by_id["v1"]["body"]
    assert "auto caption text" in by_id["v2"]["body"]
    assert by_id["v1"]["metadata"]["has_transcript"] and by_id["v2"]["metadata"]["has_transcript"]
    # same ids across both queries → merged, not duplicated
    assert set(by_id["v1"]["metadata"]["queries"]) == {"q1", "q2"}


def test_fetch_raises_when_all_searches_fail(monkeypatch, settings):
    def boom(query, limit, **kw):
        raise RuntimeError("yt-dlp exited 1")

    monkeypatch.setattr(ytdlp, "search_videos", boom)
    with pytest.raises(RuntimeError):
        ytdlp.YtDlpBackend(["q1"]).fetch(settings, None)


def test_transcript_enrichment_is_capped(monkeypatch, settings):
    calls = {"n": 0}

    def fake_search(query, limit, **kw):
        return [{"id": f"vid{i}", "title": "t", "description": "d"} for i in range(5)]

    def counting_transcript(vid, **k):
        calls["n"] += 1
        return "x"

    monkeypatch.setattr(ytdlp, "search_videos", fake_search)
    monkeypatch.setattr(ytdlp, "fetch_transcript", counting_transcript)
    ytdlp.YtDlpBackend(["q1"], max_transcripts=2).fetch(settings, None)
    assert calls["n"] == 2  # stopped after the cap


# ── collector ordering ───────────────────────────────────────────────────────

def test_youtube_uses_ytdlp_when_available(monkeypatch, settings):
    monkeypatch.setattr(ytdlp, "ytdlp_available", lambda: True)
    monkeypatch.setattr(ytdlp, "search_videos",
                        lambda q, limit, **kw: [{"id": "yt1", "title": "t", "description": "d"}])
    monkeypatch.setattr(ytdlp, "fetch_transcript", lambda vid, **k: "")

    result = youtube.YouTubeCollector().collect(settings=settings)
    assert result.status == "completed"
    assert result.metadata["active_backend"] == "yt_dlp"
    assert result.items[0]["source_id"] == "yt1"


def test_youtube_falls_through_to_legacy_when_no_ytdlp(monkeypatch, settings):
    monkeypatch.setattr(ytdlp, "ytdlp_available", lambda: False)
    monkeypatch.setattr(
        youtube.YouTubeApiScrapeBackend, "fetch",
        lambda self, s, db: [{"source_id": "legacy1", "title": "t", "body": "b",
                              "url": "u", "metadata": {"source": "scrapetube"}}],
    )
    result = youtube.YouTubeCollector().collect(settings=settings)
    assert result.status == "completed"
    assert result.metadata["active_backend"] == "youtube_api_scrape"
    assert result.items[0]["source_id"] == "legacy1"


def test_youtube_dry_run_short_circuits(settings):
    result = youtube.YouTubeCollector().collect(settings=settings, dry_run=True)
    assert result.items_collected == 0
    assert result.status == "completed"
