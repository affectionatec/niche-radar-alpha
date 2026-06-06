"""Mock LLM client that returns canned fixture responses for golden-set evaluation."""
from __future__ import annotations

from typing import Any


class MockLLMClient:
    """An LLMClient-compatible mock that returns pre-defined responses.

    Matches responses by caller_id. Falls back to a default response for
    unknown caller_ids so the eval runner can test "unexpected" inputs too.
    """

    def __init__(self, fixtures: dict[str, dict[str, Any]], default: dict[str, Any] | None = None) -> None:
        self._fixtures = fixtures
        self._default = default or {}
        self.calls: list[dict[str, Any]] = []

    def chat_completion(self, messages: list[dict[str, str]], caller_id: str = "", **kwargs: Any) -> str:
        self.calls.append({"messages": messages, "caller_id": caller_id, "kwargs": kwargs})
        fixture = self._fixtures.get(caller_id, self._default)
        content = fixture.get("content", "")
        return content

    # Stub the other LLMClient methods — they shouldn't be called during eval
    def chat_completion_stream(self, messages: list[dict[str, str]], **kwargs: Any) -> Any:
        raise NotImplementedError("streaming not used in eval")

    @property
    def model(self) -> str:
        return "mock-eval-model"
