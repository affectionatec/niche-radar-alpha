"""Per-agent LLM client resolution.

Each agent (a1..a8) can override provider/model/base_url/api_key/temperature via a single
JSON blob stored in app_settings under key `agent_llm_config`. Anything not specified
falls back to the global /settings config (same fields the existing _get_llm_client reads).

Default temperatures (refactor_prompt.md: temperature 0.2 for scoring agents,
0.4 for creative agents):
    a1=0.0  binary filter, want determinism
    a2=0.3  extraction; some flexibility
    a3=0.3  market research
    a4=0.2  scoring — calibrated
    a5=0.3  feasibility judgment
    a6=0.2  verdict — calibrated
    a7=0.4  PRD writing — slightly creative
    a8=0.4  brief writing — slightly creative

Per-agent provider/model overrides are optional; the cheap-tier hint is informational —
the user picks the actual cheap model in the override JSON.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from niche_radar.llm.base import LLMClient
from niche_radar.storage.repository import get_app_setting

DEFAULT_TEMPERATURES: dict[str, float] = {
    "a1": 0.0,
    "a2": 0.3,
    "a3": 0.3,
    "a4": 0.2,
    "a5": 0.3,
    "a6": 0.2,
    "a7": 0.4,
    "a8": 0.4,
}

# Informational tier hint — recorded so /settings UI (future) can suggest sensible defaults.
TIER_HINT: dict[str, str] = {
    "a1": "cheap",
    "a2": "cheap",
    "a3": "strong",
    "a4": "strong",
    "a5": "strong",
    "a6": "strong",
    "a7": "strong",
    "a8": "strong",
}

SETTINGS_KEY = "agent_llm_config"


def load_overrides(db: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    """Read the per-agent override JSON from app_settings. Returns {} on absence/parse error."""
    raw = get_app_setting(db, SETTINGS_KEY)
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {k: v for k, v in data.items() if isinstance(v, dict)}


def _resolve_config(agent_id: str, db: sqlite3.Connection, settings) -> dict[str, Any]:
    """Merge per-agent override with global settings + per-agent defaults."""
    overrides = load_overrides(db).get(agent_id, {})
    cfg = {
        "provider":    overrides.get("provider")    or get_app_setting(db, "llm_provider") or settings.llm_provider,
        "api_key":     overrides.get("api_key")     or get_app_setting(db, "llm_api_key")  or settings.llm_api_key,
        "model":       overrides.get("model")       or get_app_setting(db, "llm_model")    or settings.llm_model,
        "base_url":    overrides.get("base_url")    or get_app_setting(db, "llm_base_url") or settings.llm_base_url,
        "temperature": overrides.get("temperature", DEFAULT_TEMPERATURES.get(agent_id, 0.3)),
    }
    return cfg


def resolve_agent_client(
    agent_id: str,
    db: sqlite3.Connection,
    settings,
    overrides: dict[str, LLMClient] | None = None,
) -> tuple[LLMClient, float]:
    """Return a (client, temperature) pair for `agent_id`.

    `overrides` is a test-only shortcut: pass {"a1": FakeClient(), ...} to bypass DB/env.
    Temperature is returned alongside so the orchestrator can pass it into
    `client.complete_structured(system, user, temperature=...)`.
    """
    if overrides and agent_id in overrides:
        return overrides[agent_id], DEFAULT_TEMPERATURES.get(agent_id, 0.3)

    cfg = _resolve_config(agent_id, db, settings)
    if not cfg["api_key"]:
        raise ValueError(
            f"LLM API key not configured for agent {agent_id}. "
            "Set it in Settings or LLM_API_KEY env var, or override in agent_llm_config."
        )

    provider = cfg["provider"]
    if provider == "anthropic":
        from niche_radar.llm.anthropic_client import AnthropicClient
        client: LLMClient = AnthropicClient(api_key=cfg["api_key"], model=cfg["model"])
    else:
        from niche_radar.llm.openai_compat import OpenAICompatClient
        client = OpenAICompatClient(
            api_key=cfg["api_key"], model=cfg["model"], base_url=cfg["base_url"] or None
        )
    return client, float(cfg["temperature"])
