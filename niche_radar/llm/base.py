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
