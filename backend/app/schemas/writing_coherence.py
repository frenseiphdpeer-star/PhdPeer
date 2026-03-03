"""
Pydantic schemas for the Writing Coherence Scoring API.

Defines request / response contracts consumed by the ``/writing-coherence``
endpoints.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class ScoreTextRequest(BaseModel):
    """Score coherence from raw text (optionally pre-segmented)."""

    text: str = Field(
        ...,
        min_length=1,
        description="Full document text to analyse.",
    )
    paragraphs: Optional[List[str]] = Field(
        None,
        description=(
            "Pre-segmented paragraph list.  If omitted the text is "
            "auto-segmented on double-newline boundaries."
        ),
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "text": (
                        "This study examines the effects of climate change on "
                        "biodiversity.\n\nWe collected data from twelve "
                        "monitoring stations over five years.\n\nOur analysis "
                        "reveals a significant decline in species richness."
                    ),
                }
            ]
        }
    )


class ScoreDocumentRequest(BaseModel):
    """Score coherence of an already-uploaded document by ID."""

    document_id: UUID = Field(
        ...,
        description="Primary key of the document in document_artifacts.",
    )


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class CoherenceDetailOut(BaseModel):
    """Detailed consecutive-paragraph similarity metrics."""

    mean_similarity: float = Field(description="Mean cosine similarity (0–1).")
    min_similarity: float = Field(description="Worst transition similarity.")
    max_similarity: float = Field(description="Best transition similarity.")
    std_similarity: float = Field(description="Std-dev of transition sims.")
    transition_similarities: List[float] = Field(
        description="Per-transition cosine similarities (len = n_paragraphs - 1).",
    )


class TopicDriftDetailOut(BaseModel):
    """Detailed topic-drift clustering metrics."""

    optimal_k: int = Field(description="Chosen number of topic clusters.")
    silhouette: float = Field(description="Silhouette score for chosen k.")
    cluster_labels: List[int] = Field(
        description="Cluster assignment per paragraph.",
    )
    n_switches: int = Field(description="Number of abrupt cluster switches.")
    switch_ratio: float = Field(description="Switches / (n_paragraphs - 1).")


class WritingCoherenceOut(BaseModel):
    """Full coherence scoring response."""

    coherence_score: float = Field(
        description="Paragraph-transition coherence (0–100).",
    )
    topic_drift_score: float = Field(
        description="Topical focus score (0–100; higher = less drift).",
    )
    structural_consistency_score: float = Field(
        description="Structural consistency (0–100; penalises abrupt switches).",
    )
    composite_score: float = Field(
        description="Weighted composite of the three scores (0–100).",
    )
    n_paragraphs: int = Field(description="Total paragraphs in input.")
    paragraphs_used: int = Field(
        description="Paragraphs after min-length filtering.",
    )
    coherence_detail: CoherenceDetailOut
    topic_drift_detail: TopicDriftDetailOut


class ScoreResponse(BaseModel):
    """Wrapper for coherence scoring endpoints."""

    success: bool = True
    data: WritingCoherenceOut
