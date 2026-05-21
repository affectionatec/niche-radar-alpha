"""Test fixtures for agent-pipeline tests.

FakeLLMClient lets us drive the orchestrator without hitting any real API. It accepts a
dict of canned responses keyed by either agent_id or a queue of dicts to return in order.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import pytest


class FakeLLMClient:
    """Records every call and returns canned dicts.

    `responses` may be:
    - A dict keyed by agent_id (matched via a substring of the system prompt) — returns
      the same dict every time that agent is called.
    - A list of dicts — returns them in FIFO order regardless of agent.
    - A callable: invoked with (system, user, temperature) and must return a dict.

    Special: a dict value of `{"__raise__": "ValueError: ..."}` raises instead of returning.
    A dict value of `{"__noise__": True}` returns an empty dict (simulates malformed JSON).
    """

    def __init__(self, responses: Any) -> None:
        self.responses = responses
        self.calls: list[dict[str, Any]] = []
        self._queue_pos = 0
        # Per-agent retry counters to support "fail twice then succeed" patterns.
        self._agent_call_counts: dict[str, int] = defaultdict(int)

    def _agent_id_from_system(self, system: str) -> str:
        """Cheap heuristic: detect which agent from the system prompt text."""
        s = system.lower()
        if "signal filter" in s:
            return "a1"
        if "ux researcher" in s:
            return "a2"
        if "competitive intelligence" in s:
            return "a3"
        if "venture analyst" in s:
            return "a4"
        if "indie developer" in s:
            return "a5"
        if "decisive" in s and "entrepreneur" in s:
            return "a6"
        if "product manager generating a concise prd" in s:
            return "a7"
        if "opportunity brief" in s:
            return "a8"
        return "unknown"

    def complete_structured(
        self,
        system: str,
        user: str,
        temperature: float | None = None,
    ) -> dict:
        agent_id = self._agent_id_from_system(system)
        self._agent_call_counts[agent_id] += 1
        attempt = self._agent_call_counts[agent_id]

        self.calls.append({
            "agent_id": agent_id,
            "system": system,
            "user": user,
            "temperature": temperature,
            "attempt": attempt,
        })

        # Callable responses table: defer entirely
        if callable(self.responses):
            out = self.responses(agent_id, user, attempt)
        elif isinstance(self.responses, list):
            if self._queue_pos >= len(self.responses):
                out = {}
            else:
                out = self.responses[self._queue_pos]
                self._queue_pos += 1
        elif isinstance(self.responses, dict):
            out = self.responses.get(agent_id, {})
            # Support "fail N times then succeed" by passing a list per agent
            if isinstance(out, list):
                idx = min(attempt - 1, len(out) - 1)
                out = out[idx]
        else:
            out = {}

        if isinstance(out, dict) and out.get("__raise__"):
            raise RuntimeError(out["__raise__"])
        if isinstance(out, dict) and out.get("__noise__"):
            return {}
        return out or {}

    # Match LLMClient protocol so isinstance checks pass
    def complete(self, prompt: str) -> str:
        return ""

    def complete_json(self, prompt: str) -> dict:
        return {}

    def calls_for(self, agent_id: str) -> list[dict]:
        return [c for c in self.calls if c["agent_id"] == agent_id]


@pytest.fixture
def fake_llm():
    """Factory for FakeLLMClient — pass in the canned responses dict/list."""
    return FakeLLMClient


@pytest.fixture
def canned_a1_pass():
    return {
        "is_valid_signal": True,
        "confidence": 0.85,
        "pain_summary": "Manual cost reporting is tedious",
        "rejection_reason": None,
        "signal_type": "pain_point",
    }


@pytest.fixture
def canned_a1_reject():
    return {
        "is_valid_signal": False,
        "confidence": 0.92,
        "pain_summary": None,
        "rejection_reason": "vague complaint with no actionable core",
        "signal_type": "noise",
    }


@pytest.fixture
def canned_a2():
    return {
        "who": "sysadmins at small companies",
        "what": "manually copying AWS cost data into spreadsheets monthly",
        "when": "end of each month for manager reports",
        "current_workaround": "manual copy-paste from AWS Cost Explorer",
        "why_current_sucks": "time-consuming and error-prone",
        "desired_outcome": "automated monthly cost reports",
        "emotional_intensity": 7,
        "frequency": "monthly",
        "affected_scale": "team",
        "willingness_to_pay_signal": True,
        "pay_signal_evidence": "CloudHealth is $500/month which is insane",
        "keywords": ["aws", "cost", "reporting", "spreadsheet", "monthly"],
    }


@pytest.fixture
def canned_a3():
    return {
        "existing_solutions": [
            {"name": "CloudHealth", "type": "saas", "price_range": "enterprise",
             "main_weakness": "too expensive for small teams", "market_position": "leader"},
        ],
        "market_leader": "CloudHealth",
        "market_maturity": "growing",
        "saturation_score": 4,
        "key_gap": "no affordable simple AWS cost reporting tool for 20-person teams",
        "price_ceiling": "$50-100/mo for SMBs",
        "buyer_type": "smb",
        "estimated_tam": "$10-100M",
        "competition_notes": "Enterprise tools dominate; the SMB gap is real.",
    }


@pytest.fixture
def canned_a4():
    return {
        "scores": {
            "problem_clarity":       {"score": 8, "rationale": "very specific"},
            "market_size":           {"score": 6, "rationale": "every AWS team"},
            "willingness_to_pay":    {"score": 7, "rationale": "complains about $500/mo"},
            "competition_gap":       {"score": 7, "rationale": "no cheap option"},
            "technical_feasibility": {"score": 8, "rationale": "just an API+template"},
            "distribution_clarity":  {"score": 6, "rationale": "r/sysadmin, HN"},
            "trend_momentum":        {"score": 5, "rationale": "cloud cost is hot"},
        },
        "total_score": 47,
        "top_3_strengths": ["specific pain", "willing-to-pay buyers", "easy to build"],
        "top_3_risks": ["AWS API churn", "small ACV", "enterprise migration"],
        "comparable_products": ["Vantage", "Infracost"],
    }


@pytest.fixture
def canned_a5():
    return {
        "mvp_scope": "Connect AWS account, generate monthly PDF cost report, email it.",
        "core_features": ["AWS Cost Explorer integration", "PDF report generator", "scheduled email"],
        "explicitly_cut_from_mvp": ["multi-cloud", "real-time alerts", "custom dashboards"],
        "tech_stack": {
            "backend": "FastAPI + Python",
            "frontend": "Next.js",
            "ai_components": "none",
            "key_integrations": ["AWS Cost Explorer API", "SendGrid"],
        },
        "estimated_weeks_to_mvp": 3,
        "biggest_technical_risk": "AWS auth + IAM permissions setup",
        "distribution_strategy": "r/sysadmin, r/aws, HN Show",
        "first_channel": "Reddit",
        "revenue_model": "subscription",
        "price_hypothesis": "$29/mo team",
        "feasibility_score": 8,
        "solo_buildable": True,
    }


@pytest.fixture
def canned_a6_go():
    return {
        "verdict": "GO",
        "confidence": 0.78,
        "one_line_rationale": "specific buyers + clear gap + 3-week build",
        "full_rationale": "Real pain, willing payers, no good cheap option, easy MVP.",
        "killer_risk": "AWS-only TAM may be smaller than estimated",
        "pivot_suggestion": None,
        "conditions_to_reconsider": "if a free OSS tool launches",
        "recommended_next_step": "post a poll on r/sysadmin to validate price point",
    }


@pytest.fixture
def canned_a6_nogo():
    return {
        "verdict": "NO-GO",
        "confidence": 0.85,
        "one_line_rationale": "ACV too low for solo founder distribution effort",
        "full_rationale": "Even at $29/mo, breaking even on solo time investment is hard.",
        "killer_risk": "Customer acquisition cost > LTV",
        "pivot_suggestion": None,
        "conditions_to_reconsider": "if you find a B2B channel partner",
        "recommended_next_step": "skip — find a bigger pain",
    }


@pytest.fixture
def canned_a7():
    return {
        "product_name": "CostScribe",
        "one_liner": "Monthly AWS cost PDF reports, emailed to your inbox.",
        "target_user_persona": "sysadmin at a 10-50 person company using AWS",
        "core_problem_statement": "we help sysadmins generate monthly cost reports so they can stop copy-pasting",
        "mvp_features": [
            {"feature": "AWS connect", "user_story": "as a user, I want to connect AWS so reports auto-generate", "acceptance_criteria": "OAuth works", "priority": "P0"}
        ],
        "explicitly_out_of_scope": ["multi-cloud", "real-time alerts"],
        "success_metrics": ["10 paying users in 30 days", "MRR $300", "<5% churn"],
        "monetization": {
            "model": "subscription",
            "free_tier": None,
            "paid_tier_price": "$29/month",
            "paid_tier_value": "unlimited monthly reports",
        },
        "launch_plan": {
            "day_1_to_7": "build AWS Cost Explorer integration",
            "day_8_to_14": "post on r/sysadmin",
            "day_15_to_30": "convert first 10 to paid",
        },
    }


@pytest.fixture
def canned_a8():
    return {
        "title": "AWS Cost Report Tool",
        "verdict_badge": "🟢 GO",
        "tldr": "Easy AWS bill summary tool for small companies. They'll pay $29/mo.",
        "the_pain": "Sysadmins waste hours copying AWS costs into spreadsheets monthly.",
        "the_gap": "No affordable AWS reporting tool exists for sub-50 person teams.",
        "the_user": "Sysadmins at 10-50 person companies running on AWS.",
        "the_money": "$29/mo subscription, target $300 MRR in 30 days.",
        "scores": {
            "pain_intensity": 7,
            "opportunity_score": "47/70",
            "feasibility": "8/10",
            "confidence": 0.78,
        },
        "top_reason_to_do_it": "Easy to build, clear buyer, real money on the table.",
        "top_reason_not_to": "Total addressable market may be capped.",
        "if_i_were_to_start_today": "post a price-validation poll on r/sysadmin",
        "similar_successes": ["Vantage", "Infracost"],
        "source": "reddit",
        "analyzed_at": "2026-05-20T10:00:00Z",
    }
