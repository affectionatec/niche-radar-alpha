"""Tests for MockLLMClient — deterministic fixture-based LLM mock."""
from __future__ import annotations

import pytest
from niche_radar.eval.mock_client import MockLLMClient


def test_mock_client_returns_fixture_response():
    fixtures = {
        "item_001": {"content": '{"is_valid_signal": true, "confidence": 0.9}'},
        "item_002": {"content": '{"is_valid_signal": false, "confidence": 0.1}'},
    }
    client = MockLLMClient(fixtures=fixtures, default={"content": '{"is_valid_signal": false}'})

    result = client.chat_completion(
        messages=[{"role": "user", "content": "test with item_001 in it"}],
        caller_id="item_001",
    )
    assert result == '{"is_valid_signal": true, "confidence": 0.9}'

    result = client.chat_completion(
        messages=[{"role": "user", "content": "test with item_002 in it"}],
        caller_id="item_002",
    )
    assert result == '{"is_valid_signal": false, "confidence": 0.1}'


def test_mock_client_falls_back_to_default_for_unknown_item():
    fixtures = {}
    client = MockLLMClient(fixtures=fixtures, default={"content": '{"is_valid_signal": false, "confidence": 0.0}'})

    result = client.chat_completion(
        messages=[{"role": "user", "content": "some unknown item"}],
        caller_id="unknown_item",
    )
    assert result == '{"is_valid_signal": false, "confidence": 0.0}'


def test_mock_client_records_calls():
    fixtures = {"item_001": {"content": "ok"}}
    client = MockLLMClient(fixtures=fixtures)

    client.chat_completion(messages=[{"role": "user", "content": "call 1"}], caller_id="item_001")
    client.chat_completion(messages=[{"role": "user", "content": "call 2"}], caller_id="item_002")

    assert len(client.calls) == 2
    assert client.calls[0]["caller_id"] == "item_001"
    assert client.calls[1]["caller_id"] == "item_002"


def test_mock_client_model_property():
    client = MockLLMClient(fixtures={})
    assert client.model == "mock-eval-model"


def test_mock_client_stream_raises_not_implemented():
    client = MockLLMClient(fixtures={})
    with pytest.raises(NotImplementedError):
        client.chat_completion_stream(messages=[{"role": "user", "content": "any"}])


def test_mock_client_unknown_caller_id_no_default_returns_empty():
    client = MockLLMClient(fixtures={})
    result = client.chat_completion(messages=[], caller_id="nonexistent")
    assert result == ""


def test_mock_client_records_kwargs():
    client = MockLLMClient(fixtures={"x": {"content": "ok"}})
    client.chat_completion(messages=[], caller_id="x", temperature=0.5, top_p=0.9)
    assert client.calls[0]["kwargs"] == {"temperature": 0.5, "top_p": 0.9}
