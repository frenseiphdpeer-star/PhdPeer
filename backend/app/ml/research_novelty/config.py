"""
Configuration for the Research Novelty Scoring module.

All tunables are env-overridable so they can be changed per deployment
without touching code.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_BACKEND_ROOT = Path(__file__).resolve().parents[3]  # backend/
NOVELTY_ARTIFACTS_DIR: Path = Path(
    os.getenv("NOVELTY_ARTIFACTS_DIR", str(_BACKEND_ROOT / "ml_artifacts" / "novelty"))
)

# ---------------------------------------------------------------------------
# SciBERT embedding model
# ---------------------------------------------------------------------------
SCIBERT_MODEL_NAME: str = os.getenv(
    "NOVELTY_SCIBERT_MODEL", "allenai/scibert_scivocab_uncased"
)
SCIBERT_MAX_LENGTH: int = int(os.getenv("NOVELTY_SCIBERT_MAX_LEN", "512"))
DEVICE: str = os.getenv("NOVELTY_DEVICE", "cpu")

# ---------------------------------------------------------------------------
# FAISS index
# ---------------------------------------------------------------------------
FAISS_NPROBE: int = int(os.getenv("NOVELTY_FAISS_NPROBE", "16"))
FAISS_INDEX_TYPE: str = os.getenv("NOVELTY_FAISS_INDEX_TYPE", "IVFFlat")
FAISS_NLIST: int = int(os.getenv("NOVELTY_FAISS_NLIST", "100"))

# ---------------------------------------------------------------------------
# TF-IDF
# ---------------------------------------------------------------------------
TFIDF_MAX_FEATURES: int = int(os.getenv("NOVELTY_TFIDF_MAX_FEATURES", "50000"))
TFIDF_NGRAM_MIN: int = int(os.getenv("NOVELTY_TFIDF_NGRAM_MIN", "1"))
TFIDF_NGRAM_MAX: int = int(os.getenv("NOVELTY_TFIDF_NGRAM_MAX", "2"))

# ---------------------------------------------------------------------------
# Scoring weights
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class NoveltyConfig:
    """Tunables for the novelty scoring pipeline."""

    # Component weights for the composite novelty score (must sum to 1.0)
    weight_field_distance: float = float(
        os.getenv("NOVELTY_W_DISTANCE", "0.55")
    )
    weight_terminology: float = float(
        os.getenv("NOVELTY_W_TERMINOLOGY", "0.30")
    )
    weight_citation_novelty: float = float(
        os.getenv("NOVELTY_W_CITATION", "0.15")
    )

    # Score scale (max score)
    score_scale: float = 100.0

    # Distance calibration: distances below this are "not novel"
    min_novel_distance: float = float(
        os.getenv("NOVELTY_MIN_DIST", "0.2")
    )
    # Distances above this are "maximally novel"
    max_novel_distance: float = float(
        os.getenv("NOVELTY_MAX_DIST", "1.2")
    )

    # Number of nearest neighbours for local novelty estimation
    knn_k: int = int(os.getenv("NOVELTY_KNN_K", "10"))

    def validate(self) -> None:
        total = (
            self.weight_field_distance
            + self.weight_terminology
            + self.weight_citation_novelty
        )
        if abs(total - 1.0) > 1e-6:
            raise ValueError(
                f"Novelty weights must sum to 1.0, got {total:.4f}"
            )


CONFIG = NoveltyConfig()
