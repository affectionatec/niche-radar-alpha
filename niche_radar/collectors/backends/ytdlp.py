"""yt-dlp source backend — keyless, transcript-bearing YouTube capture.

[yt-dlp](https://github.com/yt-dlp/yt-dlp) reads YouTube without an API key (so
no Data API quota) and exposes the *full* video description plus auto-caption
transcripts — a far richer pain signal than the Data API's truncated snippet.
It is the preferred YouTube backend when the ``yt-dlp`` binary is present;
``youtube.py`` falls back to the Data-API/scrapetube path when it isn't.

The subprocess seams (``ytdlp_available``, ``search_videos``,
``fetch_transcript``) are module-level so tests mock them and run fully offline.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone

import structlog

from niche_radar.collectors.multi_backend import SourceBackend

logger = structlog.get_logger()

YTDLP_BINARY = "yt-dlp"
DEFAULT_QUERIES = ["AI tools", "SaaS alternative", "developer tools", "self-hosted"]


def ytdlp_available() -> bool:
    """True when the yt-dlp binary is on PATH. Never raises."""
    try:
        return shutil.which(YTDLP_BINARY) is not None
    except Exception:
        return False


def search_videos(query: str, limit: int, *, timeout: int = 90) -> list[dict]:
    """Run ``yt-dlp -j ytsearchN:query`` and return one parsed JSON dict per video.

    Raises ``RuntimeError`` on a non-zero exit so the backend records it and
    falls through.
    """
    cmd = [
        YTDLP_BINARY, "-j", "--skip-download", "--no-warnings",
        "--flat-playlist", f"ytsearch{limit}:{query}",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"yt-dlp search failed: {exc}") from exc
    if proc.returncode != 0:
        raise RuntimeError(f"yt-dlp exited {proc.returncode}: {(proc.stderr or '')[:200]}")
    out: list[dict] = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def fetch_transcript(video_id: str, *, timeout: int = 60) -> str:
    """Best-effort English auto-caption transcript as plain text. "" on any failure."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        with tempfile.TemporaryDirectory() as tmp:
            cmd = [
                YTDLP_BINARY, "--skip-download", "--write-auto-subs", "--write-subs",
                "--sub-langs", "en.*", "--sub-format", "vtt", "--no-warnings",
                "-o", os.path.join(tmp, "%(id)s.%(ext)s"), url,
            ]
            subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
            for fn in sorted(os.listdir(tmp)):
                if fn.endswith(".vtt"):
                    with open(os.path.join(tmp, fn), encoding="utf-8", errors="ignore") as fh:
                        return vtt_to_text(fh.read())
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return ""


def vtt_to_text(vtt: str) -> str:
    """Strip a WebVTT caption file down to deduplicated plain text."""
    lines: list[str] = []
    for raw in vtt.splitlines():
        line = raw.strip()
        if not line or line == "WEBVTT" or "-->" in line or line.isdigit():
            continue
        if line.startswith(("Kind:", "Language:", "NOTE")):
            continue
        line = re.sub(r"<[^>]+>", "", line)  # inline timing tags
        if line and (not lines or lines[-1] != line):  # drop consecutive dupes
            lines.append(line)
    return " ".join(lines)


def _parse_date(video: dict) -> datetime | None:
    ts = video.get("timestamp")
    if isinstance(ts, (int, float)):
        return datetime.fromtimestamp(ts, timezone.utc)
    ud = video.get("upload_date")
    if isinstance(ud, str) and len(ud) == 8 and ud.isdigit():
        return datetime(int(ud[:4]), int(ud[4:6]), int(ud[6:8]), tzinfo=timezone.utc)
    return None


def normalize_video(video: dict, query: str, cutoff: datetime | None) -> dict | None:
    """Map a yt-dlp video JSON into a raw item. Returns None if no id or stale.

    Transcript text present on the payload (``video['transcript']``) is folded
    into the body here; the backend additionally enriches via
    :func:`fetch_transcript` when the payload carries none.
    """
    vid = video.get("id")
    if not vid:
        return None
    posted = _parse_date(video)
    if posted is not None and cutoff is not None and posted < cutoff:
        return None  # stale — outside the freshness window
    description = (video.get("description") or "").strip()
    transcript = (video.get("transcript") or "").strip()
    has_transcript = bool(transcript)
    body = description
    if transcript:
        body = (description[:1500] + "\n\nTranscript:\n" + transcript[:6000]).strip()
    return {
        "source_id": vid,
        "title": (video.get("title") or vid)[:300],
        "body": body or None,
        "url": video.get("webpage_url") or f"https://www.youtube.com/watch?v={vid}",
        "score": video.get("view_count") if isinstance(video.get("view_count"), int) else None,
        "comment_count": video.get("comment_count") if isinstance(video.get("comment_count"), int) else None,
        "posted_at": posted.isoformat() if posted else None,
        "metadata": {
            "queries": [query],
            "channel": video.get("channel") or video.get("uploader"),
            "has_transcript": has_transcript,
            "source": "yt_dlp",
        },
    }


class YtDlpBackend(SourceBackend):
    """Keyless, transcript-capable YouTube capture via the yt-dlp CLI."""

    name = "yt_dlp"

    def __init__(self, queries: list[str] | None = None, *, per_query: int = 8, max_transcripts: int = 20):
        self._queries = queries or DEFAULT_QUERIES
        self._per_query = per_query
        self._max_transcripts = max_transcripts

    def is_available(self, settings, db) -> bool:
        return ytdlp_available()

    def fetch(self, settings, db) -> list[dict]:
        window_hours = getattr(settings, "freshness_youtube_hours", None)
        cutoff = (
            datetime.now(timezone.utc) - timedelta(hours=window_hours)
            if window_hours else None
        )
        items: dict[str, dict] = {}
        errors: list[str] = []
        transcripts = 0

        for query in self._queries:
            try:
                videos = search_videos(query, self._per_query)
            except Exception as exc:
                logger.warning("ytdlp_search_failed", query=query, error=str(exc))
                errors.append(f"{query}: {exc}")
                continue

            for video in videos:
                item = normalize_video(video, query, cutoff)
                if item is None:
                    continue
                sid = item["source_id"]
                existing = items.get(sid)
                if existing:
                    qs = existing["metadata"].setdefault("queries", [])
                    if query not in qs:
                        qs.append(query)
                    continue
                # Enrich with a transcript when the payload carried none (bounded).
                if not item["metadata"]["has_transcript"] and transcripts < self._max_transcripts:
                    text = fetch_transcript(sid)
                    if text:
                        item["body"] = ((item["body"] or "")[:1500] + "\n\nTranscript:\n" + text[:6000]).strip()
                        item["metadata"]["has_transcript"] = True
                        transcripts += 1
                items[sid] = item

        if not items and errors:
            raise RuntimeError("yt-dlp captured nothing: " + "; ".join(errors))
        return list(items.values())
