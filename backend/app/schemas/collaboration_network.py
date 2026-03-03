"""
Pydantic schemas for the Collaboration Network Intelligence API.

Defines request / response contracts consumed by the
``/collaboration-network`` endpoints.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class CitationEdgeIn(BaseModel):
    """A directed citation: *source* cites *target*."""

    source: str = Field(..., description="Citing researcher ID.")
    target: str = Field(..., description="Cited researcher ID.")
    weight: float = Field(1.0, ge=0, description="Citation strength / count.")


class CoauthorEdgeIn(BaseModel):
    """An undirected co-authorship edge."""

    source: str = Field(..., description="First researcher ID.")
    target: str = Field(..., description="Second researcher ID.")
    weight: float = Field(1.0, ge=0, description="Number of joint papers.")


class AnalyseRequest(BaseModel):
    """POST /analyse request body."""

    citation_edges: List[CitationEdgeIn] = Field(
        ..., min_length=1,
        description="Directed citation edges.",
    )
    coauthor_edges: List[CoauthorEdgeIn] = Field(
        default_factory=list,
        description="Undirected co-authorship edges (may be empty).",
    )
    target_nodes: Optional[List[str]] = Field(
        None,
        description=(
            "If provided, only produce scores for these researcher IDs. "
            "Otherwise all nodes are scored."
        ),
    )


class ResearcherAnalyseRequest(BaseModel):
    """POST /analyse/researcher request body."""

    researcher_id: str = Field(
        ..., description="The researcher to analyse.",
    )
    citation_edges: List[CitationEdgeIn] = Field(
        ..., min_length=1,
        description="Directed citation edges.",
    )
    coauthor_edges: List[CoauthorEdgeIn] = Field(
        default_factory=list,
        description="Undirected co-authorship edges.",
    )


class SyntheticRequest(BaseModel):
    """POST /synthetic request body."""

    n_researchers: int = Field(
        30, ge=5, le=500,
        description="Number of synthetic researchers.",
    )
    seed: int = Field(42, description="Random seed for reproducibility.")


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class NodeMetricsOut(BaseModel):
    """Centrality metrics for one researcher node."""

    pagerank: float
    betweenness_centrality: float
    clustering_coefficient: float
    citation_in_degree: int
    citation_out_degree: int
    coauthor_degree: int


class SuggestedCollaboratorOut(BaseModel):
    """A recommended collaborator."""

    researcher_id: str
    score: float = Field(description="Suggestion strength 0–100.")
    citation_weight: float
    same_community: bool
    reason: str


class NodeScoreOut(BaseModel):
    """Full analysis result for one researcher."""

    researcher_id: str
    collaboration_strength_score: float = Field(
        description="Collaboration quality 0–100."
    )
    isolation_score: float = Field(
        description="Isolation risk 0–100 (higher = more isolated)."
    )
    metrics: NodeMetricsOut
    community_id: int
    is_bridge: bool
    suggested_collaborators: List[SuggestedCollaboratorOut]


class CommunityOut(BaseModel):
    """Louvain community detection result."""

    partition: Dict[str, int]
    n_communities: int
    modularity: float
    community_sizes: Dict[str, int]


class GraphSummaryOut(BaseModel):
    """High-level graph statistics."""

    n_nodes: int
    n_citation_edges: int
    n_coauthor_edges: int
    n_combined_edges: int


class AnalyseResponse(BaseModel):
    """POST /analyse response."""

    graph_summary: GraphSummaryOut
    communities: CommunityOut
    n_gaps: int
    node_scores: Dict[str, NodeScoreOut]


class ResearcherAnalyseResponse(BaseModel):
    """POST /analyse/researcher response."""

    graph_summary: GraphSummaryOut
    communities: CommunityOut
    n_gaps: int
    researcher: NodeScoreOut


class SummaryResponse(BaseModel):
    """GET /summary response."""

    graph_summary: GraphSummaryOut
    communities: CommunityOut
