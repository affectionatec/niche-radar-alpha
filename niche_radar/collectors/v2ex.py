"""V2EX data collector — pain-point discovery from China's tech community.

Capture walks an ordered chain:

    1. v2_api  — V2EX API v2 (requires personal token from v2ex.com/settings/tokens)
               — queries configurable nodes (startup, qna, python, share) for
               targeted discovery; richer data including content field.
    2. v1_api  — V2EX API v1 (keyless, always available) — global hot + latest
               topics; less targeted but zero-config.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import ClassVar

import structlog

from niche_radar.collectors._http import get_json
from niche_radar.collectors.multi_backend import MultiBackendCollector, SourceBackend
from niche_radar.storage.repository import get_source_credential

logger = structlog.get_logger()

_V2_BASE = "https://www.v2ex.com/api/v2"
_V1_BASE = "https://www.v2ex.com/api"

DEFAULT_NODES = ["startup", "qna", "python", "share"]
_DEFAULT_FRESHNESS_HOURS = 72


def _cutoff(settings) -> datetime:
    hours = getattr(settings, "freshness_v2ex_hours", _DEFAULT_FRESHNESS_HOURS)
    return datetime.now(timezone.utc) - timedelta(hours=int(hours))


def _token(settings, db: sqlite3.Connection | None) -> str | None:
    val = get_source_credential(db, "v2ex", "api_token", None) if db else None
    return val or getattr(settings, "v2ex_api_token", None) or None


def _nodes(db: sqlite3.Connection | None) -> list[str]:
    raw = get_source_credential(db, "v2ex", "nodes", None) if db else None
    return json.loads(raw) if raw else DEFAULT_NODES


def _normalize(topic: dict, cutoff: datetime) -> dict[str, dict]:
    """Map a V2EX topic dict to a normalized raw item; returns {} if stale."""
    tid = str(topic.get("id") or "")
    if not tid:
        return {}
    created_ts = topic.get("created") or topic.get("last_modified")
    if created_ts:
        posted_dt = datetime.fromtimestamp(int(created_ts), tz=timezone.utc)
        if posted_dt < cutoff:
            return {}
    else:
        posted_dt = datetime.now(timezone.utc)

    member = topic.get("member") or {}
    node = topic.get("node") or {}

    return {
        tid: {
            "source_id": tid,
            "title": str(topic.get("title") or ""),
            "body": topic.get("content") or None,
            "url": topic.get("url") or f"https://www.v2ex.com/t/{tid}",
            "score": int(topic.get("replies") or 0),
            "comment_count": int(topic.get("replies") or 0),
            "posted_at": posted_dt.isoformat(),
            "metadata": {
                "node": node.get("name") if isinstance(node, dict) else str(node or ""),
                "node_title": node.get("title") if isinstance(node, dict) else "",
                "author": member.get("username") if isinstance(member, dict) else str(member or ""),
            },
        }
    }


class V2exV2ApiBackend(SourceBackend):
    """V2EX API v2 — node-targeted discovery (requires personal token)."""

    name = "v2_api"

    def is_available(self, settings, db: sqlite3.Connection | None) -> bool:
        return bool(_token(settings, db))

    def fetch(self, settings, db: sqlite3.Connection | None) -> list[dict]:
        token = _token(settings, db)
        nodes = _nodes(db)
        cutoff = _cutoff(settings)
        headers = {"Authorization": f"Bearer {token}"}
        items: dict[str, dict] = {}

        for node in nodes:
            try:
                data = get_json(f"{_V2_BASE}/nodes/{node}/topics", headers=headers)
                for topic in (data.get("result") or []):
                    items.update(_normalize(topic, cutoff))
            except Exception as exc:
                logger.warning("v2ex_v2_node_failed", node=node, error=str(exc))

        return list(items.values())


class V2exV1ApiBackend(SourceBackend):
    """V2EX API v1 — keyless hot + latest topics (always available)."""

    name = "v1_api"

    def is_available(self, settings, db: sqlite3.Connection | None) -> bool:
        return True

    def fetch(self, settings, db: sqlite3.Connection | None) -> list[dict]:
        cutoff = _cutoff(settings)
        items: dict[str, dict] = {}
        errors: list[str] = []

        for endpoint in ("hot", "latest"):
            try:
                topics = get_json(f"{_V1_BASE}/topics/{endpoint}.json")
                if isinstance(topics, list):
                    for topic in topics:
                        items.update(_normalize(topic, cutoff))
            except Exception as exc:
                logger.warning("v2ex_v1_fetch_failed", endpoint=endpoint, error=str(exc))
                errors.append(f"{endpoint}: {exc}")

        if not items and errors:
            raise RuntimeError("; ".join(errors))
        return list(items.values())


class V2exCollector(MultiBackendCollector):
    source_name = "v2ex"

    CREDENTIAL_SCHEMA: ClassVar[list[dict]] = [
        {
            "key": "api_token",
            "label": "V2EX API Token",
            "secret": True,
            "optional": True,
            "help": "Personal access token from v2ex.com/settings/tokens. Unlocks node-targeted discovery; without it the keyless v1 API (hot + latest) runs automatically.",
        },
        {
            "key": "nodes",
            "label": "Nodes (JSON array)",
            "secret": False,
            "optional": True,
            "help": 'e.g. ["startup","qna","python"]. Only applies with the v2 API token.',
        },
    ]

    def build_backends(self) -> list[SourceBackend]:
        return [V2exV2ApiBackend(), V2exV1ApiBackend()]

    @classmethod
    def test_connection(cls, db: sqlite3.Connection, settings) -> tuple[bool, str]:
        if _token(settings, db):
            return True, "V2EX will use the v2 API (node-targeted discovery)"
        return True, "No token — using keyless v1 API (hot + latest topics)"
