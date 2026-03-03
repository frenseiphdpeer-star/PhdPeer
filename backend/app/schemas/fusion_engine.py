"""
Pydantic schemas for the Cross-Feature Intelligence Fusion Engine API.

Defines request / response contracts consumed by the
``/fusion`` endpoints.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class SignalObservationIn(BaseModel):
    """A single timestamped observation of one signal."""

    timestamp: str = Field(..., description="ISO-8601 datetime string.")
    signal_name: str = Field(
        ..., description="Signal name (e.g. supervision_latency).",
    )
    value: float = Field(..., description="Numeric observation value.")
    researcher_id: Optional[str] = Field(
        None, description="Researcher ID for multi-researcher datasets.",
    )


class AnalyseRequest(BaseModel):
    """POST /analyse request body."""

    observations: List[SignalObservationIn] = Field(
        ..., min_length=1,
        description="Timestamped signal observations.",
    )
    save_model: bool = Field(
        True,
        description="Whether to persist trained models to disk.",
    )


class SyntheticRequest(BaseModel):
    """POST /synthetic request body."""

    n_researchers: int = Field(
        5, ge=1, le=100,
        description="Number of synthetic researchers.",
    )
    n_weeks: int = Field(
        52, ge=10, le=520,
        description="Number of weeks of data to generate.",
    )
    seed: int = Field(42, description="Random seed for reproducibility.")
    run_analysis: bool = Field(
        True,
        description="Whether to immediately analyse the synthetic data.",
    )


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class TargetMetricsOut(BaseModel):
    """Regression metrics for one target variable."""

    target: str
    r2: float
    mae: float
    rmse: float
    n_train: int
    n_test: int


class FeatureImportanceOut(BaseModel):
    """Single feature importance entry."""

    feature: str
    importance: float
    relative_importance: float
    rank: int


class CorrelationPairOut(BaseModel):
    """A pair of correlated signals."""

    signal_a: str
    signal_b: str
    correlation: float
    abs_correlation: float


class CorrelationMatrixOut(BaseModel):
    """Full correlation matrix."""

    signal_names: List[str]
    matrix: Dict[str, Dict[str, float]]
    strongest_pairs: List[CorrelationPairOut]


class InsightOut(BaseModel):
    """A single generated insight."""

    category: str
    priority: str
    message: str
    evidence: Dict[str, Any] = Field(default_factory=dict)


class TrainingResultOut(BaseModel):
    """Training result for the multi-target model."""
    model_config = ConfigDict(protected_namespaces=())

    target_metrics: List[TargetMetricsOut]
    feature_importances: Dict[str, Dict[str, float]]
    feature_names: List[str]
    n_samples: int
    n_features: int


class PredictionOut(BaseModel):
    """Predicted values for all targets at one time-point."""

    predictions: Dict[str, float]


class AnalyseResponse(BaseModel):
    """POST /analyse response."""
    model_config = ConfigDict(protected_namespaces=())

    correlation: CorrelationMatrixOut
    training_result: Optional[TrainingResultOut] = None
    predictions: Optional[List[PredictionOut]] = None
    insights: List[InsightOut]
    n_observations: int
    n_aligned_periods: int
    n_features: int
    feature_names: List[str]


class ModelStatusResponse(BaseModel):
    """GET /status response."""
    model_config = ConfigDict(protected_namespaces=())

    model_trained: bool
    model_path: str
    artifacts_dir: str
