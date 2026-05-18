"""
Centralised embedding service.

Loads the embedding model once at process startup and reuses it for
every embedding call — for listings (write path) and search queries
(read path) alike.
"""

from functools import lru_cache

import numpy as np
from sentence_transformers import SentenceTransformer


EMBEDDING_MODEL_NAME = "KBLab/sentence-bert-swedish-cased"
EMBEDDING_DIMENSION = 768


@lru_cache(maxsize=1)
def get_embedding_model() -> SentenceTransformer:
    """Return the singleton embedding model."""
    return SentenceTransformer(EMBEDDING_MODEL_NAME)


def embed_text(text: str) -> list[float]:
    """Convert text into a normalised 768-dim vector.

    Used for both write path (saving listing embeddings) and read
    path (search queries). Same function on both paths guarantees
    vectors live in the same space.
    """
    if not text or not text.strip():
        return [0.0] * EMBEDDING_DIMENSION

    model = get_embedding_model()
    vector: np.ndarray = model.encode(
        text,
        normalize_embeddings=True,
    )
    return vector.tolist()


def embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed many texts at once — faster than one-at-a-time."""
    if not texts:
        return []

    model = get_embedding_model()
    vectors: np.ndarray = model.encode(
        texts,
        normalize_embeddings=True,
        batch_size=32,
        show_progress_bar=False,
    )
    return vectors.tolist()
