"""
ML module configuration.

Centralises hyper-parameters, feature lists, and path constants so they can be
overridden via environment variables without touching code.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_DEFAULT_MODEL_DIR = Path(__file__).resolve().parent.parent.parent / "ml_artifacts"

MODEL_DIR: Path = Path(
    os.getenv("ML_MODEL_DIR", str(_DEFAULT_MODEL_DIR))
)
MODEL_DIR.mkdir(parents=True, exist_ok=True)

MODEL_FILENAME = "milestone_duration_model.joblib"
METADATA_FILENAME = "milestone_duration_metadata.json"

# ---------------------------------------------------------------------------
# Feature catalogue
# ---------------------------------------------------------------------------
CATEGORICAL_FEATURES: List[str] = [
    "stage_type",
    "discipline",
    "milestone_type",
]

NUMERIC_FEATURES: List[str] = [
    "number_of_prior_milestones",
    "supervision_latency_avg",
    "writing_velocity_score",
    "prior_delay_ratio",
    "opportunity_engagement_score",
    "health_score_trajectory",
    "revision_density",
    "historical_completion_time",
]

TARGET_COLUMN = "actual_duration_months"

ALL_FEATURES: List[str] = CATEGORICAL_FEATURES + NUMERIC_FEATURES


# ---------------------------------------------------------------------------
# Hyper-parameters (sensible defaults; override per-environment)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class LGBMHyperParams:
    """LightGBM hyper-parameters for milestone duration regression."""

    n_estimators: int = int(os.getenv("ML_N_ESTIMATORS", "500"))
    learning_rate: float = float(os.getenv("ML_LEARNING_RATE", "0.05"))
    max_depth: int = int(os.getenv("ML_MAX_DEPTH", "6"))
    num_leaves: int = int(os.getenv("ML_NUM_LEAVES", "31"))
    min_child_samples: int = int(os.getenv("ML_MIN_CHILD_SAMPLES", "10"))
    subsample: float = float(os.getenv("ML_SUBSAMPLE", "0.8"))
    colsample_bytree: float = float(os.getenv("ML_COLSAMPLE_BYTREE", "0.8"))
    reg_alpha: float = float(os.getenv("ML_REG_ALPHA", "0.1"))
    reg_lambda: float = float(os.getenv("ML_REG_LAMBDA", "1.0"))
    random_state: int = 42
    n_jobs: int = -1
    verbosity: int = -1

    # Confidence interval quantiles
    ci_lower_quantile: float = 0.1
    ci_upper_quantile: float = 0.9

    def to_dict(self) -> dict:
        """Return a plain dict suitable for ``LGBMRegressor(**params)``."""
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


HYPERPARAMS = LGBMHyperParams()
