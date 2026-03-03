"""
Pydantic schemas for the Opportunity Matching API.

Defines request / response contracts consumed by the ``/opportunity-matching``
endpoints.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class OpportunityInput(BaseModel):
    """
    Describes a single researcher ↔ opportunity pair for matching.

    Either provide ``researcher_text`` + ``opportunity_text`` (the API
    will embed them), **or** supply ``cosine_similarity`` directly.
    """

    # ── Text inputs (optional – for embedding) ────────────────────────
    researcher_text: Optional[str] = Field(
        None,
        description=(
            "Research proposal / abstract text. "
            "If provided, embeddings and cosine similarity are computed automatically."
        ),
    )
    opportunity_text: Optional[str] = Field(
        None,
        description="Opportunity description / call-for-proposals text.",
    )

    # ── Pre-computed similarity ───────────────────────────────────────
    cosine_similarity: Optional[float] = Field(
        None, ge=0, le=1,
        description="Pre-computed cosine similarity (overrides text embedding).",
    )

    # ── Categorical ───────────────────────────────────────────────────
    stage_type: Optional[str] = Field(
        None,
        description=(
            "Current PhD stage: proposal, literature_review, data_collection, "
            "analysis, writing, revision, defence."
        ),
    )
    researcher_discipline: Optional[str] = Field(
        None,
        description="Researcher's discipline (e.g. computer_science, biology).",
    )
    opportunity_discipline: Optional[str] = Field(
        None,
        description="Target discipline of the opportunity.",
    )

    # ── Numeric scalars ───────────────────────────────────────────────
    prior_success_rate: Optional[float] = Field(
        None, ge=0, le=1,
        description="Fraction of prior applications that succeeded (0–1).",
    )
    prior_application_count: Optional[int] = Field(
        None, ge=0,
        description="Number of prior applications / submissions.",
    )
    timeline_readiness_score: Optional[float] = Field(
        None, ge=0, le=1,
        description="How ready the researcher is timeline-wise (0–1).",
    )
    days_to_deadline: Optional[float] = Field(
        None, ge=0,
        description="Days remaining until application deadline.",
    )


class MatchRequest(BaseModel):
    """POST /match request body."""

    opportunities: List[OpportunityInput] = Field(
        ..., min_length=1,
        description="One or more opportunities to match against.",
    )


class TrainRecord(BaseModel):
    """A single historical outcome record for training."""

    cosine_similarity: Optional[float] = None
    stage_type: Optional[str] = None
    researcher_discipline: Optional[str] = None
    opportunity_discipline: Optional[str] = None
    prior_success_rate: Optional[float] = None
    prior_application_count: Optional[int] = None
    timeline_readiness_score: Optional[float] = None
    days_to_deadline: Optional[float] = None
    accepted: int = Field(
        ..., ge=0, le=1,
        description="Outcome: 1 = accepted, 0 = not accepted.",
    )


class TrainRequest(BaseModel):
    """POST /train request body."""

    records: List[TrainRecord] = Field(
        ..., min_length=5,
        description="Historical outcome records (min 5).",
    )


class BootstrapRequest(BaseModel):
    """POST /bootstrap request body."""

    n: int = Field(500, ge=50, le=10_000, description="Number of synthetic records.")


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class RecommendationOut(BaseModel):
    """A single preparation recommendation."""

    category: str
    priority: str
    message: str
    rationale: str


class PreparationOut(BaseModel):
    """Full preparation plan."""

    recommendations: List[RecommendationOut]
    readiness_label: str


class MatchResultOut(BaseModel):
    """Result for a single opportunity match."""

    match_score: float = Field(description="Composite match score 0–100.")
    success_probability: float = Field(description="Predicted acceptance probability 0–1.")
    cosine_similarity: float = Field(description="Semantic similarity 0–1.")
    urgency_score: float = Field(description="Time-to-deadline urgency 0–1.")
    preparation_recommendation: PreparationOut


class MatchResponse(BaseModel):
    """POST /match response."""

    results: List[MatchResultOut]


class MetricsOut(BaseModel):
    """Classification metrics for the ranking model."""

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
    """POST /train and POST /bootstrap response."""

    model_config = ConfigDict(protected_namespaces=())

    metrics: MetricsOut
    feature_importances: Dict[str, float]
    n_samples: int
    n_features: int
    model_type: str = "LGBMClassifier"


class ModelStatusOut(BaseModel):
    """GET /status response."""

    model_config = ConfigDict(protected_namespaces=())

    loaded: bool
    metrics: Optional[MetricsOut] = None
    n_samples: Optional[int] = None
    n_features: Optional[int] = None
