"""LLMClient protocol — implemented by openai_compat and anthropic_client."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMClient(Protocol):
    def complete(self, prompt: str) -> str:
        """Send a plain text prompt, return the response text."""
        ...

    def complete_json(self, prompt: str) -> dict:
        """Send a prompt expecting a JSON object response."""
        ...

    def complete_structured(
        self,
        system: str,
        user: str,
        temperature: float | None = None,
    ) -> dict:
        """Send a system + user prompt pair expecting a JSON object response.

        Used by the 8-agent pipeline to keep role separation and per-agent
        temperature control. Implementations may fall back to a single combined
        prompt internally if their underlying API doesn't support separate roles.
        """
        ...
