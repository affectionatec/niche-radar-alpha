"""Tests for MockLLMClient — deterministic LLM mock implementing the real protocol."""
from __future__ import annotations

from niche_radar.eval.mock_client import MockLLMClient
from niche_radar.llm.base import LLMClient


def test_mock_client_satisfies_llm_client_protocol():
    client = MockLLMClient()
    assert isinstance(client, LLMClient)


def test_mock_client_returns_response_for_active_agent():
    client = MockLLMClient(
        responses={
            "a1": {"is_valid_signal": True, "confidence": 0.9},
            "a2": {"who": "designer", "what": "manual copying"},
        }
    )

    client.set_agent("a1")
    assert client.complete_structured("sys", "user") == {
        "is_valid_signal": True,
        "confidence": 0.9,
    }

    client.set_agent("a2")
    assert client.complete_structured("sys", "user") == {
        "who": "designer",
        "what": "manual copying",
    }


def test_mock_client_falls_back_to_default_for_unknown_agent():
    client = MockLLMClient(responses={}, default={"is_valid_signal": False})
    client.set_agent("a7")
    assert client.complete_structured("sys", "user") == {"is_valid_signal": False}


def test_mock_client_default_default_is_empty_dict():
    client = MockLLMClient()
    client.set_agent("a1")
    assert client.complete_structured("sys", "user") == {}


def test_mock_client_returns_copies_not_shared_state():
    canned = {"is_valid_signal": True}
    client = MockLLMClient(responses={"a1": canned})
    client.set_agent("a1")
    first = client.complete_structured("sys", "user")
    first["mutated"] = True
    assert client.complete_structured("sys", "user") == {"is_valid_signal": True}


def test_mock_client_records_calls_with_agent_and_prompts():
    client = MockLLMClient(responses={"a1": {"is_valid_signal": True}})

    client.set_agent("a1")
    client.complete_structured("system prompt", "user prompt", temperature=0.3)
    client.set_agent("a2")
    client.complete_structured("system 2", "user 2")

    assert len(client.calls) == 2
    assert client.calls[0]["agent_id"] == "a1"
    assert client.calls[0]["system"] == "system prompt"
    assert client.calls[0]["user"] == "user prompt"
    assert client.calls[0]["temperature"] == 0.3
    assert client.calls[1]["agent_id"] == "a2"


def test_mock_client_complete_json_uses_active_agent():
    client = MockLLMClient(responses={"a3": {"market_leader": "X"}})
    client.set_agent("a3")
    assert client.complete_json("prompt") == {"market_leader": "X"}


def test_mock_client_complete_returns_empty_string():
    client = MockLLMClient()
    assert client.complete("prompt") == ""


def test_mock_client_model_property():
    client = MockLLMClient()
    assert client.model == "mock-eval-model"
