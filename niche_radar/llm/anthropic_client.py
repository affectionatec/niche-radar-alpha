"""Anthropic Claude LLM client."""

from __future__ import annotations

import json


class AnthropicClient:
    def __init__(self, api_key: str, model: str) -> None:
        import anthropic
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def complete(self, prompt: str) -> str:
        message = self._client.messages.create(
            model=self._model,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text  # type: ignore[union-attr]

    def complete_json(self, prompt: str) -> dict:
        full_prompt = prompt + "\n\nRespond with valid JSON only. No markdown, no explanation."
        text = self.complete(full_prompt)
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
