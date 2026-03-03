"""
Configuration for Collaboration Network Intelligence.

All tunables are env-overridable so they can be changed per deployment
without touching code.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_BACKEND_ROOT = Path(__file__).resolve().parents[3]  # backend/
NETWORK_ARTIFACTS_DIR: Path = Path(
    os.getenv(
        "NETWORK_ARTIFACTS_DIR",
        str(_BACKEND_ROOT / "ml_artifacts" / "collaboration_network"),
    )
)

SNAPSHOT_FILENAME = "collab_network_snapshot.json"


# ---------------------------------------------------------------------------
# Graph defaults
# ---------------------------------------------------------------------------
DEFAULT_CITATION_WEIGHT: float = float(
    os.getenv("CN_CITATION_WEIGHT", "1.0")
)
DEFAULT_COAUTHOR_WEIGHT: float = float(
    os.getenv("CN_COAUTHOR_WEIGHT", "1.0")
)


# ---------------------------------------------------------------------------
# Metric thresholds
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class MetricsConfig:
    """Thresholds that govern isolation / collaboration scoring."""

    # PageRank below this → low influence flag
    pagerank_low_threshold: float = float(
        os.getenv("CN_PR_LOW", "0.005")
    )
    # Betweenness centrality below this → bridge deficit
    betweenness_low_threshold: float = float(
        os.getenv("CN_BC_LOW", "0.01")
    )
    # Clustering coefficient below this → low local clustering
    clustering_low_threshold: float = float(
        os.getenv("CN_CC_LOW", "0.1")
    )

    # Maximum collaborators to suggest
    max_suggestions: int = int(os.getenv("CN_MAX_SUGGESTIONS", "10"))

    # Gap detection: minimum citation weight to be flagged
    gap_min_citation_weight: float = float(
        os.getenv("CN_GAP_MIN_CIT", "1.0")
    )


METRICS_CONFIG = MetricsConfig()


# ---------------------------------------------------------------------------
# Scoring weights
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ScoringWeights:
    """Weights for the final collaboration_strength_score composition.

    The collaboration_strength_score blends:
      * normalised PageRank     – global influence
      * clustering coefficient  – local cohesion
      * co-author degree ratio  – active collaboration fraction

    The isolation_score blends:
      * inverse co-author ratio  – how few collaborators vs citations
      * (1 − clustering_coeff)   – local sparsity
      * gap_ratio                – fraction of citation links without collab
    """

    # collaboration_strength
    w_pagerank: float = float(os.getenv("CN_W_PR", "0.35"))
    w_clustering: float = float(os.getenv("CN_W_CC", "0.30"))
    w_coauthor_ratio: float = float(os.getenv("CN_W_CA", "0.35"))

    # isolation_score
    w_iso_inv_coauthor: float = float(os.getenv("CN_W_ISO_CA", "0.40"))
    w_iso_sparsity: float = float(os.getenv("CN_W_ISO_SP", "0.30"))
    w_iso_gap: float = float(os.getenv("CN_W_ISO_GAP", "0.30"))

    score_scale: float = 100.0

    def validate(self) -> None:
        cs = self.w_pagerank + self.w_clustering + self.w_coauthor_ratio
        if abs(cs - 1.0) > 1e-6:
            raise ValueError(
                f"Collaboration strength weights must sum to 1.0, got {cs:.4f}"
            )
        iso = self.w_iso_inv_coauthor + self.w_iso_sparsity + self.w_iso_gap
        if abs(iso - 1.0) > 1e-6:
            raise ValueError(
                f"Isolation weights must sum to 1.0, got {iso:.4f}"
            )


WEIGHTS = ScoringWeights()


# ---------------------------------------------------------------------------
# Louvain parameters
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class LouvainParams:
    """Parameters for Louvain community detection."""

    resolution: float = float(os.getenv("CN_LOUVAIN_RES", "1.0"))
    random_state: int = 42


LOUVAIN_PARAMS = LouvainParams()
