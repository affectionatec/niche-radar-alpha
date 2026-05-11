"""Cluster extracted keyphrases into niche candidates."""

from __future__ import annotations

import numpy as np
from sklearn.cluster import AgglomerativeClustering
from sentence_transformers import SentenceTransformer


def _normalize(vector: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vector)
    return vector if norm == 0 else vector / norm


def _build_cluster(phrases: list[str], embeddings: np.ndarray) -> dict:
    centroid = _normalize(embeddings.mean(axis=0))
    sims = embeddings @ centroid
    keyword_index = int(np.argmax(sims))
    keyword = phrases[keyword_index]
    aliases = [phrase for i, phrase in enumerate(phrases) if i != keyword_index]
    return {
        "keyword": keyword,
        "aliases": list(dict.fromkeys(aliases)),
        "embedding": centroid.astype(np.float32),
        "members": list(dict.fromkeys(phrases)),
    }


def cluster_keyphrases(keyphrases: list[str], settings) -> list[dict]:
    """Group semantically similar keyphrases into niches."""
    phrases = list(dict.fromkeys(phrase.strip().lower() for phrase in keyphrases if phrase))
    if not phrases:
        return []

    model = SentenceTransformer(settings.keybert_model)
    embeddings = model.encode(phrases, normalize_embeddings=True)
    if len(phrases) == 1:
        clusters = [_build_cluster(phrases, np.asarray(embeddings, dtype=np.float32))]
    else:
        labels = AgglomerativeClustering(
            n_clusters=None,
            metric="cosine",
            linkage="average",
            distance_threshold=settings.cluster_distance_threshold,
        ).fit_predict(embeddings)
        clusters = []
        for label in sorted(set(int(value) for value in labels)):
            indices = [i for i, value in enumerate(labels) if int(value) == label]
            cluster_embeddings = np.asarray([embeddings[i] for i in indices], dtype=np.float32)
            cluster_phrases = [phrases[i] for i in indices]
            clusters.append(_build_cluster(cluster_phrases, cluster_embeddings))

    merged: list[dict] = []
    for cluster in sorted(clusters, key=lambda value: len(value["members"]), reverse=True):
        target = next(
            (
                existing
                for existing in merged
                if float(np.dot(existing["embedding"], cluster["embedding"])) > 0.85
            ),
            None,
        )
        if target is None:
            merged.append(cluster)
            continue
        target["aliases"] = [
            phrase
            for phrase in dict.fromkeys(target["aliases"] + cluster["members"])
            if phrase != target["keyword"]
        ]
        target["embedding"] = _normalize(target["embedding"] + cluster["embedding"]).astype(np.float32)
        target["members"] = list(dict.fromkeys(target["members"] + cluster["members"]))
    return merged
