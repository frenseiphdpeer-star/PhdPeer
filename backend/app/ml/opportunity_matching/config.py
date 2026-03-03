"""
Configuration for the Opportunity Matching Engine.

All tunables are env-overridable so they can be changed per deployment
without touching code.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_BACKEND_ROOT = Path(__file__).resolve().parents[3]  # backend/
MATCHING_ARTIFACTS_DIR: Path = Path(
    os.getenv(
        "MATCHING_ARTIFACTS_DIR",
        str(_BACKEND_ROOT / "ml_artifacts" / "opportunity_matching"),
    )
)

MODEL_FILENAME = "opp_match_lgbm.joblib"
FEATURE_STATE_FILENAME = "opp_match_feature_state.joblib"
METADATA_FILENAME = "opp_match_metadata.json"

# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------
EMBEDDING_MODEL_NAME: str = os.getenv("OPP_EMBEDDING_MODEL", "all-MiniLM-L6-v2")
EMBEDDING_DEVICE: str = os.getenv("OPP_EMBEDDING_DEVICE", "cpu")

# ---------------------------------------------------------------------------
# Known stage types and disciplines
# ---------------------------------------------------------------------------
STAGE_TYPES: List[str] = [
    "proposal",
    "literature_review",
    "data_collection",
    "analysis",
    "writing",
    "revision",
    "defence",
]

DISCIPLINES: List[str] = [
    "computer_science",
    "biology",
    "physics",
    "psychology",
    "engineering",
    "mathematics",
    "social_sciences",
    "humanities",
    "medicine",
    "business",
    "other",
]

# ---------------------------------------------------------------------------
# Feature catalogue
# ---------------------------------------------------------------------------

# Scalar numerical features fed into LightGBM
NUMERIC_FEATURES: List[str] = [
    "cosine_similarity",
    "prior_success_rate",
    "prior_application_count",
    "timeline_readiness_score",
    "days_to_deadline",
    "urgency_score",
    "discipline_match",          # 1.0 if exact match, else 0.0
]

# One-hot encoded categorical groups
STAGE_ONEHOT_FEATURES: List[str] = [f"stage_{s}" for s in STAGE_TYPES]
DISCIPLINE_ONEHOT_FEATURES: List[str] = [f"disc_{d}" for d in DISCIPLINES]

ALL_FEATURES: List[str] = (
    NUMERIC_FEATURES + STAGE_ONEHOT_FEATURES + DISCIPLINE_ONEHOT_FEATURES
)

TARGET_COLUMN: str = "accepted"  # binary: 1 = accepted / succeeded, 0 = not


# ---------------------------------------------------------------------------
# LightGBM hyper-parameters
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class LGBMRankParams:
    """LightGBM hyper-parameters for opportunity ranking."""

    n_estimators: int = int(os.getenv("OPP_N_ESTIMATORS", "300"))
    learning_rate: float = float(os.getenv("OPP_LEARNING_RATE", "0.05"))
    max_depth: int = int(os.getenv("OPP_MAX_DEPTH", "5"))
    num_leaves: int = int(os.getenv("OPP_NUM_LEAVES", "31"))
    min_child_samples: int = int(os.getenv("OPP_MIN_CHILD_SAMPLES", "5"))
    subsample: float = float(os.getenv("OPP_SUBSAMPLE", "0.8"))
    colsample_bytree: float = float(os.getenv("OPP_COLSAMPLE_BYTREE", "0.8"))
    reg_alpha: float = float(os.getenv("OPP_REG_ALPHA", "0.1"))
    reg_lambda: float = float(os.getenv("OPP_REG_LAMBDA", "1.0"))
    random_state: int = 42
    n_jobs: int = int(os.getenv("OPP_N_JOBS", "1"))
    verbosity: int = -1

    def to_dict(self) -> dict:
        return {
            "n_estimators": self.n_estimators,
            "learning_rate": self.learning_rate,
            "max_depth": self.max_depth,
            "num_leaves": self.num_leaves,
            "min_child_samples": self.min_child_samples,
            "subsample": self.subsample,
            "colsample_bytree": self.colsample_bytree,
            "reg_alpha": self.reg_alpha,
            "reg_lambda": self.reg_lambda,
            "random_state": self.random_state,
            "n_jobs": self.n_jobs,
            "verbosity": self.verbosity,
        }


HYPERPARAMS = LGBMRankParams()


# ---------------------------------------------------------------------------
# Scoring weights & urgency
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ScoringConfig:
    """Weights for the final match_score composition."""

    weight_similarity: float = float(os.getenv("OPP_W_SIM", "0.40"))
    weight_model: float = float(os.getenv("OPP_W_MODEL", "0.45"))
    weight_urgency: float = float(os.getenv("OPP_W_URGENCY", "0.15"))

    # Urgency curve: deadline within this many days → urgency = 1.0
    urgency_max_days: int = int(os.getenv("OPP_URGENCY_MAX_DAYS", "7"))
    # Deadline farther than this → urgency ≈ 0
    urgency_zero_days: int = int(os.getenv("OPP_URGENCY_ZERO_DAYS", "180"))

    score_scale: float = 100.0

    def validate(self) -> None:
        total = self.weight_similarity + self.weight_model + self.weight_urgency
        if abs(total - 1.0) > 1e-6:
            raise ValueError(
                f"Scoring weights must sum to 1.0, got {total:.4f}"
            )


SCORING = ScoringConfig()
