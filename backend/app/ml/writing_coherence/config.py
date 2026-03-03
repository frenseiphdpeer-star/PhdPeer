"""
Configuration for the Writing Coherence Scoring module.

All tunables are env-overridable so they can be changed per deployment
without touching code.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Embedding model
# ---------------------------------------------------------------------------
EMBEDDING_MODEL_NAME: str = os.getenv(
    "WC_EMBEDDING_MODEL", "all-MiniLM-L6-v2"
)

# Device: "cpu" | "cuda" | "mps"  (auto-detected if "auto")
DEVICE: str = os.getenv("WC_DEVICE", "cpu")


# ---------------------------------------------------------------------------
# Coherence scoring
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class CoherenceConfig:
    """Tunables for the coherence pipeline."""

    # Minimum paragraph length (chars) to include in analysis
    min_paragraph_length: int = int(os.getenv("WC_MIN_PARA_LEN", "40"))

    # KMeans cluster range for topic-drift detection
    kmeans_k_min: int = int(os.getenv("WC_K_MIN", "3"))
    kmeans_k_max: int = int(os.getenv("WC_K_MAX", "6"))
    kmeans_random_state: int = 42

    # Weights for the composite coherence score (must sum to 1.0)
    weight_coherence: float = float(os.getenv("WC_W_COHERENCE", "0.50"))
    weight_topic_drift: float = float(os.getenv("WC_W_TOPIC_DRIFT", "0.30"))
    weight_structural: float = float(os.getenv("WC_W_STRUCTURAL", "0.20"))

    # Abrupt-switch penalty factor (0–1; higher = harsher)
    switch_penalty_factor: float = float(os.getenv("WC_SWITCH_PENALTY", "0.15"))

    # Scale raw cosine similarity (0–1) to a 0–100 score
    score_scale: float = 100.0

    def validate(self) -> None:
        total = self.weight_coherence + self.weight_topic_drift + self.weight_structural
        if abs(total - 1.0) > 1e-6:
            raise ValueError(
                f"Coherence weights must sum to 1.0, got {total:.4f}"
            )


CONFIG = CoherenceConfig()
