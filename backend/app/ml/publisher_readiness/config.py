"""
Configuration for the Publisher Readiness Index scoring model.

All tunables are env-overridable so they can be changed per deployment
without touching code.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_BACKEND_ROOT = Path(__file__).resolve().parents[3]  # backend/
READINESS_ARTIFACTS_DIR: Path = Path(
    os.getenv(
        "READINESS_ARTIFACTS_DIR",
        str(_BACKEND_ROOT / "ml_artifacts" / "publisher_readiness"),
    )
)

MODEL_FILENAME = "readiness_lgbm.joblib"
QUANTILE_LOW_FILENAME = "readiness_lgbm_q_low.joblib"
QUANTILE_HIGH_FILENAME = "readiness_lgbm_q_high.joblib"
SCALER_FILENAME = "readiness_scaler.joblib"
FEATURE_STATE_FILENAME = "readiness_feature_state.joblib"
METADATA_FILENAME = "readiness_metadata.json"


# ---------------------------------------------------------------------------
# Feature catalogue
# ---------------------------------------------------------------------------

# The six input signals consumed by the model.
RAW_FEATURES: List[str] = [
    "coherence_score",              # writing coherence 0–1
    "novelty_score",                # research novelty 0–1
    "supervision_quality_score",    # supervisor interaction quality 0–1
    "revision_density",             # revision activity (events / week)
    "citation_consistency",         # citation pattern regularity 0–1
    "stage_completion_ratio",       # PhD progress fraction 0–1
]

# Derived / interaction features appended during feature engineering.
DERIVED_FEATURES: List[str] = [
    "quality_composite",            # coherence × novelty
    "engagement_composite",         # supervision_quality × revision_density
    "progress_quality",             # stage_completion × coherence
    "revision_citation_interact",   # revision_density × citation_consistency
    "overall_mean",                 # mean of all six raw features
    "min_signal",                   # weakest signal (bottleneck detector)
]

ALL_FEATURES: List[str] = RAW_FEATURES + DERIVED_FEATURES
TARGET_COLUMN: str = "acceptance_outcome"


# ---------------------------------------------------------------------------
# Readiness categories
# ---------------------------------------------------------------------------

CATEGORY_THRESHOLDS: List[Tuple[float, str]] = [
    (40.0, "revise"),               # < 40  →  revise
    (70.0, "moderate readiness"),   # 40–70 →  moderate readiness
    (100.1, "submission-ready"),    # > 70  →  submission-ready
]


def categorise(score: float) -> str:
    """Map a 0–100 readiness score to a categorical label."""
    for upper, label in CATEGORY_THRESHOLDS:
        if score < upper:
            return label
    return CATEGORY_THRESHOLDS[-1][1]


# ---------------------------------------------------------------------------
# LightGBM hyper-parameters
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LGBMReadinessParams:
    """LightGBM hyper-parameters for the readiness regression model."""

    n_estimators: int = int(os.getenv("READINESS_N_ESTIMATORS", "300"))
    learning_rate: float = float(os.getenv("READINESS_LR", "0.05"))
    max_depth: int = int(os.getenv("READINESS_MAX_DEPTH", "5"))
    num_leaves: int = int(os.getenv("READINESS_NUM_LEAVES", "31"))
    min_child_samples: int = int(os.getenv("READINESS_MIN_CHILD", "10"))
    subsample: float = float(os.getenv("READINESS_SUBSAMPLE", "0.8"))
    colsample_bytree: float = float(os.getenv("READINESS_COLSAMPLE", "0.8"))
    reg_alpha: float = float(os.getenv("READINESS_REG_ALPHA", "0.1"))
    reg_lambda: float = float(os.getenv("READINESS_REG_LAMBDA", "1.0"))
    random_state: int = 42
    n_jobs: int = int(os.getenv("READINESS_N_JOBS", "1"))

    def to_dict(self) -> Dict[str, object]:
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
            "verbose": -1,
        }


HYPERPARAMS = LGBMReadinessParams()


# ---------------------------------------------------------------------------
# Quantile regression for confidence
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class QuantileConfig:
    """Controls the quantile regression models used for confidence bands."""

    alpha_low: float = float(os.getenv("READINESS_Q_LOW", "0.1"))
    alpha_high: float = float(os.getenv("READINESS_Q_HIGH", "0.9"))


QUANTILE_CFG = QuantileConfig()
