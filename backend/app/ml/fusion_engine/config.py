"""
Configuration for the Cross-Feature Intelligence Fusion Engine.

All tunables are env-overridable so they can be changed per deployment
without touching code.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_BACKEND_ROOT = Path(__file__).resolve().parents[3]  # backend/
FUSION_ARTIFACTS_DIR: Path = Path(
    os.getenv(
        "FUSION_ARTIFACTS_DIR",
        str(_BACKEND_ROOT / "ml_artifacts" / "fusion_engine"),
    )
)

MODEL_FILENAME = "fusion_lgbm_models.joblib"
METADATA_FILENAME = "fusion_metadata.json"


# ---------------------------------------------------------------------------
# Signal catalogue
# ---------------------------------------------------------------------------

# Each signal is a named time-series column that can be ingested.
# The catalogue is the canonical list of recognised signals.

SIGNAL_NAMES: List[str] = [
    "supervision_latency",       # days since last supervisor interaction
    "writing_coherence",         # coherence score 0–1
    "health_score",              # overall health / wellness 0–100
    "opportunity_engagement",    # opportunity match score 0–100
    "network_centrality",        # collaboration network PageRank (normalised)
    "publication_acceptance",    # binary or probability 0–1
]

# Prediction targets
TARGET_NAMES: List[str] = [
    "publication_success",       # next-period publication acceptance
    "milestone_acceleration",    # milestone days ahead/behind schedule
    "dropout_risk",              # dropout probability 0–1
]


# ---------------------------------------------------------------------------
# Temporal alignment
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class TemporalConfig:
    """Controls how raw signals are resampled / aligned."""

    # Resample period for temporal alignment (pandas offset alias)
    resample_period: str = os.getenv("FUSION_RESAMPLE", "W")

    # Aggregation method per period
    aggregation: str = os.getenv("FUSION_AGG", "mean")

    # Forward-fill limit when signals are sparse (periods)
    ffill_limit: int = int(os.getenv("FUSION_FFILL_LIMIT", "4"))


TEMPORAL = TemporalConfig()


# ---------------------------------------------------------------------------
# Lag feature parameters
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class LagConfig:
    """Controls lag-feature creation for cross-signal prediction."""

    # Number of lag periods to create per signal
    lag_periods: List[int] = field(
        default_factory=lambda: [int(x) for x in
                                 os.getenv("FUSION_LAGS", "1,2,4").split(",")]
    )

    # Rolling-window sizes for moving averages
    rolling_windows: List[int] = field(
        default_factory=lambda: [int(x) for x in
                                 os.getenv("FUSION_ROLLS", "3,6").split(",")]
    )

    # Rate-of-change periods
    roc_periods: List[int] = field(
        default_factory=lambda: [int(x) for x in
                                 os.getenv("FUSION_ROC", "1,3").split(",")]
    )


LAGS = LagConfig()


# ---------------------------------------------------------------------------
# LightGBM hyper-parameters (multi-target regression)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class LGBMFusionParams:
    """LightGBM hyper-parameters for each target regressor."""

    n_estimators: int = int(os.getenv("FUSION_N_EST", "200"))
    learning_rate: float = float(os.getenv("FUSION_LR", "0.05"))
    max_depth: int = int(os.getenv("FUSION_MAX_DEPTH", "5"))
    num_leaves: int = int(os.getenv("FUSION_NUM_LEAVES", "31"))
    min_child_samples: int = int(os.getenv("FUSION_MIN_CHILD", "5"))
    subsample: float = float(os.getenv("FUSION_SUBSAMPLE", "0.8"))
    colsample_bytree: float = float(os.getenv("FUSION_COLSAMPLE", "0.8"))
    reg_alpha: float = float(os.getenv("FUSION_REG_ALPHA", "0.1"))
    reg_lambda: float = float(os.getenv("FUSION_REG_LAMBDA", "1.0"))
    random_state: int = 42
    n_jobs: int = int(os.getenv("FUSION_N_JOBS", "1"))
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


HYPERPARAMS = LGBMFusionParams()


# ---------------------------------------------------------------------------
# Insight generation thresholds
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class InsightConfig:
    """Thresholds that govern automated insight generation."""

    # Correlation thresholds
    strong_correlation: float = float(os.getenv("FUSION_STRONG_CORR", "0.6"))
    moderate_correlation: float = float(os.getenv("FUSION_MOD_CORR", "0.3"))

    # Feature importance threshold for "top predictor" flag
    top_importance_threshold: float = float(
        os.getenv("FUSION_TOP_IMP", "0.08")
    )

    # Maximum insights to return
    max_insights: int = int(os.getenv("FUSION_MAX_INSIGHTS", "20"))


INSIGHTS = InsightConfig()
INSIGHT_CFG = INSIGHTS  # alias used by insights / scorer modules
