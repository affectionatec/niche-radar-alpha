"""Cluster A1-pass extractions by pain similarity.

Two-step strategy:
  1. Jaccard pre-grouping on A2.keywords (no LLM, deterministic): build Union-Find
     components where any pair with Jaccard similarity >= JACCARD_THRESHOLD is merged.
  2. LLM refinement ONLY for pre-clusters with >= LLM_REFINE_MIN_SIZE items.
     A single LLM call confirms coherence or splits the pre-cluster, and assigns each
     resulting cluster a short name.

For small pre-clusters (<= LLM_REFINE_MIN_SIZE-1 items, including singletons), the cluster
name is just the most-frequent keyword across the items — no LLM cost.

This keeps clustering cost bounded and deterministic for the easy cases, while letting the
LLM resolve the ambiguous "is pain A the same problem as pain B" cases.
"""

from __future__ import annotations

import json
import re
import uuid
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

import os

import structlog

from niche_radar.agents.orchestrator import BudgetExceeded
from niche_radar.llm.base import LLMClient

logger = structlog.get_logger()

JACCARD_THRESHOLD = float(os.environ.get("NR_JACCARD_THRESHOLD", "0.5"))
LLM_REFINE_MIN_SIZE = int(os.environ.get("NR_CLUSTER_LLM_MIN_SIZE", "4"))
LLM_MAX_ITEMS_PER_CALL = int(os.environ.get("NR_CLUSTER_LLM_MAX_ITEMS", "40"))
LLM_TEMPERATURE = float(os.environ.get("NR_CLUSTER_LLM_TEMP", "0.2"))

_CLUSTERING_SYSTEM_PROMPT = """\
You are deduping pain points for a startup idea discovery system. Below are several \
similar pain extractions from user feedback. Decide which items describe the SAME \
underlying problem (could be solved by the same product) vs. distinct problems.

Group the items into coherent clusters. If all items describe the same problem, return \
a single cluster. If they're a mix, return multiple clusters. A cluster of one item is \
fine if that item is genuinely distinct from the others.

Each cluster gets a short kebab-case name (2-5 words) describing the shared pain.

Return ONLY valid JSON, no other text:
{
  "clusters": [
    {"name": "short-kebab-case-name", "item_ids": ["id1", "id2"]}
  ]
}"""


@dataclass
class Cluster:
    cluster_id: str
    name: str
    raw_item_ids: list[str]
    extractions: list[dict] = field(default_factory=list)  # full extraction dicts

    @property
    def size(self) -> int:
        return len(self.raw_item_ids)


# ---------- Jaccard pre-grouping (no LLM) ----------


def _keyword_set(extraction: dict) -> set[str]:
    """Lowercase + light stem on A2.keywords; fall back to A1.pain_summary tokens."""
    a2 = extraction.get("a2") or {}
    kws = a2.get("keywords") or []
    if not kws and (a1 := extraction.get("a1")):
        # Fall back to pain_summary tokens for items where A2 returned nothing useful
        summary = (a1.get("pain_summary") or "").lower()
        kws = re.findall(r"[a-z][a-z0-9-]{2,}", summary)
    return {_stem(k) for k in kws if k and isinstance(k, str)}


def _stem(token: str) -> str:
    """Trivial stemmer — strip trailing s/ing. Good enough for keyword overlap."""
    t = token.lower().strip()
    if t.endswith("ing") and len(t) > 5:
        return t[:-3]
    if t.endswith("ed") and len(t) > 4:
        return t[:-2]
    if t.endswith("s") and len(t) > 3 and not t.endswith("ss"):
        return t[:-1]
    return t


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _union_find_groups(n: int, edges: list[tuple[int, int]]) -> list[list[int]]:
    """Standard Union-Find; returns list of groups as index lists."""
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for i, j in edges:
        union(i, j)

    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    return list(groups.values())


def jaccard_pre_cluster(extractions: list[dict]) -> list[list[dict]]:
    """Return a list of pre-clusters, each a list of extraction dicts."""
    if not extractions:
        return []
    keyword_sets = [_keyword_set(e) for e in extractions]
    edges: list[tuple[int, int]] = []
    n = len(extractions)
    for i in range(n):
        for j in range(i + 1, n):
            if _jaccard(keyword_sets[i], keyword_sets[j]) >= JACCARD_THRESHOLD:
                edges.append((i, j))
    groups = _union_find_groups(n, edges)
    return [[extractions[i] for i in g] for g in groups]


# ---------- name a small cluster (no LLM) ----------


def _name_small_cluster(extractions: list[dict]) -> str:
    """Pick the most-frequent keyword across the cluster."""
    bag: Counter = Counter()
    for e in extractions:
        for k in _keyword_set(e):
            bag[k] += 1
    if not bag:
        return "unnamed-cluster"
    top = bag.most_common(1)[0][0]
    return top.replace(" ", "-")


# ---------- LLM refinement for large pre-clusters ----------


def _build_refinement_user_prompt(extractions: list[dict]) -> str:
    lines = ["Items to cluster:"]
    for e in extractions:
        a2 = e.get("a2") or {}
        who = a2.get("who") or "?"
        what = a2.get("what") or "?"
        keywords = a2.get("keywords") or []
        lines.append(
            f'- [{e["raw_item_id"]}] WHO: {who} | WHAT: {what} | KEYWORDS: {keywords}'
        )
    lines.append("")
    lines.append("Return JSON only.")
    return "\n".join(lines)


def _refine_large_cluster(
    extractions: list[dict],
    client: LLMClient,
    temperature: float = LLM_TEMPERATURE,
    log_fn: Any = None,
) -> list[Cluster]:
    """Send the pre-cluster to the LLM and parse the response into sub-clusters.

    If the LLM call fails (any exception), falls back to a single cluster spanning all
    inputs — we don't want clustering to break the whole run.
    """
    user = _build_refinement_user_prompt(extractions)
    try:
        resp = client.complete_structured(_CLUSTERING_SYSTEM_PROMPT, user, temperature=temperature)
    except BudgetExceeded:
        raise
    except Exception as exc:
        logger.warning("clustering_llm_failed", error=str(exc))
        if log_fn:
            log_fn(f"CLUSTERING fallback to single cluster (LLM error: {exc})")
        return _single_fallback_cluster(extractions)

    raw_groups = resp.get("clusters") if isinstance(resp, dict) else None
    if not isinstance(raw_groups, list) or not raw_groups:
        logger.warning("clustering_llm_bad_shape", response=resp)
        if log_fn:
            log_fn("CLUSTERING fallback to single cluster (bad LLM shape)")
        return _single_fallback_cluster(extractions)

    by_id = {e["raw_item_id"]: e for e in extractions}
    used_ids: set[str] = set()
    out: list[Cluster] = []
    for grp in raw_groups:
        if not isinstance(grp, dict):
            continue
        ids = [str(x) for x in (grp.get("item_ids") or []) if str(x) in by_id]
        if not ids:
            continue
        name = (grp.get("name") or "").strip() or "unnamed-cluster"
        out.append(Cluster(
            cluster_id=str(uuid.uuid4()),
            name=_safe_kebab(name),
            raw_item_ids=ids,
            extractions=[by_id[i] for i in ids],
        ))
        used_ids.update(ids)

    # Anything the LLM dropped goes into a leftover cluster — never lose items.
    missed = [e for e in extractions if e["raw_item_id"] not in used_ids]
    if missed:
        out.append(Cluster(
            cluster_id=str(uuid.uuid4()),
            name=_name_small_cluster(missed),
            raw_item_ids=[e["raw_item_id"] for e in missed],
            extractions=missed,
        ))

    return out or _single_fallback_cluster(extractions)


def _single_fallback_cluster(extractions: list[dict]) -> list[Cluster]:
    return [Cluster(
        cluster_id=str(uuid.uuid4()),
        name=_name_small_cluster(extractions),
        raw_item_ids=[e["raw_item_id"] for e in extractions],
        extractions=list(extractions),
    )]


def _safe_kebab(name: str) -> str:
    """Lowercase + non-alnum → hyphens + collapse + strip."""
    s = re.sub(r"[^a-zA-Z0-9]+", "-", name.lower()).strip("-")
    return s or "unnamed-cluster"


# ---------- public entrypoint ----------


def cluster_extractions(
    extractions: list[dict],
    refinement_client: LLMClient | None = None,
    refinement_temperature: float = LLM_TEMPERATURE,
    log_fn: Any = None,
) -> list[Cluster]:
    """Partition extractions into clusters.

    Pass `refinement_client=None` to skip the LLM step entirely (useful for tests and
    for environments without configured LLM credentials — falls back to pure Jaccard).
    """
    pre = jaccard_pre_cluster(extractions)
    if log_fn:
        log_fn(f"CLUSTERING pre_groups={len(pre)} (jaccard)")

    final: list[Cluster] = []
    for group in pre:
        if len(group) < LLM_REFINE_MIN_SIZE or refinement_client is None:
            final.append(Cluster(
                cluster_id=str(uuid.uuid4()),
                name=_name_small_cluster(group),
                raw_item_ids=[e["raw_item_id"] for e in group],
                extractions=list(group),
            ))
            continue

        # Big pre-cluster — refine via LLM. Chunk if it exceeds the per-call limit.
        for chunk_start in range(0, len(group), LLM_MAX_ITEMS_PER_CALL):
            chunk = group[chunk_start:chunk_start + LLM_MAX_ITEMS_PER_CALL]
            final.extend(_refine_large_cluster(
                chunk, refinement_client, refinement_temperature, log_fn=log_fn,
            ))

    if log_fn:
        log_fn(f"CLUSTERING final_clusters={len(final)}")
    return final
