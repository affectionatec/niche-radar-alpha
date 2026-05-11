"""Keyphrase extraction with KeyBERT."""

from __future__ import annotations

import structlog

logger = structlog.get_logger()


class KeyBERTExtractor:
    """Thin wrapper around KeyBERT with project defaults."""

    def __init__(self, model_name: str) -> None:
        from keybert import KeyBERT

        self.model_name = model_name
        self._model = KeyBERT(model=model_name)

    def extract(self, texts: list[str]) -> list[list[tuple[str, float]]]:
        """Extract up to five diverse 1-3 gram keyphrases per text."""
        results: list[list[tuple[str, float]]] = []
        for text in texts:
            if not text:
                results.append([])
                continue
            phrases = self._model.extract_keywords(
                text,
                keyphrase_ngram_range=(1, 3),
                stop_words="english",
                top_n=5,
                use_mmr=True,
                diversity=0.5,
            )
            normalized = [(phrase.strip().lower(), float(score)) for phrase, score in phrases]
            results.append([(phrase, score) for phrase, score in normalized if phrase])
        logger.debug("keyphrases_extracted", texts=len(texts))
        return results
