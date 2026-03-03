"""
Writing Coherence Scorer – orchestration layer.

Combines:
  1. Paragraph segmentation
  2. Embedding generation
  3. Consecutive-paragraph coherence
  4. Topic-drift detection
  5. Structural consistency

into a single composite score.

This module is **stateless** – it takes text in and returns scores out.
The heavier ``service.py`` layer adds caching, document-DB integration, etc.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np

from app.ml.writing_coherence.coherence import CoherenceResult, compute_coherence
from app.ml.writing_coherence.config import CONFIG, CoherenceConfig
from app.ml.writing_coherence.embeddings import ParagraphEmbedder, get_embedder
from app.ml.writing_coherence.topic_drift import TopicDriftResult, detect_topic_drift

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class WritingCoherenceScore:
    """Composite writing-coherence analysis result."""

    # ── Top-level scores (0–100) ──────────────────────────────────────
    coherence_score: float
    topic_drift_score: float
    structural_consistency_score: float
    composite_score: float          # weighted combination of the three

    # ── Detailed sub-results ──────────────────────────────────────────
    coherence_detail: CoherenceResult
    topic_drift_detail: TopicDriftResult

    # ── Paragraph metadata ────────────────────────────────────────────
    n_paragraphs: int
    paragraphs_used: int            # after length filtering

    def to_dict(self) -> Dict[str, Any]:
        """JSON-serialisable dict."""
        return {
            "coherence_score": self.coherence_score,
            "topic_drift_score": self.topic_drift_score,
            "structural_consistency_score": self.structural_consistency_score,
            "composite_score": self.composite_score,
            "n_paragraphs": self.n_paragraphs,
            "paragraphs_used": self.paragraphs_used,
            "coherence_detail": {
                "mean_similarity": self.coherence_detail.mean_similarity,
                "min_similarity": self.coherence_detail.min_similarity,
                "max_similarity": self.coherence_detail.max_similarity,
                "std_similarity": self.coherence_detail.std_similarity,
                "transition_similarities": self.coherence_detail.transition_similarities,
            },
            "topic_drift_detail": {
                "optimal_k": self.topic_drift_detail.optimal_k,
                "silhouette": self.topic_drift_detail.silhouette,
                "cluster_labels": self.topic_drift_detail.cluster_labels,
                "n_switches": self.topic_drift_detail.n_switches,
                "switch_ratio": self.topic_drift_detail.switch_ratio,
            },
        }


# ---------------------------------------------------------------------------
# Paragraph segmentation
# ---------------------------------------------------------------------------

def segment_paragraphs(
    text: str,
    *,
    min_length: int = CONFIG.min_paragraph_length,
) -> List[str]:
    """
    Split *text* into paragraphs.

    Strategy (in priority order):
      1. Double-newline boundaries (``\\n\\n``).
      2. If that yields only 1 chunk, fall back to single-newline splits.
      3. Filter out paragraphs shorter than *min_length*.
    """
    # Normalise line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Try double-newline first
    chunks = re.split(r"\n\s*\n", text)
    if len(chunks) <= 1:
        # Fallback: single newline
        chunks = text.split("\n")

    # Strip whitespace and filter short chunks
    paragraphs = [c.strip() for c in chunks if c.strip()]
    paragraphs = [p for p in paragraphs if len(p) >= min_length]

    return paragraphs


# ---------------------------------------------------------------------------
# Main scoring function
# ---------------------------------------------------------------------------

def score_text(
    text: str,
    *,
    paragraphs: Optional[List[str]] = None,
    config: Optional[CoherenceConfig] = None,
    embedder: Optional[ParagraphEmbedder] = None,
) -> WritingCoherenceScore:
    """
    Score the writing coherence of *text*.

    Parameters
    ----------
    text : str
        Full document text.
    paragraphs : list[str], optional
        Pre-segmented paragraphs.  If ``None``, ``segment_paragraphs()`` is
        called automatically.
    config : CoherenceConfig, optional
        Override default config tunables.
    embedder : ParagraphEmbedder, optional
        Override the default singleton embedder (useful for testing).

    Returns
    -------
    WritingCoherenceScore
    """
    cfg = config or CONFIG
    cfg.validate()
    emb = embedder or get_embedder()

    # --- 1. Paragraph segmentation ----------------------------------------
    raw_paragraphs = paragraphs or segment_paragraphs(text, min_length=cfg.min_paragraph_length)
    n_raw = len(raw_paragraphs)

    if n_raw == 0:
        # Empty / trivially short document
        return _empty_score(cfg)

    # --- 2. Embed paragraphs -----------------------------------------------
    embeddings = emb.encode(raw_paragraphs, normalize=True)
    if embeddings.ndim == 1:
        embeddings = embeddings.reshape(1, -1)

    n_used = embeddings.shape[0]

    # --- 3. Consecutive-paragraph coherence --------------------------------
    coherence = compute_coherence(embeddings, score_scale=cfg.score_scale)

    # --- 4. Topic drift + structural consistency ---------------------------
    drift = detect_topic_drift(
        embeddings,
        k_min=cfg.kmeans_k_min,
        k_max=cfg.kmeans_k_max,
        random_state=cfg.kmeans_random_state,
        switch_penalty_factor=cfg.switch_penalty_factor,
        score_scale=cfg.score_scale,
    )

    # --- 5. Composite score ------------------------------------------------
    composite = round(
        cfg.weight_coherence * coherence.coherence_score
        + cfg.weight_topic_drift * drift.topic_drift_score
        + cfg.weight_structural * drift.structural_consistency_score,
        2,
    )

    return WritingCoherenceScore(
        coherence_score=coherence.coherence_score,
        topic_drift_score=drift.topic_drift_score,
        structural_consistency_score=drift.structural_consistency_score,
        composite_score=composite,
        coherence_detail=coherence,
        topic_drift_detail=drift,
        n_paragraphs=n_raw,
        paragraphs_used=n_used,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _empty_score(cfg: CoherenceConfig) -> WritingCoherenceScore:
    """Return a zeroed-out score for empty input."""
    coh = CoherenceResult(
        mean_similarity=0.0, min_similarity=0.0, max_similarity=0.0,
        std_similarity=0.0, transition_similarities=[], coherence_score=0.0,
        n_paragraphs=0,
    )
    drift = TopicDriftResult(
        topic_drift_score=0.0, structural_consistency_score=0.0,
        optimal_k=0, silhouette=0.0, cluster_labels=[], n_switches=0,
        switch_ratio=0.0,
    )
    return WritingCoherenceScore(
        coherence_score=0.0, topic_drift_score=0.0,
        structural_consistency_score=0.0, composite_score=0.0,
        coherence_detail=coh, topic_drift_detail=drift,
        n_paragraphs=0, paragraphs_used=0,
    )
