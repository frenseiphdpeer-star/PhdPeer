"""
Pydantic schemas for the Dropout Risk Prediction API.

Defines request / response contracts consumed by the ``/dropout-risk``
endpoints.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class StudentSnapshot(BaseModel):
    """
    Feature vector for a single student-snapshot prediction.

    All fields are optional – the model handles missing values via imputation.
    """

    supervision_latency_avg: Optional[float] = Field(
        None, ge=0,
        description="Average days between supervision meetings.",
    )
    supervision_gap_max: Optional[float] = Field(
        None, ge=0,
        description="Maximum gap (days) between consecutive supervisions.",
    )
    milestone_delay_ratio: Optional[float] = Field(
        None, ge=0, le=1,
        description="Fraction of milestones completed late (0–1).",
    )
    health_score_decline_slope: Optional[float] = Field(
        None,
        description="Slope of journey health score over recent weeks (negative = declining).",
    )
    opportunity_engagement_count: Optional[int] = Field(
        None, ge=0,
        description="Number of opportunities engaged with (conferences, workshops, etc.).",
    )
    writing_coherence_trend: Optional[float] = Field(
        None,
        description="Trend in writing coherence scores over recent submissions (-1 to 1).",
    )
    revision_response_rate: Optional[float] = Field(
        None, ge=0, le=1,
        description="Fraction of supervisor revision requests addressed (0–1).",
    )
    peer_connection_count: Optional[int] = Field(
        None, ge=0,
        description="Number of active peer connections / collaborations.",
    )
    health_score_history: Optional[List[float]] = Field(
        None,
        description="Time-series of recent health scores for slope computation.",
    )
    engagement_history: Optional[List[float]] = Field(
        None,
        description="Time-series of recent engagement counts for velocity computation.",
    )
    weeks_since_last_supervision: Optional[float] = Field(
        None, ge=0,
        description="Weeks since the last supervision session.",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "supervision_latency_avg": 14.5,
                    "supervision_gap_max": 28.0,
                    "milestone_delay_ratio": 0.4,
                    "health_score_decline_slope": -0.12,
                    "opportunity_engagement_count": 3,
                    "writing_coherence_trend": -0.2,
                    "revision_response_rate": 0.65,
                    "peer_connection_count": 2,
                }
            ]
        }
    )


class PredictRequest(BaseModel):
    """Predict dropout risk for one or more student snapshots."""

    students: List[StudentSnapshot] = Field(
        ..., min_length=1,
        description="One or more student snapshots to evaluate.",
    )
    model: str = Field(
        "xgboost",
        description='Model to use: "xgboost" (default) or "logistic_regression".',
    )


class ExplainRequest(BaseModel):
    """Predict dropout risk with SHAP explanations."""

    students: List[StudentSnapshot] = Field(
        ..., min_length=1,
        description="Student snapshots to evaluate and explain.",
    )
    model: str = Field("xgboost")
    top_n: int = Field(
        5, ge=1, le=13,
        description="Number of top risk factors to return per student.",
    )


class TrainRequest(BaseModel):
    """Train dropout models on provided labelled data."""

    records: List[Dict[str, Any]] = Field(
        ..., min_length=10,
        description="Labelled training records (must include 'dropout' key).",
    )


class BootstrapRequest(BaseModel):
    """Bootstrap training on synthetic data."""

    n: int = Field(
        500, ge=50, le=50000,
        description="Number of synthetic samples to generate.",
    )


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class RiskFactorOut(BaseModel):
    """A single SHAP risk-factor attribution."""

    feature_name: str
    feature_value: Any = None
    shap_value: float
    direction: str


class PredictionOut(BaseModel):
    """Single-student dropout prediction."""

    dropout_probability: float = Field(..., ge=0, le=1)
    risk_category: str = Field(
        ..., description='"green", "yellow", or "red".',
    )
    model_used: str


class ExplanationOut(BaseModel):
    """Single-student dropout prediction with SHAP explanation."""

    base_probability: float
    predicted_probability: float = Field(..., ge=0, le=1)
    risk_category: str
    top_risk_factors: List[RiskFactorOut]


class PredictResponse(BaseModel):
    """Envelope for prediction results."""

    status: str = "ok"
    predictions: List[PredictionOut]


class ExplainResponse(BaseModel):
    """Envelope for explained prediction results."""

    status: str = "ok"
    explanations: List[ExplanationOut]


class ClassificationMetricsOut(BaseModel):
    """Evaluation metrics for a classifier."""

    auc_roc: float
    auc_pr: float
    precision: float
    recall: float
    f1: float
    n_train: int
    n_test: int
    pos_rate_train: float
    pos_rate_test: float


class TrainResponse(BaseModel):
    """Response after training dropout models."""

    status: str = "ok"
    lr_metrics: ClassificationMetricsOut
    xgb_metrics: ClassificationMetricsOut
    feature_importances: Dict[str, float]
    n_samples: int
    n_features: int

    model_config = ConfigDict(protected_namespaces=())


class ModelStatusOut(BaseModel):
    """Metadata about the current trained model."""

    loaded: bool
    lr_metrics: Optional[ClassificationMetricsOut] = None
    xgb_metrics: Optional[ClassificationMetricsOut] = None
    n_samples: Optional[int] = None
    n_features: Optional[int] = None

    model_config = ConfigDict(protected_namespaces=())
