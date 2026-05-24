"""Anthropic Claude LLM client."""

from __future__ import annotations

import json

from niche_radar.llm.usage import record_usage


class AnthropicClient:
    def __init__(self, api_key: str, model: str) -> None:
        import anthropic
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model
        self._current_agent: str = "unknown"

    def set_agent(self, agent: str) -> None:
        """Set the current agent name for usage tracking."""
        self._current_agent = agent

    def _track(self, message: object) -> None:
        usage = getattr(message, "usage", None)
        if usage:
            prompt = getattr(usage, "input_tokens", 0) or 0
            completion = getattr(usage, "output_tokens", 0) or 0

            class _Compat:
                prompt_tokens = prompt
                completion_tokens = completion
                total_tokens = prompt + completion

            record_usage(self._current_agent, self._model, _Compat())

    def complete(self, prompt: str) -> str:
        message = self._client.messages.create(
            model=self._model,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        self._track(message)
        return message.content[0].text  # type: ignore[union-attr]

    def complete_json(self, prompt: str) -> dict:
        full_prompt = prompt + "\n\nRespond with valid JSON only. No markdown, no explanation."
        text = self.complete(full_prompt)
        return _extract_json(text)

    def complete_structured(
        self,
        system: str,
        user: str,
        temperature: float | None = None,
    ) -> dict:
        kwargs: dict = {
            "model": self._model,
            "max_tokens": 4096,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        if temperature is not None:
            kwargs["temperature"] = temperature
        message = self._client.messages.create(**kwargs)
        self._track(message)
        text = message.content[0].text  # type: ignore[union-attr]
        return _extract_json(text)


def _extract_json(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass
    return {}
