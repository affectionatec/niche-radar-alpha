"""OpenAI-compatible LLM client. Works with OpenAI, DeepSeek, Groq, Ollama, etc."""

from __future__ import annotations

import json


class OpenAICompatClient:
    def __init__(self, api_key: str, model: str, base_url: str | None = None) -> None:
        from openai import OpenAI
        self._client = OpenAI(api_key=api_key, base_url=base_url or None)
        self._model = model

    def complete(self, prompt: str) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2048,
        )
        return response.choices[0].message.content or ""

    def complete_json(self, prompt: str) -> dict:
        # Try with json_object response format; fall back to text extraction
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                max_tokens=4096,
            )
            return json.loads(response.choices[0].message.content or "{}")
        except Exception:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=4096,
            )
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
            return json.loads(response.choices[0].message.content or "{}")
        except Exception:
            response = self._client.chat.completions.create(**kwargs)
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
