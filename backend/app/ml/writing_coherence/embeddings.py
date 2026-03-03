"""
Sentence-transformer embedding wrapper.

Provides a **lazy-loaded singleton** so the ~80 MB model is downloaded and
loaded into memory exactly once across the entire application lifetime.

Usage::

    from app.ml.writing_coherence.embeddings import get_embedder
    embedder = get_embedder()
    vectors = embedder.encode(["paragraph one", "paragraph two"])
"""

from __future__ import annotations

import logging
import os
from typing import List, Optional, Union

# Prevent transformers from importing TensorFlow (avoids protobuf conflicts
# in environments where an older TF is installed alongside newer protobuf).
os.environ.setdefault("USE_TF", "0")

import numpy as np

from app.ml.writing_coherence.config import DEVICE, EMBEDDING_MODEL_NAME

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
_model = None


class ParagraphEmbedder:
    """
    Thin wrapper around ``SentenceTransformer`` focused on paragraph encoding.

    Encapsulates model loading, normalisation, and batch encoding so callers
    never import ``sentence_transformers`` directly.
    """

    def __init__(self, model_name: str = EMBEDDING_MODEL_NAME, device: str = DEVICE):
        from sentence_transformers import SentenceTransformer

        logger.info("Loading sentence-transformer model '%s' on device '%s'…", model_name, device)
        self._model = SentenceTransformer(model_name, device=device)
        self._model_name = model_name
        self._dimension = self._model.get_sentence_embedding_dimension()
        logger.info("Model loaded – embedding dim = %d", self._dimension)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def dimension(self) -> int:
        """Embedding vector dimensionality."""
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

        Parameters
        ----------
        texts : str | list[str]
            Input text(s).
        normalize : bool
            L2-normalise vectors (recommended for cosine similarity).
        batch_size : int
            Batch size for encoding.

        Returns
        -------
        np.ndarray  shape ``(n, dim)`` or ``(dim,)`` for a single string.
        """
        single = isinstance(texts, str)
        if single:
            texts = [texts]

        embeddings: np.ndarray = self._model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=False,
            normalize_embeddings=normalize,
        )

        return embeddings[0] if single else embeddings


def get_embedder() -> ParagraphEmbedder:
    """Return the module-level singleton, creating it on first call."""
    global _model
    if _model is None:
        _model = ParagraphEmbedder()
    return _model


def reset_embedder() -> None:
    """Release the cached model (useful in tests)."""
    global _model
    _model = None
