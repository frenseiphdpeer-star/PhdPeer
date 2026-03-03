"""
Research Novelty Scorer – orchestrates all sub-components.

Takes a manuscript text (and optionally citation references), generates the
SciBERT embedding, queries the FAISS corpus index, computes TF-IDF
terminology uniqueness, and combines everything into a composite
**novelty score** (0–100).
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np

from app.ml.research_novelty.config import CONFIG, NoveltyConfig
from app.ml.research_novelty.corpus_index import CorpusIndex
from app.ml.research_novelty.tfidf import TerminologyScorer, TfidfResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class NoveltyScore:
    """Final output of the novelty-scoring pipeline."""

    # Composite novelty score: 0 (not novel) – 100 (highly novel)
    novelty_score: float
    # Euclidean distance from the field centroid
    field_distance: float
    # Mean distance to K nearest neighbours
    mean_knn_distance: float
    # 0–100 terminology uniqueness index
    terminology_uniqueness_index: float
    # 0–100 citation novelty component (based on out-of-corpus citations)
    citation_novelty: float
    # Sub-component scores (before weighting) for transparency
    distance_component: float
    terminology_component: float
    citation_component: float
    # Additional detail
    top_rare_terms: List[tuple]
    oov_ratio: float
    n_neighbours_used: int
    corpus_size: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------

def _normalise_distance(
    distance: float,
    min_d: float,
    max_d: float,
    scale: float,
) -> float:
    """Map a raw distance to a [0, scale] score via linear interpolation."""
    if max_d <= min_d:
        return scale * 0.5
    clamped = max(min_d, min(distance, max_d))
    ratio = (clamped - min_d) / (max_d - min_d)
    return scale * ratio


def _citation_novelty(
    citations: Optional[List[str]],
    corpus_ids: set,
    scale: float,
) -> float:
    """
    Proportion of cited references that are NOT in the field corpus.

    High proportion → the paper draws on work outside the immediate field
    → novelty signal.
    """
    if not citations:
        return 0.0
    if not corpus_ids:
        return scale  # no corpus to compare against – assume novel
    outside = sum(1 for c in citations if c not in corpus_ids)
    ratio = outside / len(citations)
    return scale * ratio


# ---------------------------------------------------------------------------
# Main scoring function
# ---------------------------------------------------------------------------

def score_manuscript(
    embedding: np.ndarray,
    corpus_index: CorpusIndex,
    tfidf_scorer: TerminologyScorer,
    text: str,
    *,
    citations: Optional[List[str]] = None,
    config: Optional[NoveltyConfig] = None,
) -> NoveltyScore:
    """
    Compute the composite novelty score for a manuscript.

    Parameters
    ----------
    embedding : np.ndarray
        SciBERT embedding of the manuscript, shape ``(dim,)`` or ``(1, dim)``.
    corpus_index : CorpusIndex
        Pre-built FAISS index of field-corpus embeddings.
    tfidf_scorer : TerminologyScorer
        Fitted TF-IDF vectoriser over the corpus.
    text : str
        Full manuscript text (for TF-IDF scoring).
    citations : list[str], optional
        Citation identifiers (DOIs, titles, or keys).
    config : NoveltyConfig, optional
        Override default scoring weights.

    Returns
    -------
    NoveltyScore
    """
    cfg = config or CONFIG

    embedding = embedding.flatten().astype(np.float32)

    # ---- 1. Field-centroid distance -------------------------------------
    field_dist = corpus_index.centroid_distance(embedding)

    # ---- 2. Mean KNN distance -------------------------------------------
    k = min(cfg.knn_k, corpus_index.size)
    mean_knn = corpus_index.mean_knn_distance(embedding, k=k)

    # Use the larger of centroid / mean-knn for a conservative estimate
    representative_dist = max(field_dist, mean_knn ** 0.5)
    distance_score = _normalise_distance(
        representative_dist, cfg.min_novel_distance, cfg.max_novel_distance, cfg.score_scale,
    )

    # ---- 3. Terminology uniqueness ---------------------------------------
    tfidf_result: TfidfResult = tfidf_scorer.score(text, scale=cfg.score_scale)
    terminology_score = tfidf_result.terminology_uniqueness_index

    # ---- 4. Citation novelty ---------------------------------------------
    corpus_ids = set(corpus_index._id_map.values())
    citation_score = _citation_novelty(citations, corpus_ids, cfg.score_scale)

    # ---- 5. Weighted composite -------------------------------------------
    composite = (
        cfg.weight_field_distance * distance_score
        + cfg.weight_terminology * terminology_score
        + cfg.weight_citation_novelty * citation_score
    )
    # Clamp to [0, score_scale]
    composite = max(0.0, min(cfg.score_scale, composite))

    return NoveltyScore(
        novelty_score=round(composite, 2),
        field_distance=round(field_dist, 4),
        mean_knn_distance=round(mean_knn, 4),
        terminology_uniqueness_index=round(terminology_score, 2),
        citation_novelty=round(citation_score, 2),
        distance_component=round(distance_score, 2),
        terminology_component=round(terminology_score, 2),
        citation_component=round(citation_score, 2),
        top_rare_terms=tfidf_result.top_rare_terms,
        oov_ratio=round(tfidf_result.oov_ratio, 4),
        n_neighbours_used=k,
        corpus_size=corpus_index.size,
    )
