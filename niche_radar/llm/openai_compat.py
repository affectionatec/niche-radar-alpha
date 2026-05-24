"""OpenAI-compatible LLM client. Works with OpenAI, DeepSeek, Groq, Ollama, etc."""

from __future__ import annotations

import json

from niche_radar.llm.usage import record_usage


class OpenAICompatClient:
    def __init__(self, api_key: str, model: str, base_url: str | None = None) -> None:
        from openai import OpenAI
        self._client = OpenAI(api_key=api_key, base_url=base_url or None)
        self._model = model
        self._current_agent: str = "unknown"

    def set_agent(self, agent: str) -> None:
        """Set the current agent name for usage tracking."""
        self._current_agent = agent

    def _track(self, response: object) -> None:
        usage = getattr(response, "usage", None)
        if usage:
            record_usage(self._current_agent, self._model, usage)

    def complete(self, prompt: str) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2048,
        )
        self._track(response)
        return response.choices[0].message.content or ""

    def complete_json(self, prompt: str) -> dict:
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                max_tokens=4096,
            )
            self._track(response)
            return json.loads(response.choices[0].message.content or "{}")
        except Exception:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=4096,
            )
            self._track(response)
            return _extract_json(response.choices[0].message.content or "")

    def complete_structured(
        self,
        system: str,
        user: str,
        temperature: float | None = None,
    ) -> dict:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        kwargs: dict = {"model": self._model, "messages": messages, "max_tokens": 4096}
        if temperature is not None:
            kwargs["temperature"] = temperature
        try:
            response = self._client.chat.completions.create(
                **kwargs, response_format={"type": "json_object"}
            )
            self._track(response)
            return json.loads(response.choices[0].message.content or "{}")
        except Exception:
            response = self._client.chat.completions.create(**kwargs)
            self._track(response)
            return _extract_json(response.choices[0].message.content or "")


def _extract_json(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass
    return {}
