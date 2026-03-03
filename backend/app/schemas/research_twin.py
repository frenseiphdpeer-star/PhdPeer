"""
Pydantic schemas for the AI Research Twin API.

Defines request / response contracts consumed by the
``/research-twin`` endpoints.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class BehaviourEventIn(BaseModel):
    """A single timestamped behavioural event."""

    timestamp: str = Field(..., description="ISO-8601 datetime string.")
    event_type: str = Field(
        ...,
        description="Event type (writing, revision, opportunity_engagement, submission, supervision).",
    )
    researcher_id: Optional[str] = Field(
        None, description="Researcher ID.",
    )


class AnalyseRequest(BaseModel):
    """POST /analyse request body."""

    events: List[BehaviourEventIn] = Field(
        ..., min_length=1,
        description="Timestamped behavioural events.",
    )
    save_model: bool = Field(
        True,
        description="Whether to persist the trained LSTM model.",
    )


class ResearcherAnalyseRequest(BaseModel):
    """POST /analyse/researcher request body."""

    researcher_id: str = Field(
        ..., description="Target researcher ID.",
    )
    events: List[BehaviourEventIn] = Field(
        ..., min_length=1,
        description="Timestamped behavioural events.",
    )


class SyntheticRequest(BaseModel):
    """POST /synthetic request body."""

    n_researchers: int = Field(
        3, ge=1, le=50,
        description="Number of synthetic researchers.",
    )
    n_days: int = Field(
        30, ge=7, le=365,
        description="Number of days of behaviour to simulate.",
    )
    seed: int = Field(42, description="Random seed for reproducibility.")
    run_analysis: bool = Field(
        True,
        description="Whether to immediately analyse the synthetic data.",
    )


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class TimeWindowOut(BaseModel):
    """A productive or submission time window."""

    start_hour: int
    end_hour: int
    day_of_week: Optional[int] = None
    day_name: str = "any"
    score: float


class ProcrastinationPatternOut(BaseModel):
    """A detected procrastination pattern."""

    pattern_type: str
    description: str
    severity: str
    evidence: Dict[str, Any] = Field(default_factory=dict)


class NudgeOut(BaseModel):
    """A personalised nudge recommendation."""

    category: str
    message: str
    priority: str
    trigger: str


class RecommendationOut(BaseModel):
    """Full recommendation for one researcher."""

    researcher_id: str
    productive_time_window: List[TimeWindowOut]
    procrastination_pattern: List[ProcrastinationPatternOut]
    optimal_submission_window: List[TimeWindowOut]
    personalized_nudge_recommendations: List[NudgeOut]


class TrainingResultOut(BaseModel):
    """LSTM training result."""

    epochs_trained: int
    final_loss: float
    best_loss: float
    n_sequences: int
    n_features: int
    history: List[float]


class EmbeddingOut(BaseModel):
    """User embedding info."""

    researcher_id: str
    vector: List[float]
    norm: float
    dim: int


class EmbeddingAnalysisOut(BaseModel):
    """Aggregated embedding analysis."""

    n_users: int
    embedding_dim: int
    embeddings: List[EmbeddingOut]
    similarity_matrix: List[List[float]]


class AnalyseResponse(BaseModel):
    """POST /analyse response."""
    model_config = ConfigDict(protected_namespaces=())

    training_result: Optional[TrainingResultOut] = None
    recommendations: Dict[str, RecommendationOut]
    embedding_analysis: Optional[EmbeddingAnalysisOut] = None
    n_events: int
    n_researchers: int


class ModelStatusResponse(BaseModel):
    """GET /status response."""
    model_config = ConfigDict(protected_namespaces=())

    model_trained: bool
    model_path: str
    artifacts_dir: str
