"""
Configuration for the Dropout Risk Prediction module.

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
DROPOUT_ARTIFACTS_DIR: Path = Path(
    os.getenv(
        "DROPOUT_ARTIFACTS_DIR",
        str(_BACKEND_ROOT / "ml_artifacts" / "dropout_risk"),
    )
)

MODEL_FILENAME_LR = "dropout_lr_model.joblib"
MODEL_FILENAME_XGB = "dropout_xgb_model.joblib"
FEATURE_STATE_FILENAME = "dropout_feature_state.joblib"
METADATA_FILENAME = "dropout_metadata.json"

# ---------------------------------------------------------------------------
# Feature catalogue
# ---------------------------------------------------------------------------
RAW_FEATURES: List[str] = [
    "supervision_latency_avg",
    "supervision_gap_max",
    "milestone_delay_ratio",
    "health_score_decline_slope",
    "opportunity_engagement_count",
    "writing_coherence_trend",
    "revision_response_rate",
    "peer_connection_count",
]

# Derived / engineered features appended during feature engineering
DERIVED_FEATURES: List[str] = [
    "supervision_intensity",           # latency_avg * gap_max
    "delay_health_interaction",        # delay_ratio * decline_slope
    "engagement_per_peer",             # engagement_count / peer_count
    "risk_velocity",                   # slope of rolling risk indicators
    "weeks_since_last_supervision",    # derived from gap_max
]

ALL_FEATURES: List[str] = RAW_FEATURES + DERIVED_FEATURES
TARGET_COLUMN: str = "dropout"

# ---------------------------------------------------------------------------
# Risk thresholds
# ---------------------------------------------------------------------------
RISK_THRESHOLD_YELLOW: float = float(
    os.getenv("DROPOUT_THRESHOLD_YELLOW", "0.3")
)
RISK_THRESHOLD_RED: float = float(
    os.getenv("DROPOUT_THRESHOLD_RED", "0.6")
)

# Early-warning horizon (weeks)
EARLY_WARNING_MIN_WEEKS: int = int(os.getenv("DROPOUT_EW_MIN_WEEKS", "8"))
EARLY_WARNING_MAX_WEEKS: int = int(os.getenv("DROPOUT_EW_MAX_WEEKS", "12"))


# ---------------------------------------------------------------------------
# Model hyper-parameters
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class XGBHyperParams:
    """XGBoost hyper-parameters for dropout classification."""

    n_estimators: int = int(os.getenv("DROPOUT_N_ESTIMATORS", "300"))
    learning_rate: float = float(os.getenv("DROPOUT_LEARNING_RATE", "0.05"))
    max_depth: int = int(os.getenv("DROPOUT_MAX_DEPTH", "5"))
    min_child_weight: int = int(os.getenv("DROPOUT_MIN_CHILD_WEIGHT", "5"))
    subsample: float = float(os.getenv("DROPOUT_SUBSAMPLE", "0.8"))
    colsample_bytree: float = float(os.getenv("DROPOUT_COLSAMPLE", "0.8"))
    reg_alpha: float = float(os.getenv("DROPOUT_REG_ALPHA", "0.1"))
    reg_lambda: float = float(os.getenv("DROPOUT_REG_LAMBDA", "1.0"))
    scale_pos_weight: float = float(os.getenv("DROPOUT_SCALE_POS_WEIGHT", "1.0"))
    random_state: int = 42
    n_jobs: int = int(os.getenv("DROPOUT_N_JOBS", "1"))
    eval_metric: str = "logloss"

    def to_dict(self) -> dict:
        return {
            "n_estimators": self.n_estimators,
            "learning_rate": self.learning_rate,
            "max_depth": self.max_depth,
            "min_child_weight": self.min_child_weight,
            "subsample": self.subsample,
            "colsample_bytree": self.colsample_bytree,
            "reg_alpha": self.reg_alpha,
            "reg_lambda": self.reg_lambda,
            "scale_pos_weight": self.scale_pos_weight,
            "random_state": self.random_state,
            "n_jobs": self.n_jobs,
            "eval_metric": self.eval_metric,
        }


@dataclass(frozen=True)
class LRHyperParams:
    """Logistic Regression hyper-parameters (baseline)."""

    C: float = float(os.getenv("DROPOUT_LR_C", "1.0"))
    max_iter: int = int(os.getenv("DROPOUT_LR_MAX_ITER", "1000"))
    solver: str = "lbfgs"
    random_state: int = 42

    def to_dict(self) -> dict:
        return {
            "C": self.C,
            "max_iter": self.max_iter,
            "solver": self.solver,
            "random_state": self.random_state,
        }


HYPERPARAMS_XGB = XGBHyperParams()
HYPERPARAMS_LR = LRHyperParams()
