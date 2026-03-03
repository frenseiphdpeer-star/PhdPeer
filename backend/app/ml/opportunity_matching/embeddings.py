"""
Embedding layer for the Opportunity Matching Engine.

Re-uses the same sentence-transformers approach as the Writing Coherence
module, but provides a dedicated singleton so the two modules do not
share mutable state.

Usage::

    from app.ml.opportunity_matching.embeddings import get_embedder
    embedder = get_embedder()
    vecs = embedder.encode(["my research proposal text"])
"""

from __future__ import annotations

import logging
import os
from typing import List, Optional, Union

# Prevent transformers from importing TF
os.environ.setdefault("USE_TF", "0")

import numpy as np

from app.ml.opportunity_matching.config import EMBEDDING_DEVICE, EMBEDDING_MODEL_NAME

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
_model: Optional["OpportunityEmbedder"] = None


class OpportunityEmbedder:
    """
    Thin wrapper around ``SentenceTransformer`` for encoding researcher
    proposals and opportunity descriptions into the same vector space.
    """

    def __init__(
        self,
        model_name: str = EMBEDDING_MODEL_NAME,
        device: str = EMBEDDING_DEVICE,
    ):
        from sentence_transformers import SentenceTransformer

        logger.info(
            "Loading opportunity embedder '%s' on device '%s'…",
            model_name,
            device,
        )
        self._model = SentenceTransformer(model_name, device=device)
        self._model_name = model_name
        self._dimension = self._model.get_sentence_embedding_dimension()
        logger.info("Embedder loaded – dim = %d", self._dimension)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_name(self) -> str:
        return self._model_name

    def encode(
        self,
        texts: Union[str, List[str]],
        *,
        normalize: bool = True,
        batch_size: int = 64,
    ) -> np.ndarray:
        """
        Encode one or more texts into dense vectors.

        Returns shape ``(n, dim)`` even for a single text.
        """
        if isinstance(texts, str):
            texts = [texts]

        vecs = self._model.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=normalize,
            show_progress_bar=False,
        )
        return np.asarray(vecs, dtype=np.float32)

    def cosine_similarity(
        self,
        vec_a: np.ndarray,
        vec_b: np.ndarray,
    ) -> float:
        """
        Compute cosine similarity between two vectors.

        If both vectors are L2-normalised (default from ``encode``),
        this is simply the dot product.
        """
        a = vec_a.flatten().astype(np.float64)
        b = vec_b.flatten().astype(np.float64)

        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a < 1e-12 or norm_b < 1e-12:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))


def get_embedder() -> OpportunityEmbedder:
    """Return the module-level singleton (lazy-loaded)."""
    global _model
    if _model is None:
        _model = OpportunityEmbedder()
    return _model
