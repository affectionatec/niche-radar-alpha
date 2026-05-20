"""Anthropic SDK wrapper with JSON parsing and retry logic."""

from __future__ import annotations

import json

import anthropic
import structlog

logger = structlog.get_logger()


class LLMCaller:
    """Calls the Claude API and returns parsed JSON dicts."""

    def __init__(self, settings) -> None:
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.model = settings.pipeline_model
        self.default_max_tokens = settings.pipeline_max_tokens

    def call(
        self,
        system: str,
        user: str,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        agent_id: int | None = None,
    ) -> dict:
        """Call LLM, parse JSON. Retries up to 2 times on parse failure.

        Returns the parsed dict on success, or {"_error": True, "_raw": ...} on
        exhausted retries so the pipeline can continue with partial context.
        """
        max_tokens = max_tokens or self.default_max_tokens

        for attempt in range(3):
            try:
                message = self.client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=system,
                    messages=[{"role": "user", "content": user}],
                )
                raw = message.content[0].text.strip()
                parsed = _parse_json(raw)
                logger.debug(
                    "agent_call_ok",
                    agent_id=agent_id,
                    attempt=attempt,
                    tokens_used=message.usage.output_tokens,
                )
                return parsed

            except json.JSONDecodeError as exc:
                logger.warning(
                    "json_parse_failure",
                    agent_id=agent_id,
                    attempt=attempt,
                    error=str(exc),
                    raw_preview=raw[:200] if "raw" in dir() else "",
                )
                if attempt == 2:
                    logger.error(
                        "agent_failed_all_retries",
                        agent_id=agent_id,
                        raw_preview=raw[:300] if "raw" in dir() else "",
                    )
                    return {"_error": True, "_raw": raw if "raw" in dir() else ""}

            except anthropic.APIError as exc:
                logger.error(
                    "anthropic_api_error",
                    agent_id=agent_id,
                    attempt=attempt,
                    error=str(exc),
                )
                if attempt == 2:
                    return {"_error": True, "_raw": str(exc)}

        return {"_error": True}


def _parse_json(raw: str) -> dict:
    """Extract JSON from a response that may contain markdown code fences."""
    text = raw.strip()

    # Strip ```json ... ``` or ``` ... ``` wrappers
    if text.startswith("```"):
        lines = text.split("\n")
        # Drop first line (```json or ```) and last line (```)
        inner_lines = lines[1:]
        if inner_lines and inner_lines[-1].strip() == "```":
            inner_lines = inner_lines[:-1]
        text = "\n".join(inner_lines).strip()

    return json.loads(text)
