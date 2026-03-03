"""
Pydantic schemas for the Research Novelty Scoring API.

Defines request / response contracts consumed by the ``/research-novelty``
endpoints.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class ScoreTextRequest(BaseModel):
    """Score novelty of raw manuscript text against the field corpus."""

    text: str = Field(
        ...,
        min_length=1,
        description="Full manuscript text to analyse.",
    )
    citations: Optional[List[str]] = Field(
        None,
        description=(
            "List of citation identifiers (DOIs, titles, or keys).  "
            "Used for the citation-novelty component."
        ),
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "text": (
                        "We introduce a novel graph-attention network for "
                        "molecular property prediction that outperforms "
                        "message-passing neural networks on QM9."
                    ),
                    "citations": ["10.1234/example.doi.1", "10.5678/example.doi.2"],
                }
            ]
        }
    )


class ScoreDocumentRequest(BaseModel):
    """Score novelty of an already-uploaded document by ID."""

    document_id: UUID = Field(
        ..., description="UUID of the uploaded DocumentArtifact."
    )
    citations: Optional[List[str]] = Field(
        None,
        description="Citation identifiers for citation-novelty scoring.",
    )


class BuildCorpusRequest(BaseModel):
    """Build / replace the FAISS field-corpus index."""

    texts: List[str] = Field(
        ...,
        min_length=1,
        description="One document per element – the field corpus.",
    )
    ids: Optional[List[str]] = Field(
        None,
        description="Paper identifiers (DOIs, keys) matching *texts*.",
    )


class BuildDemoCorpusRequest(BaseModel):
    """Generate a synthetic demo corpus and build the index."""

    n: int = Field(
        50,
        ge=5,
        le=10000,
        description="Number of synthetic papers to generate.",
    )


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class RareTermOut(BaseModel):
    """A single rare term + its IDF weight."""
    term: str
    idf: float


class NoveltyScoreOut(BaseModel):
    """Full novelty-scoring result."""

    novelty_score: float = Field(
        ..., ge=0, le=100,
        description="Composite novelty score (0–100).",
    )
    field_distance: float = Field(
        ..., description="Euclidean distance from the field centroid.",
    )
    mean_knn_distance: float = Field(
        ..., description="Mean L2 distance to K nearest neighbours.",
    )
    terminology_uniqueness_index: float = Field(
        ..., ge=0, le=100,
        description="TF-IDF terminology uniqueness index (0–100).",
    )
    citation_novelty: float = Field(
        ..., ge=0, le=100,
        description="Citation novelty component (0–100).",
    )
    distance_component: float = Field(
        ..., description="Distance sub-score before weighting.",
    )
    terminology_component: float = Field(
        ..., description="Terminology sub-score before weighting.",
    )
    citation_component: float = Field(
        ..., description="Citation sub-score before weighting.",
    )
    top_rare_terms: List[RareTermOut] = Field(
        default_factory=list,
        description="Top rare terms by IDF found in the manuscript.",
    )
    oov_ratio: float = Field(
        ..., description="Fraction of query terms absent from corpus vocab.",
    )
    n_neighbours_used: int
    corpus_size: int


class ScoreResponse(BaseModel):
    """Envelope for a scoring result."""
    status: str = "ok"
    data: NoveltyScoreOut


class CorpusStatusOut(BaseModel):
    """Metadata about the current corpus index."""

    loaded: bool
    corpus_size: int
    dimension: int
    index_type: str

    model_config = ConfigDict(protected_namespaces=())


class BuildCorpusResponse(BaseModel):
    """Response after building / rebuilding the corpus index."""

    status: str = "ok"
    corpus_size: int
    dimension: int
    index_type: str

    model_config = ConfigDict(protected_namespaces=())
