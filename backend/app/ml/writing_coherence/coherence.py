"""
Paragraph-level coherence scoring via cosine similarity.

Computes pairwise cosine similarity between consecutive paragraph embeddings
and derives a coherence score (0–100).  Also produces a per-transition
similarity vector for fine-grained analysis.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class CoherenceResult:
    """Output of the consecutive-paragraph coherence analysis."""

    # Mean cosine similarity across all consecutive pairs (0–1)
    mean_similarity: float
    # Min cosine similarity (worst transition)
    min_similarity: float
    # Max cosine similarity (best transition)
    max_similarity: float
    # Standard deviation of transition similarities
    std_similarity: float
    # Per-transition similarity (len = n_paragraphs - 1)
    transition_similarities: List[float]
    # Scaled 0–100 score
    coherence_score: float
    # Number of paragraphs analysed
    n_paragraphs: int


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def compute_coherence(
    embeddings: np.ndarray,
    *,
    score_scale: float = 100.0,
) -> CoherenceResult:
    """
    Compute coherence from a matrix of paragraph embeddings.

    Parameters
    ----------
    embeddings : np.ndarray
        Shape ``(n_paragraphs, dim)``.  Must contain ≥ 2 rows.
    score_scale : float
        Maximum score (default 100).

    Returns
    -------
    CoherenceResult
    """
    n = embeddings.shape[0]

    if n < 2:
        # Single paragraph – perfect coherence by definition
        return CoherenceResult(
            mean_similarity=1.0,
            min_similarity=1.0,
            max_similarity=1.0,
            std_similarity=0.0,
            transition_similarities=[],
            coherence_score=score_scale,
            n_paragraphs=n,
        )

    # Cosine similarity between consecutive paragraphs
    # Embeddings are already L2-normalised → dot product = cosine sim
    sims: List[float] = []
    for i in range(n - 1):
        sim = float(np.dot(embeddings[i], embeddings[i + 1]))
        # Clamp to [0, 1] (negative cosine is rare but possible)
        sims.append(max(0.0, min(1.0, sim)))

    arr = np.array(sims)
    mean_sim = float(arr.mean())
    min_sim = float(arr.min())
    max_sim = float(arr.max())
    std_sim = float(arr.std())

    coherence_score = round(mean_sim * score_scale, 2)

    return CoherenceResult(
        mean_similarity=round(mean_sim, 4),
        min_similarity=round(min_sim, 4),
        max_similarity=round(max_sim, 4),
        std_similarity=round(std_sim, 4),
        transition_similarities=[round(s, 4) for s in sims],
        coherence_score=coherence_score,
        n_paragraphs=n,
    )
