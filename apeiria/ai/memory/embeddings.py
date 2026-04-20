"""Local embedding helpers for knowledge-memory recall."""

from __future__ import annotations

import math

EMBEDDING_MODEL_NAME = "local_bigrams_v1"
EMBEDDING_DIMENSION = 256
NGRAM_SIZE = 2


def embed_text(text: str) -> list[float]:
    """Build a deterministic lightweight embedding from normalized text."""

    normalized = text.strip().lower()
    vector = [0.0] * EMBEDDING_DIMENSION
    if not normalized:
        return vector

    tokens = {token.strip() for token in normalized.split() if token.strip()}
    if not tokens:
        tokens.add(normalized)
    if len(normalized) >= NGRAM_SIZE:
        tokens.update(
            normalized[index : index + NGRAM_SIZE]
            for index in range(len(normalized) - NGRAM_SIZE + 1)
            if normalized[index : index + NGRAM_SIZE].strip()
        )

    for token in tokens:
        vector[hash(token) % EMBEDDING_DIMENSION] += 1.0

    return _normalize(vector)


def cosine_similarity(left: list[float], right: list[float]) -> float:
    """Return cosine similarity for two already-normalized vectors."""

    if len(left) != len(right):
        return 0.0
    return sum(lv * rv for lv, rv in zip(left, right, strict=False))


def _normalize(vector: list[float]) -> list[float]:
    magnitude = math.sqrt(sum(value * value for value in vector))
    if magnitude <= 0:
        return vector
    return [value / magnitude for value in vector]
