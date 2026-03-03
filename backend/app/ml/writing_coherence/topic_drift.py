"""
Topic-drift detection via KMeans clustering.

Assigns each paragraph embedding to a topic cluster, then analyses the
sequence of cluster labels to detect:

  1. **Topic drift score** – how scattered the topics are (entropy-based).
  2. **Structural consistency score** – penalises abrupt cluster switches
     between consecutive paragraphs.

The optimal *k* (number of topics) is chosen by silhouette score within a
configurable range (default 3–6).
"""

from __future__ import annotations

import logging
import math
from collections import Counter
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

from app.ml.writing_coherence.config import CONFIG

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class TopicDriftResult:
    """Output of the topic-drift / structural-consistency analysis."""

    # 0–100: higher = less drift (more topically focused)
    topic_drift_score: float
    # 0–100: higher = more structurally consistent (fewer abrupt switches)
    structural_consistency_score: float
    # Optimal k chosen by silhouette
    optimal_k: int
    # Silhouette score for the chosen k
    silhouette: float
    # Cluster label per paragraph
    cluster_labels: List[int]
    # Number of abrupt cluster switches
    n_switches: int
    # Ratio of switches to transitions
    switch_ratio: float


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def detect_topic_drift(
    embeddings: np.ndarray,
    *,
    k_min: int = CONFIG.kmeans_k_min,
    k_max: int = CONFIG.kmeans_k_max,
    random_state: int = CONFIG.kmeans_random_state,
    switch_penalty_factor: float = CONFIG.switch_penalty_factor,
    score_scale: float = CONFIG.score_scale,
) -> TopicDriftResult:
    """
    Cluster paragraph embeddings and analyse topic drift.

    Parameters
    ----------
    embeddings : np.ndarray
        Shape ``(n_paragraphs, dim)``.  Must contain ≥ 3 rows (otherwise
        returns perfect scores).
    k_min, k_max : int
        Range of cluster counts to evaluate.
    random_state : int
        Reproducibility seed.
    switch_penalty_factor : float
        Per-switch penalty subtracted from structural consistency (0–1).
    score_scale : float
        Maximum score value (100).

    Returns
    -------
    TopicDriftResult
    """
    n = embeddings.shape[0]

    if n < 3:
        return TopicDriftResult(
            topic_drift_score=score_scale,
            structural_consistency_score=score_scale,
            optimal_k=1,
            silhouette=1.0,
            cluster_labels=[0] * n,
            n_switches=0,
            switch_ratio=0.0,
        )

    # --- Choose optimal k via silhouette ---------------------------------
    best_k, best_score, best_labels = _select_k(
        embeddings, k_min=k_min, k_max=k_max, random_state=random_state,
    )

    # --- Topic drift score (entropy-based + pairwise similarity) ---------
    topic_drift_score = _compute_topic_drift_score(
        embeddings, best_labels, n, score_scale,
    )

    # --- Structural consistency (switch penalty) --------------------------
    n_switches, switch_ratio = _count_switches(best_labels)
    structural_consistency_score = _compute_structural_score(
        switch_ratio, switch_penalty_factor, score_scale,
    )

    return TopicDriftResult(
        topic_drift_score=round(topic_drift_score, 2),
        structural_consistency_score=round(structural_consistency_score, 2),
        optimal_k=best_k,
        silhouette=round(best_score, 4),
        cluster_labels=best_labels.tolist() if isinstance(best_labels, np.ndarray) else list(best_labels),
        n_switches=n_switches,
        switch_ratio=round(switch_ratio, 4),
    )


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _select_k(
    embeddings: np.ndarray,
    *,
    k_min: int,
    k_max: int,
    random_state: int,
) -> Tuple[int, float, np.ndarray]:
    """Sweep k and pick the value with the highest silhouette score."""
    n = embeddings.shape[0]
    # k must be ≥ 2 and < n for silhouette_score to work
    k_min = max(2, k_min)
    k_max = min(k_max, n - 1)

    if k_min > k_max:
        # All paragraphs collapse to one cluster
        labels = np.zeros(n, dtype=int)
        return 1, 0.0, labels

    best_k = k_min
    best_sil = -1.0
    best_labels = None

    for k in range(k_min, k_max + 1):
        km = KMeans(n_clusters=k, random_state=random_state, n_init=10)
        labels = km.fit_predict(embeddings)
        sil = silhouette_score(embeddings, labels)
        if sil > best_sil:
            best_k = k
            best_sil = sil
            best_labels = labels

    return best_k, best_sil, best_labels


def _compute_topic_drift_score(
    embeddings: np.ndarray,
    labels: np.ndarray,
    n: int,
    scale: float,
) -> float:
    """
    Composite topic-drift score blending pairwise similarity with entropy.

    Uses **mean pairwise cosine similarity** as the primary signal (robust
    even for small paragraph counts) and cluster-label entropy as a secondary
    refinement when the clustering is meaningful (silhouette ≥ 0.25).

    Higher score → more focused (less drift).
    """
    # --- Primary signal: mean pairwise cosine similarity ------------------
    # Embeddings are already L2-normalised by ParagraphEmbedder, so
    # cosine similarity = dot product.
    sim_matrix = embeddings @ embeddings.T
    # Extract upper triangle (exclude self-similarity on diagonal)
    triu_indices = np.triu_indices(n, k=1)
    pairwise_sims = sim_matrix[triu_indices]
    mean_sim = float(np.mean(pairwise_sims))     # range roughly [-1, 1]
    # Map to [0, 1]: similarity of 1 → 1.0, similarity of 0 → 0.5
    sim_component = max(0.0, min(1.0, (mean_sim + 1.0) / 2.0))

    # --- Secondary signal: normalised entropy of cluster labels -----------
    counts = Counter(labels.tolist() if isinstance(labels, np.ndarray) else labels)
    k = len(counts)
    if k <= 1:
        entropy_component = 1.0
    else:
        probs = np.array([c / n for c in counts.values()])
        entropy = -float(np.sum(probs * np.log2(probs + 1e-12)))
        max_entropy = math.log2(k)
        normalised = entropy / max_entropy if max_entropy > 0 else 0.0
        entropy_component = 1.0 - normalised

    # --- Blend: similarity dominates (75%), entropy refines (25%) ---------
    blended = 0.75 * sim_component + 0.25 * entropy_component
    return scale * blended


def _count_switches(labels) -> Tuple[int, float]:
    """Count consecutive-cluster switches and their ratio."""
    if isinstance(labels, np.ndarray):
        labels = labels.tolist()
    if len(labels) < 2:
        return 0, 0.0
    switches = sum(1 for i in range(len(labels) - 1) if labels[i] != labels[i + 1])
    ratio = switches / (len(labels) - 1)
    return switches, ratio


def _compute_structural_score(
    switch_ratio: float,
    penalty_factor: float,
    scale: float,
) -> float:
    """
    Higher score = fewer abrupt switches = more structurally consistent.

    ``score = scale * (1 - switch_ratio * (1 + penalty_factor))``
    Clamped to [0, scale].
    """
    raw = 1.0 - switch_ratio * (1.0 + penalty_factor)
    return max(0.0, min(scale, scale * raw))
