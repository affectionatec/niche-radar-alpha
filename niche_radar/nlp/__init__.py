"""NLP extraction pipeline."""

from __future__ import annotations

import uuid
from collections import defaultdict

import structlog

from niche_radar.nlp.preprocessor import clean_text
from niche_radar.storage.repository import (
    get_niche_candidates_with_embeddings,
    get_unprocessed_items,
    link_niche_item,
    upsert_niche_candidate,
)

logger = structlog.get_logger()


def _decode_embedding(value: bytes | None):
    if not value:
        return None
    import numpy as np

    return np.frombuffer(value, dtype=np.float32)


def run_extraction(db, settings, dry_run: bool = False) -> int:
    """Preprocess, extract, cluster, and persist niche candidates."""
    items = get_unprocessed_items(db)
    prepared = []
    for item in items:
        text = clean_text(f"{item.get('title') or ''} {item.get('body') or ''}")
        if text:
            prepared.append((item, text))
    if not prepared:
        logger.info("extraction_skipped", items=0)
        return 0

    from niche_radar.nlp.clusterer import cluster_keyphrases
    from niche_radar.nlp.extractor import KeyBERTExtractor

    extractor = KeyBERTExtractor(settings.keybert_model)
    extracted = extractor.extract([text for _, text in prepared])
    phrase_hits: dict[str, list[dict]] = defaultdict(list)
    for (item, _), phrases in zip(prepared, extracted, strict=False):
        for phrase, score in phrases:
            phrase_hits[phrase].append({"raw_item_id": item["id"], "keyphrase": phrase, "relevance_score": score})
    niches = cluster_keyphrases(list(phrase_hits), settings)
    existing = get_niche_candidates_with_embeddings(db)
    produced = 0

    for niche in niches:
        item_links: dict[str, dict] = {}
        for phrase in niche["members"]:
            for hit in phrase_hits.get(phrase, []):
                best = item_links.get(hit["raw_item_id"])
                if best is None or hit["relevance_score"] > best["relevance_score"]:
                    item_links[hit["raw_item_id"]] = hit
        if not item_links:
            continue

        niche_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, niche["keyword"]))
        keyword = niche["keyword"]
        aliases = list(dict.fromkeys(niche["aliases"]))
        for current in existing:
            embedding = _decode_embedding(current.get("embedding"))
            if embedding is None or embedding.size != niche["embedding"].size:
                continue
            similarity = sum(float(left) * float(right) for left, right in zip(embedding, niche["embedding"], strict=False))
            if similarity <= 0.85:
                continue
            niche_id = current["id"]
            keyword = current["keyword"]
            aliases = list(dict.fromkeys((current.get("aliases") or []) + [keyword] + [niche["keyword"]] + aliases))
            break

        if not dry_run:
            for _ in range(len(item_links)):
                upsert_niche_candidate(db, niche_id, keyword, aliases, niche["embedding"].astype("float32").tobytes())
            for hit in item_links.values():
                link_niche_item(db, niche_id, hit["raw_item_id"], hit["keyphrase"], hit["relevance_score"])
        produced += 1

    logger.info("extraction_finished", items=len(prepared), niches=produced, dry_run=dry_run)
    return produced
