"""Pydantic v2 models for each agent's JSON output schema."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# A1 — Signal Filter
# ---------------------------------------------------------------------------

class A1Output(BaseModel):
    is_valid_signal: bool
    confidence: float
    pain_summary: str | None = None
    rejection_reason: str | None = None
    signal_type: Literal["pain_point", "feature_request", "competitor_complaint", "noise"] = "noise"


# ---------------------------------------------------------------------------
# A2 — Pain Extractor
# ---------------------------------------------------------------------------

class A2Output(BaseModel):
    who: str | None = None
    what: str | None = None
    when: str | None = None
    current_workaround: str | None = None
    why_current_sucks: str | None = None
    desired_outcome: str | None = None
    emotional_intensity: int = 5  # 1-10
    frequency: Literal["daily", "weekly", "monthly", "rarely"] = "weekly"
    affected_scale: Literal["individual", "team", "company", "industry"] = "individual"
    willingness_to_pay_signal: bool = False
    pay_signal_evidence: str | None = None
    keywords: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# A3 — Market Researcher
# ---------------------------------------------------------------------------

class ExistingSolution(BaseModel):
    name: str
    type: Literal["saas", "open_source", "manual_process", "enterprise"]
    price_range: Literal["free", "$1-10/mo", "$10-50/mo", "$50-200/mo", "enterprise"]
    main_weakness: str
    market_position: Literal["leader", "challenger", "niche"]


class A3Output(BaseModel):
    existing_solutions: list[ExistingSolution] = field(default_factory=list)
    market_leader: str | None = None
    market_maturity: Literal["emerging", "growing", "mature", "declining"] = "growing"
    saturation_score: int = 5  # 1-10
    key_gap: str | None = None
    price_ceiling: str | None = None
    buyer_type: Literal["consumer", "smb", "enterprise", "developer"] = "smb"
    estimated_tam: Literal["<$1M", "$1-10M", "$10-100M", ">$100M"] = "$1-10M"
    competition_notes: str | None = None


# ---------------------------------------------------------------------------
# A4 — Opportunity Scorer
# ---------------------------------------------------------------------------

class ScoreDetail(BaseModel):
    score: int  # 1-10
    rationale: str


class A4Scores(BaseModel):
    problem_clarity: ScoreDetail
    market_size: ScoreDetail
    willingness_to_pay: ScoreDetail
    competition_gap: ScoreDetail
    technical_feasibility: ScoreDetail
    distribution_clarity: ScoreDetail
    trend_momentum: ScoreDetail


class A4Output(BaseModel):
    scores: A4Scores
    total_score: int  # 0-70
    top_3_strengths: list[str] = field(default_factory=list)
    top_3_risks: list[str] = field(default_factory=list)
    comparable_products: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# A5 — Feasibility Analyst
# ---------------------------------------------------------------------------

class TechStack(BaseModel):
    backend: str
    frontend: str
    ai_components: str
    key_integrations: list[str] = field(default_factory=list)


class A5Output(BaseModel):
    mvp_scope: str | None = None
    core_features: list[str] = field(default_factory=list)
    explicitly_cut_from_mvp: list[str] = field(default_factory=list)
    tech_stack: TechStack | None = None
    estimated_weeks_to_mvp: int = 4
    biggest_technical_risk: str | None = None
    distribution_strategy: str | None = None
    first_channel: Literal["Reddit", "HN", "cold email", "Twitter", "SEO", "other"] = "other"
    revenue_model: Literal["subscription", "one-time", "usage-based", "freemium", "ads"] = "subscription"
    price_hypothesis: str | None = None
    feasibility_score: int = 5  # 1-10
    solo_buildable: bool = True


# ---------------------------------------------------------------------------
# A6 — Go / No-Go Judge
# ---------------------------------------------------------------------------

class A6Output(BaseModel):
    verdict: Literal["GO", "NO-GO", "PIVOT"]
    confidence: float
    one_line_rationale: str
    full_rationale: str | None = None
    killer_risk: str | None = None
    pivot_suggestion: str | None = None
    conditions_to_reconsider: str | None = None
    recommended_next_step: str | None = None


# ---------------------------------------------------------------------------
# A7 — PRD Generator (only runs on GO)
# ---------------------------------------------------------------------------

class MvpFeature(BaseModel):
    feature: str
    user_story: str
    acceptance_criteria: str
    priority: Literal["P0", "P1"]


class Monetization(BaseModel):
    model: Literal["subscription", "one-time", "freemium", "usage"]
    free_tier: str | None = None
    paid_tier_price: str | None = None
    paid_tier_value: str | None = None


class LaunchPlan(BaseModel):
    day_1_to_7: str | None = None
    day_8_to_14: str | None = None
    day_15_to_30: str | None = None


class A7Output(BaseModel):
    product_name: str | None = None
    one_liner: str | None = None
    target_user_persona: str | None = None
    core_problem_statement: str | None = None
    mvp_features: list[MvpFeature] = field(default_factory=list)
    explicitly_out_of_scope: list[str] = field(default_factory=list)
    success_metrics: list[str] = field(default_factory=list)
    monetization: Monetization | None = None
    launch_plan: LaunchPlan | None = None


# ---------------------------------------------------------------------------
# A8 — Opportunity Brief (always runs)
# ---------------------------------------------------------------------------

class BriefScores(BaseModel):
    pain_intensity: int | None = None
    opportunity_score: str | None = None
    feasibility: str | None = None
    confidence: str | None = None


class A8Output(BaseModel):
    title: str | None = None
    verdict_badge: Literal["🟢 GO", "🔴 NO-GO", "🟡 PIVOT"] | None = None
    tldr: str | None = None
    the_pain: str | None = None
    the_gap: str | None = None
    the_user: str | None = None
    the_money: str | None = None
    scores: BriefScores | None = None
    top_reason_to_do_it: str | None = None
    top_reason_not_to: str | None = None
    if_i_were_to_start_today: str | None = None
    similar_successes: list[str] = field(default_factory=list)
    source: str | None = None
    analyzed_at: str | None = None


# ---------------------------------------------------------------------------
# PipelineResult — full run output
# ---------------------------------------------------------------------------

@dataclass
class PipelineResult:
    raw_signal: dict
    a1: dict | None = None
    a2: dict | None = None
    a3: dict | None = None
    a4: dict | None = None
    a5: dict | None = None
    a6: dict | None = None
    a7: dict | None = None
    a8: dict | None = None
    verdict: str = "UNKNOWN"
    opportunity_score: float | None = None
    tier: str | None = None
    analyzed_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        """Serialize to a plain dict for JSON storage."""
        import dataclasses
        return dataclasses.asdict(self)
