"""Mock LLM client that returns canned fixture responses for golden-set evaluation.

Implements the real ``niche_radar.llm.base.LLMClient`` protocol so it can be
plugged straight into ``orchestrator.run_single`` / ``run_cluster`` — the eval
exercises the actual agent code (prompt build, JSON validation, short-circuit
logic) with only the network call replaced.
"""
from __future__ import annotations

from typing import Any


class MockLLMClient:
    """An LLMClient-compatible mock that returns pre-defined structured responses.

    Responses are keyed by agent_id ("a1" … "a8"). The orchestrator announces
    the active agent via ``set_agent`` before each call; ``complete_structured``
    then returns that agent's canned dict. Unknown agents fall back to
    ``default`` (an empty dict fails A-model validation, which is useful for
    testing the orchestrator's failure path).
    """

    def __init__(
        self,
        responses: dict[str, dict[str, Any]] | None = None,
        default: dict[str, Any] | None = None,
    ) -> None:
        self._responses = responses or {}
        self._default = default if default is not None else {}
        self._current_agent = ""
        self.calls: list[dict[str, Any]] = []

    # ── LLMClient protocol ──────────────────────────────────────────────

    def complete(self, prompt: str) -> str:
        self.calls.append({"agent_id": self._current_agent, "prompt": prompt})
        return ""

    def complete_json(self, prompt: str) -> dict:
        self.calls.append({"agent_id": self._current_agent, "prompt": prompt})
        return dict(self._responses.get(self._current_agent, self._default))

    def complete_structured(
        self,
        system: str,
        user: str,
        temperature: float | None = None,
    ) -> dict:
        self.calls.append(
            {
                "agent_id": self._current_agent,
                "system": system,
                "user": user,
                "temperature": temperature,
            }
        )
        return dict(self._responses.get(self._current_agent, self._default))

    # ── orchestrator hooks ──────────────────────────────────────────────

    def set_agent(self, agent_id: str) -> None:
        """Called by orchestrator._call_agent before each agent invocation."""
        self._current_agent = agent_id

    @property
    def model(self) -> str:
        return "mock-eval-model"
