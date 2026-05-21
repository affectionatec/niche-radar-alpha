"""Unit tests for niche_radar.agents.prompts."""

from niche_radar.agents.models import A1Output, A2Output, A3Output, A4Output, A4Score, A4Scores
from niche_radar.agents.prompts import (
    AGENT_IDS,
    SYSTEM_PROMPTS,
    build_system_prompt,
    build_user_prompt,
)


_RAW = {
    "text": "I copy AWS Cost Explorer into a spreadsheet every month.",
    "source": "reddit",
    "url": "https://reddit.com/r/sysadmin/x",
    "scraped_at": "2026-05-20T10:00:00Z",
}


def test_all_eight_agent_system_prompts_exist():
    for aid in AGENT_IDS:
        sp = build_system_prompt(aid)
        assert isinstance(sp, str)
        assert len(sp) > 100


def test_system_prompts_contain_return_json_instruction():
    # Every agent must instruct the model to return JSON only.
    for aid in AGENT_IDS:
        sp = SYSTEM_PROMPTS[aid].lower()
        assert "json" in sp


def test_a1_user_prompt_substitutes_signal_fields():
    prompt = build_user_prompt("a1", {"raw_signal": _RAW})
    assert "reddit" in prompt
    assert _RAW["url"] in prompt
    assert "AWS Cost Explorer" in prompt
    assert "$source" not in prompt  # all placeholders resolved


def test_a2_user_prompt_uses_a1_pain_summary():
    ctx = {"raw_signal": _RAW, "a1": A1Output(is_valid_signal=True, pain_summary="Manual AWS cost reporting is tedious")}
    prompt = build_user_prompt("a2", ctx)
    assert "Manual AWS cost reporting is tedious" in prompt
    assert "AWS Cost Explorer" in prompt


def test_a4_user_prompt_pulls_nested_a3_fields():
    ctx = {
        "raw_signal": _RAW,
        "a2": A2Output(what="copy data manually", who="sysadmins", emotional_intensity=7, willingness_to_pay_signal=True),
        "a3": A3Output(key_gap="cheap simple report tool", saturation_score=4, market_maturity="growing", estimated_tam="$10-100M"),
    }
    prompt = build_user_prompt("a4", ctx)
    assert "cheap simple report tool" in prompt
    assert "growing" in prompt
    assert "$10-100M" in prompt
    assert "7/10" in prompt


def test_a5_user_prompt_pulls_doubly_nested_a4_dimension_scores():
    a4 = A4Output(
        scores=A4Scores(
            technical_feasibility=A4Score(score=8, rationale="x"),
            distribution_clarity=A4Score(score=6, rationale="x"),
        ),
        total_score=42,
    )
    ctx = {
        "raw_signal": _RAW,
        "a2": A2Output(what="problem", who="user", desired_outcome="outcome"),
        "a3": A3Output(buyer_type="smb", price_ceiling="$20/mo"),
        "a4": a4,
    }
    prompt = build_user_prompt("a5", ctx)
    assert "8/10" in prompt  # technical_feasibility score
    assert "6/10" in prompt  # distribution_clarity score
    assert "$20/mo" in prompt


def test_partial_context_substitutes_unknown_not_raises():
    # No a2 or later — A5 should still render with "unknown" placeholders, not crash.
    prompt = build_user_prompt("a5", {"raw_signal": _RAW})
    assert "unknown" in prompt
    assert "$a2_what" not in prompt


def test_a8_user_prompt_embeds_all_upstream_outputs():
    ctx = {
        "raw_signal": _RAW,
        "a1": A1Output(is_valid_signal=True, pain_summary="cost reporting pain"),
        "a2": A2Output(what="copy data", who="sysadmins", emotional_intensity=7),
        "a3": A3Output(key_gap="simple cheap reports"),
        "a4": A4Output(total_score=48),
        "a5": A5_with_feas(8),
        "a6": A6_with_conf("GO", 0.85),
    }
    prompt = build_user_prompt("a8", ctx)
    # Each upstream output must be embedded as JSON in the user prompt
    assert "A1 OUTPUT" in prompt
    assert "A2 OUTPUT" in prompt
    assert "cost reporting pain" in prompt
    assert "copy data" in prompt
    # Concrete score values
    assert "pain_intensity: 7" in prompt
    assert "opportunity_score: 48" in prompt
    assert "feasibility: 8" in prompt
    assert "confidence: 0.85" in prompt
    # Source/timestamp instructions present
    assert "source: reddit" in prompt
    assert "2026-05-20T10:00:00Z" in prompt


def A5_with_feas(score):
    from niche_radar.agents.models import A5Output
    return A5Output(feasibility_score=score)


def A6_with_conf(verdict, conf):
    from niche_radar.agents.models import A6Output
    return A6Output(verdict=verdict, confidence=conf)


def test_a8_handles_missing_agents_gracefully():
    # If A7 never ran (NO-GO verdict), A8 must still produce a coherent prompt.
    ctx = {
        "raw_signal": _RAW,
        "a1": A1Output(is_valid_signal=True),
        "a6": A6_with_conf("NO-GO", 0.9),
    }
    prompt = build_user_prompt("a8", ctx)
    assert "A7 OUTPUT: (agent did not run or failed)" in prompt
    assert "A3 OUTPUT: (agent did not run or failed)" in prompt


def test_a8_renders_lists_as_json_not_python_repr():
    ctx = {
        "raw_signal": _RAW,
        "a4": A4Output(top_3_strengths=["strong demand", "low competition", "clear monetization"]),
    }
    prompt = build_user_prompt("a8", ctx)
    # Must use JSON quoting, not Python repr quoting
    assert '"strong demand"' in prompt
