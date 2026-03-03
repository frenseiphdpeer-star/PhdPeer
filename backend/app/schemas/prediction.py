"""
Pydantic schemas for the milestone duration prediction API.

Defines request / response contracts consumed by the ``/predictions`` endpoints.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class MilestoneFeatures(BaseModel):
    """
    Feature vector for a single milestone / stage prediction.

    All fields are optional – the model handles missing values via imputation.
    ``prior_delay_patterns`` is a list of booleans (True = that prior milestone
    was delayed); the pipeline derives ``prior_delay_ratio`` internally.
    """

    stage_type: Optional[str] = Field(
        None,
        description="PhD stage category (e.g. 'literature_review', 'writing').",
    )
    discipline: Optional[str] = Field(
        None,
        description="Academic discipline (e.g. 'computer_science', 'biology').",
    )
    milestone_type: Optional[str] = Field(
        None,
        description="Deliverable type (e.g. 'paper', 'thesis_chapter').",
    )
    number_of_prior_milestones: Optional[int] = Field(
        None, ge=0,
        description="Count of milestones completed before this one.",
    )
    supervision_latency_avg: Optional[float] = Field(
        None, ge=0,
        description="Average days between supervision meetings.",
    )
    writing_velocity_score: Optional[float] = Field(
        None, ge=0, le=1,
        description="Normalised writing velocity (0 = stalled, 1 = fast).",
    )
    prior_delay_patterns: Optional[List[bool]] = Field(
        None,
        description="Boolean list – True for each prior milestone that was delayed.",
    )
    opportunity_engagement_score: Optional[float] = Field(
        None, ge=0, le=1,
        description="How actively the student engages with opportunities (0–1).",
    )
    health_score_trajectory: Optional[float] = Field(
        None, ge=0, le=1,
        description="Recent trajectory of journey health score (0–1).",
    )
    revision_density: Optional[float] = Field(
        None, ge=0,
        description="Average number of revisions per deliverable.",
    )
    historical_completion_time: Optional[float] = Field(
        None, ge=0,
        description="Duration (months) of the most recent completed milestone.",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "stage_type": "writing",
                    "discipline": "computer_science",
                    "milestone_type": "thesis_chapter",
                    "number_of_prior_milestones": 5,
                    "supervision_latency_avg": 14.0,
                    "writing_velocity_score": 0.65,
                    "prior_delay_patterns": [False, False, True, False, True],
                    "opportunity_engagement_score": 0.8,
                    "health_score_trajectory": 0.72,
                    "revision_density": 2.1,
                    "historical_completion_time": 4.5,
                }
            ]
        }
    )


class PredictRequest(BaseModel):
    """Batch prediction request – one or more milestone feature vectors."""

    milestones: List[MilestoneFeatures] = Field(
        ..., min_length=1, max_length=100,
        description="Feature vectors for milestones to predict.",
    )
    include_explanations: bool = Field(
        True,
        description="Include SHAP-based feature attributions.",
    )
    top_k: int = Field(
        5, ge=1, le=20,
        description="Number of top SHAP contributors to return.",
    )


class TrainRequest(BaseModel):
    """Request to (re-)train the model with supplied data or synthetic bootstrap."""

    records: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Training records (flat dicts). If omitted, synthetic data is generated.",
    )
    n_synthetic: int = Field(
        500, ge=50, le=10000,
        description="Number of synthetic records to generate (used when records is null).",
    )
    test_size: float = Field(
        0.2, ge=0.0, lt=1.0,
        description="Fraction of data held out for evaluation.",
    )
    version_tag: Optional[str] = Field(
        None,
        description="Optional human-readable model version label.",
    )


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class FeatureAttributionOut(BaseModel):
    """SHAP attribution for one feature."""

    feature_name: str
    feature_value: Any
    shap_value: float
    direction: str = Field(description="'increases' | 'decreases' | 'neutral'")


class PredictionExplanationOut(BaseModel):
    """Full SHAP explanation for one prediction."""

    base_value: float
    attributions: List[FeatureAttributionOut]
    top_contributors: List[FeatureAttributionOut]


class MilestonePredictionOut(BaseModel):
    """Prediction result for a single milestone."""

    predicted_duration_months: float = Field(
        description="Point estimate (months).",
    )
    ci_lower: float = Field(
        description="80 % confidence interval – lower bound (months).",
    )
    ci_upper: float = Field(
        description="80 % confidence interval – upper bound (months).",
    )
    explanation: Optional[PredictionExplanationOut] = Field(
        None,
        description="SHAP-based feature attributions (if requested).",
    )


class PredictResponse(BaseModel):
    """Batch prediction response."""

    success: bool = True
    predictions: List[MilestonePredictionOut]


class EvaluationMetricsOut(BaseModel):
    """Evaluation summary returned after training."""

    mae: float = Field(description="Mean Absolute Error (months).")
    rmse: float = Field(description="Root Mean Squared Error (months).")
    r2: float = Field(description="R² score.")
    n_train: int
    n_test: int


class TrainResponse(BaseModel):
    """Response after model training / re-training."""

    model_config = ConfigDict(protected_namespaces=())

    success: bool = True
    message: str = "Model trained successfully."
    metrics: EvaluationMetricsOut
    model_path: str
    feature_importances: Dict[str, float]


class ModelStatusOut(BaseModel):
    """Current model status and metadata."""

    model_config = ConfigDict(protected_namespaces=())

    model_loaded: bool
    version: Optional[str] = None
    trained_at: Optional[str] = None
    metrics: Optional[EvaluationMetricsOut] = None
    feature_names: Optional[List[str]] = None
