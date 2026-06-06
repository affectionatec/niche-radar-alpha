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


def fuzzy_match(
    name: str,
    existing_canonical: str,
    existing_aliases: list[str] | None = None,
) -> bool:
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
