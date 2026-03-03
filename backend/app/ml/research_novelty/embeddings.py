"""
SciBERT embedding wrapper for research manuscripts.

Provides a **lazy-loaded singleton** so the model is loaded into memory
exactly once.  Uses ``transformers`` ``AutoModel`` + ``AutoTokenizer`` with
mean-pooling over the last hidden state to produce a fixed-length
768-dimensional vector for each input text.
"""

from __future__ import annotations

import logging
import os
from typing import List, Optional, Union

# Prevent transformers from importing TensorFlow (avoids protobuf conflicts
# in environments where an older TF is installed alongside newer protobuf).
os.environ.setdefault("USE_TF", "0")

import numpy as np
import torch
from transformers import AutoModel, AutoTokenizer

from app.ml.research_novelty.config import DEVICE, SCIBERT_MAX_LENGTH, SCIBERT_MODEL_NAME

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
_model_instance: Optional["SciBERTEmbedder"] = None


class SciBERTEmbedder:
    """
    Thin wrapper around ``allenai/scibert_scivocab_uncased`` (or any
    compatible HuggingFace model) for document-level embedding.

    The embedding is the **mean-pool** of the last hidden-state tokens
    (excluding padding), then L2-normalised.
    """

    def __init__(
        self,
        model_name: str = SCIBERT_MODEL_NAME,
        max_length: int = SCIBERT_MAX_LENGTH,
        device: str = DEVICE,
    ):
        logger.info(
            "Loading SciBERT model '%s' on device '%s'…", model_name, device
        )
        self._tokenizer = AutoTokenizer.from_pretrained(model_name)
        self._model = AutoModel.from_pretrained(model_name)
        self._device = device
        self._model.to(device)
        self._model.eval()
        self._max_length = max_length
        self._model_name = model_name
        # Infer dimension from model config
        self._dimension: int = self._model.config.hidden_size
        logger.info("SciBERT loaded – embedding dim = %d", self._dimension)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------
    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_name(self) -> str:
        return self._model_name

    # ------------------------------------------------------------------
    # Encoding
    # ------------------------------------------------------------------
    def encode(
        self,
        texts: Union[str, List[str]],
        *,
        batch_size: int = 32,
        normalise: bool = True,
    ) -> np.ndarray:
        """
        Encode one or more texts into SciBERT embeddings.

        Parameters
        ----------
        texts : str or list[str]
            Input document(s).
        batch_size : int
            Texts are processed in batches to limit memory usage.
        normalise : bool
            If ``True`` (default), output vectors are L2-normalised.

        Returns
        -------
        np.ndarray
            Shape ``(n_texts, dimension)``.  ``float32``.
        """
        if isinstance(texts, str):
            texts = [texts]

        all_embeddings: List[np.ndarray] = []

        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            encoded = self._tokenizer(
                batch,
                padding=True,
                truncation=True,
                max_length=self._max_length,
                return_tensors="pt",
            ).to(self._device)

            with torch.no_grad():
                outputs = self._model(**encoded)

            # Mean-pool over token dimension, respecting attention mask
            attention_mask = encoded["attention_mask"].unsqueeze(-1)
            token_embeddings = outputs.last_hidden_state
            sum_embeddings = (token_embeddings * attention_mask).sum(dim=1)
            count = attention_mask.sum(dim=1).clamp(min=1e-9)
            mean_pooled = sum_embeddings / count

            batch_np = mean_pooled.cpu().numpy().astype(np.float32)

            if normalise:
                norms = np.linalg.norm(batch_np, axis=1, keepdims=True)
                norms = np.where(norms == 0, 1.0, norms)
                batch_np = batch_np / norms

            all_embeddings.append(batch_np)

        return np.vstack(all_embeddings)


# ---------------------------------------------------------------------------
# Singleton access
# ---------------------------------------------------------------------------

def get_embedder(
    model_name: str = SCIBERT_MODEL_NAME,
    max_length: int = SCIBERT_MAX_LENGTH,
    device: str = DEVICE,
) -> SciBERTEmbedder:
    """Return the module-level singleton, creating it on first call."""
    global _model_instance
    if _model_instance is None:
        _model_instance = SciBERTEmbedder(
            model_name=model_name,
            max_length=max_length,
            device=device,
        )
    return _model_instance


def reset_embedder() -> None:
    """Tear down the singleton (useful in tests)."""
    global _model_instance
    _model_instance = None
