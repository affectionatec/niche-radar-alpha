"""Pydantic models for each agent's output schema.

All fields default to None so that partial pipeline failures (e.g., A4 errors mid-chain)
yield well-formed PipelineResult objects with the missing pieces left as None — downstream
agents read defensively via .get() chains and substitute "unknown" where needed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


# Tolerant base config: extra LLM keys don't raise, missing fields stay None.
class _AgentModel(BaseModel):
    model_config = ConfigDict(extra="allow", validate_assignment=False)


class A1Output(_AgentModel):
    """Signal Filter — skeptical editor judging whether the text contains a real pain point."""
    is_valid_signal: bool | None = None
    confidence: float | None = None
    pain_summary: str | None = None
    rejection_reason: str | None = None
    signal_type: Literal["pain_point", "feature_request", "competitor_complaint", "noise"] | None = None


class A2Output(_AgentModel):
    """Pain Extractor — senior UX researcher structuring the raw pain."""
    who: str | None = None
    what: str | None = None
    when: str | None = None
    current_workaround: str | None = None
    why_current_sucks: str | None = None
    desired_outcome: str | None = None
    emotional_intensity: int | None = None
    frequency: Literal["daily", "weekly", "monthly", "rarely"] | None = None
    affected_scale: Literal["individual", "team", "company", "industry"] | None = None
    willingness_to_pay_signal: bool | None = None
    pay_signal_evidence: str | None = None
    keywords: list[str] = []


class A3Solution(_AgentModel):
    name: str | None = None
    type: Literal["saas", "open_source", "manual_process", "enterprise"] | None = None
    price_range: str | None = None
    main_weakness: str | None = None
    market_position: Literal["leader", "challenger", "niche"] | None = None


class A3Output(_AgentModel):
    """Market Researcher — competitive intelligence."""
    existing_solutions: list[A3Solution] = []
    market_leader: str | None = None
    market_maturity: Literal["emerging", "growing", "mature", "declining"] | None = None
    saturation_score: int | None = None
    key_gap: str | None = None
    price_ceiling: str | None = None
    buyer_type: Literal["consumer", "smb", "enterprise", "developer"] | None = None
    estimated_tam: str | None = None
    competition_notes: str | None = None


class A4Score(_AgentModel):
    score: int | None = None
    rationale: str | None = None


class A4Scores(_AgentModel):
    problem_clarity: A4Score | None = None
    market_size: A4Score | None = None
    willingness_to_pay: A4Score | None = None
    competition_gap: A4Score | None = None
    technical_feasibility: A4Score | None = None
    distribution_clarity: A4Score | None = None
    trend_momentum: A4Score | None = None


class A4Output(_AgentModel):
    """Opportunity Scorer — VC analyst, 7 dimensions of 1-10 each."""
    scores: A4Scores | None = None
    total_score: int | None = None        # 0-70 (raw sum)
    top_3_strengths: list[str] = []
    top_3_risks: list[str] = []
    comparable_products: list[str] = []


class A5TechStack(_AgentModel):
    backend: str | None = None
    frontend: str | None = None
    ai_components: str | None = None
    key_integrations: list[str] = []


class A5Output(_AgentModel):
    """Feasibility Analyst — experienced solo indie developer."""
    mvp_scope: str | None = None
    core_features: list[str] = []
    explicitly_cut_from_mvp: list[str] = []
    tech_stack: A5TechStack | None = None
    estimated_weeks_to_mvp: int | None = None
    biggest_technical_risk: str | None = None
    distribution_strategy: str | None = None
    first_channel: str | None = None
    revenue_model: str | None = None
    price_hypothesis: str | None = None
    feasibility_score: int | None = None
    solo_buildable: bool | None = None


class A6Output(_AgentModel):
    """Go/No-Go Judge — decisive entrepreneur."""
    verdict: Literal["GO", "NO-GO", "PIVOT"] | None = None
    confidence: float | None = None
    one_line_rationale: str | None = None
    full_rationale: str | None = None
    killer_risk: str | None = None
    pivot_suggestion: str | None = None
    conditions_to_reconsider: str | None = None
    recommended_next_step: str | None = None


class A7Feature(_AgentModel):
    feature: str | None = None
    user_story: str | None = None
    acceptance_criteria: str | None = None
    priority: Literal["P0", "P1"] | None = None


class A7Monetization(_AgentModel):
    model: str | None = None
    free_tier: str | None = None
    paid_tier_price: str | None = None
    paid_tier_value: str | None = None


class A7LaunchPlan(_AgentModel):
    day_1_to_7: str | None = None
    day_8_to_14: str | None = None
    day_15_to_30: str | None = None


class A7Output(_AgentModel):
    """PRD Generator — product manager. ONLY runs if A6 verdict == GO."""
    product_name: str | None = None
    one_liner: str | None = None
    target_user_persona: str | None = None
    core_problem_statement: str | None = None
    mvp_features: list[A7Feature] = []
    explicitly_out_of_scope: list[str] = []
    success_metrics: list[str] = []
    monetization: A7Monetization | None = None
    launch_plan: A7LaunchPlan | None = None


class A8Output(_AgentModel):
    """Opportunity Brief — investment-analyst one-pager. ALWAYS runs."""
    title: str | None = None
    verdict_badge: str | None = None  # "🟢 GO" | "🔴 NO-GO" | "🟡 PIVOT"
    tldr: str | None = None
    the_pain: str | None = None
    the_gap: str | None = None
    the_user: str | None = None
    the_money: str | None = None
    scores: dict[str, Any] = {}
    top_reason_to_do_it: str | None = None
    top_reason_not_to: str | None = None
    if_i_were_to_start_today: str | None = None
    similar_successes: list[str] = []
    source: str | None = None
    analyzed_at: str | None = None


@dataclass
class PipelineResult:
    """All agent outputs for a single signal or cluster, plus run metadata."""
    raw_signal: dict[str, Any] = field(default_factory=dict)
    a1: A1Output | None = None
    a2: A2Output | None = None
    a3: A3Output | None = None
    a4: A4Output | None = None
    a5: A5Output | None = None
    a6: A6Output | None = None
    a7: A7Output | None = None
    a8: A8Output | None = None
    failed_agents: list[str] = field(default_factory=list)
    short_circuited_at: str | None = None  # "a1" if A1 rejected; None otherwise

    @property
    def verdict(self) -> str | None:
        return self.a6.verdict if self.a6 else None

    @property
    def opportunity_score(self) -> int | None:
        """Raw A4 total (0-70)."""
        return self.a4.total_score if self.a4 else None

    def to_storage_dict(self) -> dict[str, Any]:
        """Serialize each agent output as a JSON-ready dict (or None)."""
        def dump(model):
            return model.model_dump(mode="json") if model is not None else None
        return {
            "raw_signal": self.raw_signal,
            "a1": dump(self.a1),
            "a2": dump(self.a2),
            "a3": dump(self.a3),
            "a4": dump(self.a4),
            "a5": dump(self.a5),
            "a6": dump(self.a6),
            "a7": dump(self.a7),
            "a8": dump(self.a8),
            "failed_agents": self.failed_agents,
            "short_circuited_at": self.short_circuited_at,
        }
