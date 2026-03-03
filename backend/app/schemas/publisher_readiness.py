"""
Pydantic schemas for the Publisher Readiness Index API.

Defines request / response contracts consumed by the
``/publisher-readiness`` endpoints.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class ReadinessRecordIn(BaseModel):
    """A single manuscript-readiness observation."""

    coherence_score: Optional[float] = Field(None, ge=0, le=1)
    novelty_score: Optional[float] = Field(None, ge=0, le=1)
    supervision_quality_score: Optional[float] = Field(None, ge=0, le=1)
    revision_density: Optional[float] = Field(None, ge=0)
    citation_consistency: Optional[float] = Field(None, ge=0, le=1)
    stage_completion_ratio: Optional[float] = Field(None, ge=0, le=1)
    acceptance_outcome: Optional[float] = Field(
        None, ge=0, le=100,
        description="Historical acceptance score (training target).",
    )
    researcher_id: Optional[str] = None


class AnalyseRequest(BaseModel):
    """POST /analyse request body."""

    records: List[ReadinessRecordIn] = Field(
        ..., min_length=1,
        description="Manuscript readiness observations (with targets for training).",
    )
    save_model: bool = Field(True, description="Persist model to disk.")


class ScoreRequest(BaseModel):
    """POST /score request body."""

    records: List[ReadinessRecordIn] = Field(
        ..., min_length=1,
        description="Manuscript readiness observations (no target needed).",
    )


class SyntheticRequest(BaseModel):
    """POST /synthetic request body."""

    n: int = Field(200, ge=10, le=10000, description="Number of synthetic records.")
    seed: int = Field(42, description="Random seed for reproducibility.")
    run_analysis: bool = Field(True, description="Immediately analyse after generation.")


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class ReadinessPredictionOut(BaseModel):
    """A single readiness prediction."""

    readiness_score: float
    category: str
    confidence: float
    confidence_low: float
    confidence_high: float
    researcher_id: Optional[str] = None


class RegressionMetricsOut(BaseModel):
    """Model evaluation metrics."""

    r2: float
    mae: float
    rmse: float
    n_train: int
    n_test: int


class TrainingResultOut(BaseModel):
    """Training pipeline result."""

    metrics: RegressionMetricsOut
    feature_importances: Dict[str, float]
    n_samples: int
    n_features: int


class AnalyseResponse(BaseModel):
    """POST /analyse response."""
    model_config = ConfigDict(protected_namespaces=())

    training_result: Optional[TrainingResultOut] = None
    predictions: List[ReadinessPredictionOut]
    feature_importances: Dict[str, float]
    n_samples: int


class ModelStatusResponse(BaseModel):
    """GET /status response."""
    model_config = ConfigDict(protected_namespaces=())

    model_trained: bool
    model_path: str
    artifacts_dir: str
    metadata: Optional[Dict[str, Any]] = None
