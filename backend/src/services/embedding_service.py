"""
Centralised embedding service.

Loads the embedding model once at process startup and reuses it for
every embedding call — for listings (write path) and search queries
(read path) alike. Using the same instance everywhere guarantees
that query and document vectors share the same vector space.

Model: KBLab/sentence-bert-swedish-cased
- Trained specifically on Swedish by the National Library of Sweden
- 768-dimensional embeddings
- Runs locally on CPU; no API calls
"""

from functools import lru_cache

import numpy as np
from sentence_transformers import SentenceTransformer


EMBEDDING_MODEL_NAME = "KBLab/sentence-bert-swedish-cased"
EMBEDDING_DIMENSION = 768


@lru_cache(maxsize=1)
def get_embedding_model() -> SentenceTransformer:
    """Return the singleton embedding model.

    Cached so the model is loaded only once per process.
    First call: ~5-10 seconds (load from disk).
    First-ever call: ~30-60 seconds (downloads ~500MB from HuggingFace).
    Subsequent calls: instant.
    """
    return SentenceTransformer(EMBEDDING_MODEL_NAME)


def embed_text(text: str) -> list[float]:
    """Convert text into a normalised 768-dim vector.

    Used on both write path (saving listing embeddings) and read
    path (search queries). Same function on both sides guarantees
    vectors live in the same space.

    Args:
        text: Any text — listing description, search query, etc.

    Returns:
        A 768-element list of floats, ready to pass to pgvector.
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
    """Embed many texts at once.

    Much faster than calling embed_text in a loop because the model
    processes them in parallel batches.
    """
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
