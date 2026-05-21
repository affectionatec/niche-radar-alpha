"""Tests for niche_radar.agents.clustering — Jaccard pre-grouping and LLM refinement."""

from __future__ import annotations

from niche_radar.agents.clustering import (
    JACCARD_THRESHOLD,
    Cluster,
    cluster_extractions,
    jaccard_pre_cluster,
)


def _ex(rid, keywords, who="user", what="problem"):
    return {
        "raw_item_id": rid,
        "a1": {"pain_summary": f"summary for {rid}"},
        "a2": {"who": who, "what": what, "keywords": keywords},
    }


# ---------- Jaccard pre-grouping ----------


def test_distinct_keyword_sets_separate_clusters():
    ex = [
        _ex("a", ["aws", "cost", "report"]),
        _ex("b", ["video", "edit", "subtitle"]),
        _ex("c", ["postgres", "backup", "restore"]),
    ]
    groups = jaccard_pre_cluster(ex)
    assert len(groups) == 3
    assert all(len(g) == 1 for g in groups)


def test_overlapping_keywords_merge():
    # Two items sharing 2 of 3 keywords — Jaccard 2/4=0.5 ≥ threshold.
    ex = [
        _ex("a", ["aws", "cost", "report"]),
        _ex("b", ["aws", "cost", "billing"]),
        _ex("c", ["unrelated", "completely", "different"]),
    ]
    groups = jaccard_pre_cluster(ex)
    sizes = sorted(len(g) for g in groups)
    assert sizes == [1, 2]
    big = next(g for g in groups if len(g) == 2)
    assert {e["raw_item_id"] for e in big} == {"a", "b"}


def test_transitive_chaining():
    # a∩b high, b∩c high, but a∩c low — Union-Find still merges all three.
    ex = [
        _ex("a", ["aws", "cost", "report"]),
        _ex("b", ["aws", "report", "billing"]),
        _ex("c", ["aws", "billing", "invoice"]),
    ]
    groups = jaccard_pre_cluster(ex)
    assert len(groups) == 1
    assert {e["raw_item_id"] for e in groups[0]} == {"a", "b", "c"}


def test_empty_input_returns_empty():
    assert jaccard_pre_cluster([]) == []


def test_stemmer_treats_plurals_as_same():
    # "reports" → "report"; "billings" → "billing" — overlap should be high.
    ex = [
        _ex("a", ["aws", "cost", "report"]),
        _ex("b", ["aws", "costs", "reports"]),
    ]
    groups = jaccard_pre_cluster(ex)
    assert len(groups) == 1


# ---------- cluster_extractions (high-level) ----------


def test_cluster_extractions_no_llm_yields_singleton_clusters_for_distinct():
    ex = [
        _ex("a", ["aws"]),
        _ex("b", ["video"]),
        _ex("c", ["sql"]),
    ]
    clusters = cluster_extractions(ex, refinement_client=None)
    assert len(clusters) == 3
    assert all(isinstance(c, Cluster) for c in clusters)
    assert all(c.size == 1 for c in clusters)
    # Names should be derived from the dominant keyword
    names = {c.name for c in clusters}
    assert names == {"aws", "video", "sql"}


def test_cluster_extractions_small_groups_skip_llm(fake_llm):
    # 3-item group is below LLM_REFINE_MIN_SIZE=4 — no LLM call expected.
    client = fake_llm({})  # would return empty dict if called
    ex = [
        _ex("a", ["aws", "cost", "report"]),
        _ex("b", ["aws", "cost", "billing"]),
        _ex("c", ["aws", "cost", "invoice"]),
    ]
    clusters = cluster_extractions(ex, refinement_client=client)
    assert client.calls == []  # confirms LLM not invoked
    assert len(clusters) == 1
    assert clusters[0].size == 3


def test_cluster_extractions_large_group_invokes_llm_refinement(fake_llm):
    # 5-item pre-cluster (≥4) triggers LLM refinement.
    items = [
        _ex("a", ["aws", "cost", "report"]),
        _ex("b", ["aws", "cost", "billing"]),
        _ex("c", ["aws", "cost", "invoice"]),
        _ex("d", ["aws", "cost", "spending"]),
        _ex("e", ["aws", "cost", "monthly"]),
    ]
    # LLM splits into two sub-clusters
    canned = {
        "unknown": {  # FakeLLMClient identifies clustering prompt as "unknown" agent
            "clusters": [
                {"name": "aws cost reporting", "item_ids": ["a", "b", "e"]},
                {"name": "aws cost billing detail", "item_ids": ["c", "d"]},
            ]
        }
    }
    client = fake_llm(canned)
    clusters = cluster_extractions(items, refinement_client=client)
    assert len(client.calls) == 1
    assert len(clusters) == 2
    sizes = sorted(c.size for c in clusters)
    assert sizes == [2, 3]
    # Names get kebab-cased
    names = {c.name for c in clusters}
    assert "aws-cost-reporting" in names
    assert "aws-cost-billing-detail" in names


def test_cluster_extractions_llm_failure_falls_back_to_single_cluster(fake_llm):
    items = [
        _ex("a", ["aws", "cost", "report"]),
        _ex("b", ["aws", "cost", "billing"]),
        _ex("c", ["aws", "cost", "invoice"]),
        _ex("d", ["aws", "cost", "spending"]),
    ]
    # Make the FakeLLMClient raise on call
    client = fake_llm({"unknown": {"__raise__": "simulated network error"}})
    clusters = cluster_extractions(items, refinement_client=client)
    assert len(clusters) == 1
    assert clusters[0].size == 4


def test_cluster_extractions_llm_drops_items_get_recovered_in_leftover_cluster(fake_llm):
    # LLM returns only 3 of 4 items — the 4th must end up in a leftover cluster.
    items = [
        _ex("a", ["aws", "cost", "report"]),
        _ex("b", ["aws", "cost", "billing"]),
        _ex("c", ["aws", "cost", "invoice"]),
        _ex("d", ["aws", "cost", "spending"]),
    ]
    canned = {
        "unknown": {
            "clusters": [
                {"name": "aws costs", "item_ids": ["a", "b", "c"]},
            ]
        }
    }
    client = fake_llm(canned)
    clusters = cluster_extractions(items, refinement_client=client)
    all_ids: set[str] = set()
    for c in clusters:
        all_ids.update(c.raw_item_ids)
    assert all_ids == {"a", "b", "c", "d"}


def test_cluster_extractions_keyword_fallback_to_pain_summary():
    # No A2 keywords but A1 pain_summary words should still drive grouping.
    a = {"raw_item_id": "a", "a1": {"pain_summary": "aws cost report friction"}, "a2": {}}
    b = {"raw_item_id": "b", "a1": {"pain_summary": "aws cost report frustration"}, "a2": {}}
    c = {"raw_item_id": "c", "a1": {"pain_summary": "video subtitle workflow"}, "a2": {}}
    clusters = cluster_extractions([a, b, c], refinement_client=None)
    # a and b share 3 of 4 tokens → should merge
    sizes = sorted(c.size for c in clusters)
    assert sizes == [1, 2]
