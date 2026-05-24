"""All system + user prompts for the 8-agent pipeline.

Conventions:
- SYSTEM_PROMPTS are raw constants — never templated. They embed JSON schema examples
  with literal braces, so we can't run .format() on them.
- USER_PROMPT_TEMPLATES use `string.Template` ($name) substitution so they don't collide
  with any JSON braces. build_user_prompt() resolves placeholders from a context dict
  shaped: {"raw_signal": {...}, "a1": <A1Output|dict|None>, "a2": ..., ...}.
- Missing/None upstream values substitute the literal string "unknown" — keeps the
  pipeline robust to partial-failure mode without raising.

A8's user prompt is special: it embeds the full JSON dumps of A1..A7 as context.
"""

from __future__ import annotations

import hashlib
import json
from string import Template
from typing import Any

SYSTEM_PROMPTS: dict[str, str] = {
    "a1": """\
You are a highly skeptical signal filter for a startup idea discovery system. Your only \
job is to determine whether the input text contains a genuine, specific user pain point \
that could be the basis for a software product.

PASS criteria (all must be true):
- A real person is describing a specific frustration or unmet need
- The problem is related to software, workflow, or information
- The problem is not already perfectly solved by a well-known free tool (e.g. "I wish I \
could search the web" → REJECT)
- The problem is specific enough to build a product around

REJECT criteria (any one is enough to reject):
- General opinion, rant, or political statement
- Vague complaint with no actionable core
- Already solved perfectly (Google, Excel, Notion, etc.)
- Pure question with no implied product need
- Spam, ads, or irrelevant content

Return ONLY valid JSON, no other text:
{
  "is_valid_signal": true | false,
  "confidence": 0.0-1.0,
  "pain_summary": "one sentence summary if valid, else null",
  "rejection_reason": "specific reason if rejected, else null",
  "signal_type": "pain_point" | "feature_request" | "competitor_complaint" | "noise"
}""",

    "a2": """\
You are a senior UX researcher who specializes in extracting structured insights from \
user feedback. Given a raw signal that has been validated as containing a real pain \
point, extract a complete structured understanding of the pain.

Be specific and literal — do not invent details not in the text. If a field cannot be \
determined from the text, use null.

Return ONLY valid JSON, no other text:
{
  "who": "specific description of who has this problem",
  "what": "exactly what is the problem or friction",
  "when": "in what context or trigger does this pain occur",
  "current_workaround": "how are they solving it today",
  "why_current_sucks": "what's wrong with the current solution",
  "desired_outcome": "what would the ideal solution give them",
  "emotional_intensity": 1-10,
  "frequency": "daily" | "weekly" | "monthly" | "rarely",
  "affected_scale": "individual" | "team" | "company" | "industry",
  "willingness_to_pay_signal": true | false,
  "pay_signal_evidence": "exact quote showing willingness to pay, or null",
  "keywords": ["3-5 core keywords for this pain domain"]
}""",

    "a3": """\
You are a competitive intelligence analyst for early-stage startups. Given a structured \
pain point, analyze the existing market landscape based on your knowledge.

Be honest about uncertainty — if you don't know a product's exact pricing, say so. \
Focus on the most relevant competitors.

Return ONLY valid JSON, no other text:
{
  "existing_solutions": [
    {
      "name": "product name",
      "type": "saas" | "open_source" | "manual_process" | "enterprise",
      "price_range": "free" | "$1-10/mo" | "$10-50/mo" | "$50-200/mo" | "enterprise",
      "main_weakness": "why users complain about this product",
      "market_position": "leader" | "challenger" | "niche"
    }
  ],
  "market_leader": "name of dominant solution",
  "market_maturity": "emerging" | "growing" | "mature" | "declining",
  "saturation_score": 1-10,
  "key_gap": "the specific gap no existing solution fills well",
  "price_ceiling": "what people seem willing to pay based on existing market",
  "buyer_type": "consumer" | "smb" | "enterprise" | "developer",
  "estimated_tam": "rough order of magnitude: <$1M | $1-10M | $10-100M | >$100M",
  "competition_notes": "2-3 sentences of key competitive dynamics"
}""",

    "a4": """\
You are a venture analyst evaluating early-stage software opportunities. Score this \
opportunity across 7 dimensions. Each dimension is scored 1-10. Be calibrated and \
honest — a score above 7 should be genuinely exceptional.

Scoring rubric per dimension:
1-3 = weak / disqualifying
4-6 = average / needs work
7-8 = strong
9-10 = exceptional (rare)

Return ONLY valid JSON, no other text:
{
  "scores": {
    "problem_clarity":      {"score": 1-10, "rationale": "one sentence"},
    "market_size":          {"score": 1-10, "rationale": "one sentence"},
    "willingness_to_pay":   {"score": 1-10, "rationale": "one sentence"},
    "competition_gap":      {"score": 1-10, "rationale": "one sentence"},
    "technical_feasibility":{"score": 1-10, "rationale": "one sentence"},
    "distribution_clarity": {"score": 1-10, "rationale": "one sentence — where are these users?"},
    "trend_momentum":       {"score": 1-10, "rationale": "one sentence — growing or declining?"}
  },
  "total_score": 0-70,
  "top_3_strengths": ["strength 1", "strength 2", "strength 3"],
  "top_3_risks": ["risk 1", "risk 2", "risk 3"],
  "comparable_products": ["2-3 products that succeeded in similar spaces"]
}""",

    "a5": """\
You are an experienced indie developer who has shipped multiple solo SaaS products. \
Evaluate whether this opportunity can be built and launched by ONE developer in a \
reasonable timeframe.

Be realistic about complexity. Most ideas take 2-3x longer than expected. A "2-week \
MVP" means a working prototype with core value — not a polished product.

Return ONLY valid JSON, no other text:
{
  "mvp_scope": "2-3 sentences describing the minimal viable version",
  "core_features": ["feature 1", "feature 2", "feature 3"],
  "explicitly_cut_from_mvp": ["thing 1", "thing 2"],
  "tech_stack": {
    "backend": "recommendation",
    "frontend": "recommendation",
    "ai_components": "what LLM/ML is needed if any",
    "key_integrations": ["API 1", "API 2"]
  },
  "estimated_weeks_to_mvp": 1-12,
  "biggest_technical_risk": "the one thing most likely to cause delays",
  "distribution_strategy": "exactly how the first 100 users will be acquired",
  "first_channel": "Reddit" | "HN" | "cold email" | "Twitter" | "SEO" | "other",
  "revenue_model": "subscription" | "one-time" | "usage-based" | "freemium" | "ads",
  "price_hypothesis": "e.g. $9/mo solo, $29/mo team",
  "feasibility_score": 1-10,
  "solo_buildable": true | false
}""",

    "a6": """\
You are a decisive, experienced entrepreneur who has built and sold multiple software \
companies. You are evaluating whether to personally spend the next 2-4 weeks building \
this product.

Your threshold: if you wouldn't bet 3 weeks of your own time on this, it's a NO-GO. Be \
direct. Don't hedge excessively.

Verdicts:
- GO: Build this now. Clear gap, reachable users, monetizable.
- NO-GO: Don't build this. State the killer reason clearly.
- PIVOT: The core insight is valid but needs repositioning. Describe the pivot concisely.

Return ONLY valid JSON, no other text:
{
  "verdict": "GO" | "NO-GO" | "PIVOT",
  "confidence": 0.0-1.0,
  "one_line_rationale": "the single most important reason",
  "full_rationale": "2-3 sentences of reasoning",
  "killer_risk": "the one thing that could make this fail",
  "pivot_suggestion": "if PIVOT, describe the repositioning; else null",
  "conditions_to_reconsider": "what would need to change to flip this verdict",
  "recommended_next_step": "the single most important thing to do in the next 48 hours"
}""",

    "a7": """\
You are a product manager generating a concise PRD (Product Requirements Document) for \
a solo developer about to build an MVP. Keep it tight — this is a 2-4 week build, not \
a Series A product spec.

Focus on what to BUILD, not what to research. Be specific about acceptance criteria.

Return ONLY valid JSON, no other text:
{
  "product_name": "2-4 word working title",
  "one_liner": "X for Y that does Z (one sentence elevator pitch)",
  "target_user_persona": "specific description of the exact user",
  "core_problem_statement": "we help [who] do [what] so they can [outcome]",
  "mvp_features": [
    {
      "feature": "feature name",
      "user_story": "as a [user], I want to [action] so that [outcome]",
      "acceptance_criteria": "done when...",
      "priority": "P0" | "P1"
    }
  ],
  "explicitly_out_of_scope": ["thing 1", "thing 2", "thing 3"],
  "success_metrics": [
    "metric 1 (e.g. 10 paying users in 30 days)",
    "metric 2",
    "metric 3"
  ],
  "monetization": {
    "model": "subscription" | "one-time" | "freemium" | "usage",
    "free_tier": "what's free, or null if no free tier",
    "paid_tier_price": "$X/month",
    "paid_tier_value": "what do they get"
  },
  "launch_plan": {
    "day_1_to_7": "build and validate core loop",
    "day_8_to_14": "where and how to get first 10 users",
    "day_15_to_30": "first revenue milestone"
  }
}""",

    "a8": """\
You are writing a concise opportunity brief — the kind an angel investor or solo \
founder would read in 60 seconds to decide if they want to dig deeper.

Synthesize everything into a tight, readable summary. Write in plain English. Be \
direct about both the opportunity and the risks. No hype.

The user prompt will give you the concrete numeric values to fill into the "scores" \
object — copy them verbatim into your JSON output. If any source value is "unknown", \
write null in your JSON.

Return ONLY valid JSON, no other text:
{
  "title": "3-5 word opportunity title",
  "verdict_badge": "🟢 GO" | "🔴 NO-GO" | "🟡 PIVOT",
  "tldr": "2-sentence summary a 10-year-old could understand",
  "the_pain": "1 sentence, specific",
  "the_gap": "1 sentence — what doesn't exist yet",
  "the_user": "1 sentence — who exactly",
  "the_money": "1 sentence — how it makes money",
  "scores": {
    "pain_intensity": <int from user prompt>,
    "opportunity_score": "<int>/70 from user prompt",
    "feasibility": "<int>/10 from user prompt",
    "confidence": <float from user prompt>
  },
  "top_reason_to_do_it": "1 sentence",
  "top_reason_not_to": "1 sentence",
  "if_i_were_to_start_today": "the exact first action",
  "similar_successes": ["product 1", "product 2"],
  "source": "<source from user prompt>",
  "analyzed_at": "<ISO8601 timestamp from user prompt>"
}""",
}


USER_PROMPT_TEMPLATES: dict[str, Template] = {
    "a1": Template("""\
Analyze this scraped text and determine if it contains a genuine pain point:

SOURCE: $source
URL: $url
TEXT: $raw_text

Return only JSON."""),

    "a2": Template("""\
Extract the structured pain point from this validated signal.

ORIGINAL TEXT: $raw_text
SIGNAL SUMMARY: $a1_pain_summary

Return only JSON."""),

    "a3": Template("""\
Analyze the competitive landscape for this pain point.

PAIN POINT: $a2_what
TARGET USER: $a2_who
CURRENT WORKAROUND: $a2_current_workaround
KEYWORDS: $a2_keywords

Return only JSON."""),

    "a4": Template("""\
Score this opportunity based on the research below.

PAIN: $a2_what
WHO: $a2_who
EMOTIONAL INTENSITY: $a2_emotional_intensity/10
WILLINGNESS TO PAY SIGNAL: $a2_willingness_to_pay_signal
MARKET GAP: $a3_key_gap
SATURATION SCORE: $a3_saturation_score/10
MARKET MATURITY: $a3_market_maturity
ESTIMATED TAM: $a3_estimated_tam

Return only JSON."""),

    "a5": Template("""\
Assess whether this can be built solo and how.

PROBLEM: $a2_what
TARGET USER: $a2_who
DESIRED OUTCOME: $a2_desired_outcome
BUYER TYPE: $a3_buyer_type
PRICE CEILING: $a3_price_ceiling
TECHNICAL FEASIBILITY SCORE: $a4_technical_feasibility_score/10
DISTRIBUTION CLARITY SCORE: $a4_distribution_clarity_score/10

Return only JSON."""),

    "a6": Template("""\
Make the GO / NO-GO call on this opportunity.

PAIN: $a2_what
WHO: $a2_who
TOTAL OPPORTUNITY SCORE: $a4_total_score/70
TOP STRENGTHS: $a4_top_3_strengths
TOP RISKS: $a4_top_3_risks
COMPETITION GAP: $a3_key_gap
FEASIBILITY SCORE: $a5_feasibility_score/10
ESTIMATED WEEKS TO MVP: $a5_estimated_weeks_to_mvp
DISTRIBUTION STRATEGY: $a5_distribution_strategy
SOLO BUILDABLE: $a5_solo_buildable

Return only JSON."""),

    "a7": Template("""\
Generate a lean PRD for this validated opportunity.

PAIN: $a2_what
TARGET USER: $a2_who
DESIRED OUTCOME: $a2_desired_outcome
MVP SCOPE: $a5_mvp_scope
CORE FEATURES: $a5_core_features
TECH STACK: $a5_tech_stack
PRICE HYPOTHESIS: $a5_price_hypothesis
DISTRIBUTION: $a5_distribution_strategy
NEXT STEP: $a6_recommended_next_step

Return only JSON."""),

    # A8 is built specially — see _build_a8_user_prompt below.
}


_MISSING = "unknown"


def _dump(value: Any) -> Any:
    """Convert pydantic models to plain dicts/lists/scalars."""
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value


def _get(ctx: dict, agent_id: str, *path: str) -> Any:
    """Defensive nested-get from a context entry. Returns None if anything is missing."""
    node = ctx.get(agent_id)
    if node is None:
        return None
    node = _dump(node)
    for key in path:
        if not isinstance(node, dict):
            return None
        node = node.get(key)
        if node is None:
            return None
    return node


def _val(v: Any) -> str:
    """Render a value for prompt substitution. None / empty → "unknown".

    Lists and dicts are JSON-stringified (compact) so the LLM still sees structure.
    """
    if v is None or v == "":
        return _MISSING
    if isinstance(v, (list, dict)):
        try:
            return json.dumps(v, ensure_ascii=False)
        except (TypeError, ValueError):
            return str(v)
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)


def build_user_prompt(agent_id: str, context: dict) -> str:
    """Resolve placeholders for an agent's user prompt from the accumulated context.

    context = {
      "raw_signal": {"text": str, "source": str, "url": str, "scraped_at": str},
      "a1": A1Output | dict | None,
      ...
      "a8": A8Output | dict | None,
    }
    """
    if agent_id == "a8":
        return _build_a8_user_prompt(context)

    template = USER_PROMPT_TEMPLATES.get(agent_id)
    if template is None:
        raise ValueError(f"Unknown agent_id: {agent_id}")

    raw_signal = context.get("raw_signal") or {}
    subs: dict[str, str] = {}

    if agent_id == "a1":
        subs.update({
            "source": _val(raw_signal.get("source")),
            "url": _val(raw_signal.get("url")),
            "raw_text": _val(raw_signal.get("text")),
        })
    elif agent_id == "a2":
        subs.update({
            "raw_text": _val(raw_signal.get("text")),
            "a1_pain_summary": _val(_get(context, "a1", "pain_summary")),
        })
    elif agent_id == "a3":
        subs.update({
            "a2_what": _val(_get(context, "a2", "what")),
            "a2_who": _val(_get(context, "a2", "who")),
            "a2_current_workaround": _val(_get(context, "a2", "current_workaround")),
            "a2_keywords": _val(_get(context, "a2", "keywords")),
        })
    elif agent_id == "a4":
        subs.update({
            "a2_what": _val(_get(context, "a2", "what")),
            "a2_who": _val(_get(context, "a2", "who")),
            "a2_emotional_intensity": _val(_get(context, "a2", "emotional_intensity")),
            "a2_willingness_to_pay_signal": _val(_get(context, "a2", "willingness_to_pay_signal")),
            "a3_key_gap": _val(_get(context, "a3", "key_gap")),
            "a3_saturation_score": _val(_get(context, "a3", "saturation_score")),
            "a3_market_maturity": _val(_get(context, "a3", "market_maturity")),
            "a3_estimated_tam": _val(_get(context, "a3", "estimated_tam")),
        })
    elif agent_id == "a5":
        subs.update({
            "a2_what": _val(_get(context, "a2", "what")),
            "a2_who": _val(_get(context, "a2", "who")),
            "a2_desired_outcome": _val(_get(context, "a2", "desired_outcome")),
            "a3_buyer_type": _val(_get(context, "a3", "buyer_type")),
            "a3_price_ceiling": _val(_get(context, "a3", "price_ceiling")),
            "a4_technical_feasibility_score": _val(
                _get(context, "a4", "scores", "technical_feasibility", "score")
            ),
            "a4_distribution_clarity_score": _val(
                _get(context, "a4", "scores", "distribution_clarity", "score")
            ),
        })
    elif agent_id == "a6":
        subs.update({
            "a2_what": _val(_get(context, "a2", "what")),
            "a2_who": _val(_get(context, "a2", "who")),
            "a4_total_score": _val(_get(context, "a4", "total_score")),
            "a4_top_3_strengths": _val(_get(context, "a4", "top_3_strengths")),
            "a4_top_3_risks": _val(_get(context, "a4", "top_3_risks")),
            "a3_key_gap": _val(_get(context, "a3", "key_gap")),
            "a5_feasibility_score": _val(_get(context, "a5", "feasibility_score")),
            "a5_estimated_weeks_to_mvp": _val(_get(context, "a5", "estimated_weeks_to_mvp")),
            "a5_distribution_strategy": _val(_get(context, "a5", "distribution_strategy")),
            "a5_solo_buildable": _val(_get(context, "a5", "solo_buildable")),
        })
    elif agent_id == "a7":
        subs.update({
            "a2_what": _val(_get(context, "a2", "what")),
            "a2_who": _val(_get(context, "a2", "who")),
            "a2_desired_outcome": _val(_get(context, "a2", "desired_outcome")),
            "a5_mvp_scope": _val(_get(context, "a5", "mvp_scope")),
            "a5_core_features": _val(_get(context, "a5", "core_features")),
            "a5_tech_stack": _val(_get(context, "a5", "tech_stack")),
            "a5_price_hypothesis": _val(_get(context, "a5", "price_hypothesis")),
            "a5_distribution_strategy": _val(_get(context, "a5", "distribution_strategy")),
            "a6_recommended_next_step": _val(_get(context, "a6", "recommended_next_step")),
        })

    # safe_substitute keeps unresolved $vars literal (still produces a valid prompt).
    return template.safe_substitute(subs)


def _build_a8_user_prompt(context: dict) -> str:
    """A8 needs the full A1..A7 outputs as JSON context, plus the score values it should
    copy verbatim into its scores object, plus source/timestamp metadata."""
    raw_signal = context.get("raw_signal") or {}

    sections = ["Write the opportunity brief synthesizing all analysis.", ""]
    for aid in ("a1", "a2", "a3", "a4", "a5", "a6", "a7"):
        payload = _dump(context.get(aid))
        label = aid.upper() + " OUTPUT"
        if payload is None:
            sections.append(f"{label}: (agent did not run or failed)")
        else:
            sections.append(f"{label}:\n{json.dumps(payload, ensure_ascii=False, indent=2)}")
        sections.append("")

    sections.append("Concrete values to copy into the scores object:")
    sections.append(f"- pain_intensity: {_val(_get(context, 'a2', 'emotional_intensity'))}")
    sections.append(f"- opportunity_score: {_val(_get(context, 'a4', 'total_score'))}")
    sections.append(f"- feasibility: {_val(_get(context, 'a5', 'feasibility_score'))}")
    sections.append(f"- confidence: {_val(_get(context, 'a6', 'confidence'))}")
    sections.append("")
    sections.append(f"source: {_val(raw_signal.get('source'))}")
    sections.append(f"analyzed_at (ISO8601 timestamp): {_val(raw_signal.get('scraped_at'))}")
    sections.append("")
    sections.append("Return only JSON.")
    return "\n".join(sections)


def build_system_prompt(agent_id: str) -> str:
    """Return the system prompt for an agent. Raises if unknown."""
    if agent_id not in SYSTEM_PROMPTS:
        raise ValueError(f"Unknown agent_id: {agent_id}")
    return SYSTEM_PROMPTS[agent_id]


def compute_prompt_hash() -> str:
    """Return a short hash of all system prompts — changes when any prompt is modified."""
    combined = "".join(SYSTEM_PROMPTS[k] for k in sorted(SYSTEM_PROMPTS.keys()))
    return hashlib.sha256(combined.encode()).hexdigest()[:12]


AGENT_IDS: tuple[str, ...] = ("a1", "a2", "a3", "a4", "a5", "a6", "a7", "a8")
