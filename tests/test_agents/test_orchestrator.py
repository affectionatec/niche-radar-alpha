"""Tests for orchestrator.run_single and orchestrator.run_cluster."""

from __future__ import annotations

import pytest

from niche_radar.agents.models import A2Output
from niche_radar.agents.orchestrator import (
    BudgetExceeded,
    run_cluster,
    run_single,
)

_RAW = {
    "text": "I copy AWS Cost Explorer into a spreadsheet every month.",
    "source": "reddit",
    "url": "https://reddit.com/r/sysadmin/x",
    "scraped_at": "2026-05-20T10:00:00Z",
}


def _resolver(client, temp=0.3):
    """Make a clients_resolver that returns the same FakeLLMClient for every agent."""
    return lambda agent_id: (client, temp)


# ---------- run_single ----------


def test_a1_reject_short_circuits(fake_llm, canned_a1_reject):
    client = fake_llm({"a1": canned_a1_reject})
    result = run_single(_RAW, _resolver(client))

    assert result.a1 is not None
    assert result.a1.is_valid_signal is False
    assert result.a2 is None
    assert result.short_circuited_at == "a1"
    # Only one LLM call was made (A1); A2 must not be invoked.
    assert len(client.calls) == 1


def test_a1_pass_then_a2_runs(fake_llm, canned_a1_pass, canned_a2):
    client = fake_llm({"a1": canned_a1_pass, "a2": canned_a2})
    result = run_single(_RAW, _resolver(client))

    assert result.a1.is_valid_signal is True
    assert result.a2 is not None
    assert result.a2.what.startswith("manually copying")
    assert result.short_circuited_at is None
    assert client.calls[0]["agent_id"] == "a1"
    assert client.calls[1]["agent_id"] == "a2"


def test_a1_malformed_response_retries_twice_then_fails(fake_llm, canned_a1_pass):
    # First two attempts return empty dict (malformed); third returns the canned pass.
    responses = {"a1": [{"__noise__": True}, {"__noise__": True}, canned_a1_pass]}
    client = fake_llm(responses)
    result = run_single(_RAW, _resolver(client))

    # Third attempt succeeded — A1 lives.
    assert result.a1 is not None
    assert result.a1.is_valid_signal is True
    # 3 attempts for A1 + 0 (A2 not called because no a2 canned).
    a1_calls = client.calls_for("a1")
    assert len(a1_calls) == 3


def test_a1_persistent_failure_short_circuits_with_short_circuit_marker(fake_llm):
    # All 3 attempts return garbage → terminal failure.
    responses = {"a1": {"__noise__": True}}
    client = fake_llm(responses)
    result = run_single(_RAW, _resolver(client))

    assert result.a1 is None
    assert "a1" in result.failed_agents
    assert result.short_circuited_at == "a1"
    # 1 + 2 retries
    assert len(client.calls_for("a1")) == 3


def test_resolver_called_with_each_agent_id(fake_llm, canned_a1_pass, canned_a2):
    client = fake_llm({"a1": canned_a1_pass, "a2": canned_a2})
    called_with: list[str] = []

    def resolver(agent_id):
        called_with.append(agent_id)
        return client, 0.5

    run_single(_RAW, resolver)
    assert called_with == ["a1", "a2"]


def test_temperature_passed_through(fake_llm, canned_a1_pass):
    client = fake_llm({"a1": canned_a1_pass})

    def resolver(agent_id):
        return client, 0.123

    run_single(_RAW, resolver)
    assert client.calls[0]["temperature"] == 0.123


def test_budget_exceeded_propagates(fake_llm, canned_a1_pass):
    client = fake_llm({"a1": canned_a1_pass})

    def budget_check(agent_id):
        if agent_id == "a1":
            raise BudgetExceeded("ran out before A1")

    with pytest.raises(BudgetExceeded):
        run_single(_RAW, _resolver(client), budget_check=budget_check)


def test_log_fn_invoked_for_pass_and_reject(fake_llm, canned_a1_pass, canned_a2, canned_a1_reject):
    log: list[str] = []
    client_pass = fake_llm({"a1": canned_a1_pass, "a2": canned_a2})
    run_single(_RAW, _resolver(client_pass), log_fn=log.append)
    assert any("A1=PASS" in line for line in log)
    assert any("A2=DONE" in line for line in log)

    log.clear()
    client_reject = fake_llm({"a1": canned_a1_reject})
    run_single(_RAW, _resolver(client_reject), log_fn=log.append)
    assert any("A1=REJECT" in line for line in log)


# ---------- run_cluster ----------


def _cluster_ctx(a2_dict):
    """Build a minimal cluster_context with an A2 aggregate."""
    return {
        "raw_signal": _RAW,
        "a2": A2Output(**a2_dict),
    }


def test_cluster_go_runs_all_eight_through_a8(
    fake_llm, canned_a2, canned_a3, canned_a4, canned_a5, canned_a6_go, canned_a7, canned_a8,
):
    client = fake_llm({
        "a3": canned_a3, "a4": canned_a4, "a5": canned_a5,
        "a6": canned_a6_go, "a7": canned_a7, "a8": canned_a8,
    })
    result = run_cluster(_cluster_ctx(canned_a2), _resolver(client))

    assert result.a3 is not None and result.a3.market_leader == "CloudHealth"
    assert result.a4 is not None and result.a4.total_score == 47
    assert result.a5 is not None and result.a5.feasibility_score == 8
    assert result.a6 is not None and result.a6.verdict == "GO"
    assert result.a7 is not None and result.a7.product_name == "CostScribe"
    assert result.a8 is not None and result.a8.title == "AWS Cost Report Tool"
    assert result.failed_agents == []


def test_cluster_no_go_skips_a7_runs_a8(
    fake_llm, canned_a2, canned_a3, canned_a4, canned_a5, canned_a6_nogo, canned_a8,
):
    client = fake_llm({
        "a3": canned_a3, "a4": canned_a4, "a5": canned_a5,
        "a6": canned_a6_nogo, "a8": canned_a8,
    })
    result = run_cluster(_cluster_ctx(canned_a2), _resolver(client))

    assert result.a6.verdict == "NO-GO"
    assert result.a7 is None  # skipped per spec
    assert result.a8 is not None  # always runs
    # A7 must NOT have been called against the LLM
    assert client.calls_for("a7") == []
    # A8 was called exactly once
    assert len(client.calls_for("a8")) == 1


def test_cluster_pivot_skips_a7_still_runs_a8(
    fake_llm, canned_a2, canned_a3, canned_a4, canned_a5, canned_a8,
):
    pivot_a6 = {
        "verdict": "PIVOT", "confidence": 0.7,
        "one_line_rationale": "right pain, wrong audience",
        "full_rationale": "x", "killer_risk": "x",
        "pivot_suggestion": "target ops instead of devs",
        "conditions_to_reconsider": "x", "recommended_next_step": "x",
    }
    client = fake_llm({
        "a3": canned_a3, "a4": canned_a4, "a5": canned_a5,
        "a6": pivot_a6, "a8": canned_a8,
    })
    result = run_cluster(_cluster_ctx(canned_a2), _resolver(client))

    assert result.a6.verdict == "PIVOT"
    assert result.a7 is None
    assert result.a8 is not None
    assert client.calls_for("a7") == []


def test_cluster_a4_mid_chain_failure_continues_with_nulls(
    fake_llm, canned_a2, canned_a3, canned_a5, canned_a6_go, canned_a7, canned_a8,
):
    # A4 always fails — downstream agents must still run with defensive substitution.
    client = fake_llm({
        "a3": canned_a3,
        "a4": {"__noise__": True},  # 3 attempts all empty
        "a5": canned_a5, "a6": canned_a6_go, "a7": canned_a7, "a8": canned_a8,
    })
    result = run_cluster(_cluster_ctx(canned_a2), _resolver(client))

    assert result.a4 is None
    assert "a4" in result.failed_agents
    # A5, A6, A7 (GO), A8 must all have run despite A4 missing.
    assert result.a5 is not None
    assert result.a6 is not None
    assert result.a7 is not None
    assert result.a8 is not None
    # And the A5 user prompt must have substituted "unknown" for the missing A4 dim scores.
    a5_call = client.calls_for("a5")[0]
    assert "unknown" in a5_call["user"]


def test_cluster_a6_failure_skips_a7_still_runs_a8(
    fake_llm, canned_a2, canned_a3, canned_a4, canned_a5, canned_a8,
):
    # A6 fails terminally. We treat it as "not GO" → A7 skipped, A8 still runs.
    client = fake_llm({
        "a3": canned_a3, "a4": canned_a4, "a5": canned_a5,
        "a6": {"__noise__": True},
        "a8": canned_a8,
    })
    result = run_cluster(_cluster_ctx(canned_a2), _resolver(client))

    assert result.a6 is None
    assert "a6" in result.failed_agents
    assert result.a7 is None
    assert result.a8 is not None


def test_to_storage_dict_serializes_pydantic_models(
    fake_llm, canned_a2, canned_a3, canned_a4, canned_a5, canned_a6_go, canned_a7, canned_a8,
):
    client = fake_llm({
        "a3": canned_a3, "a4": canned_a4, "a5": canned_a5,
        "a6": canned_a6_go, "a7": canned_a7, "a8": canned_a8,
    })
    result = run_cluster(_cluster_ctx(canned_a2), _resolver(client))
    storage = result.to_storage_dict()
    assert storage["a4"]["total_score"] == 47
    assert storage["a7"]["product_name"] == "CostScribe"
    assert storage["failed_agents"] == []
    assert storage["short_circuited_at"] is None
