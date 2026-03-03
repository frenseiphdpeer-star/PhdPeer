"""
Scorer – orchestration layer for Collaboration Network Intelligence.

Combines graph construction, centrality metrics, Louvain community
detection, network-gap analysis, and scoring into a single entry-point.

Produces per-node:
  * ``collaboration_strength_score`` (0–100)
  * ``isolation_score``              (0–100)
  * ``suggested_collaborators``      (ranked list)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from app.ml.collaboration_network.communities import (
    CommunityResult,
    detect_communities,
    find_bridge_nodes,
)
from app.ml.collaboration_network.config import METRICS_CONFIG, WEIGHTS, ScoringWeights
from app.ml.collaboration_network.gaps import (
    NetworkGap,
    SuggestedCollaborator,
    find_gaps,
    rank_suggestions,
)
from app.ml.collaboration_network.graph import (
    CitationEdge,
    CoauthorEdge,
    CollaborationGraph,
    build_graph,
)
from app.ml.collaboration_network.metrics import NodeMetrics, compute_metrics

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class NodeScore:
    """Full analysis result for one researcher node."""

    researcher_id: str
    collaboration_strength_score: float    # 0–100
    isolation_score: float                 # 0–100
    metrics: NodeMetrics
    community_id: int
    is_bridge: bool
    suggested_collaborators: List[SuggestedCollaborator]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "researcher_id": self.researcher_id,
            "collaboration_strength_score": round(self.collaboration_strength_score, 2),
            "isolation_score": round(self.isolation_score, 2),
            "metrics": self.metrics.to_dict(),
            "community_id": self.community_id,
            "is_bridge": self.is_bridge,
            "suggested_collaborators": [
                s.to_dict() for s in self.suggested_collaborators
            ],
        }


@dataclass
class NetworkAnalysis:
    """Full analysis result for the entire network."""

    graph_summary: Dict[str, Any]
    community_result: CommunityResult
    node_scores: Dict[str, NodeScore]
    n_gaps: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "graph_summary": self.graph_summary,
            "communities": self.community_result.to_dict(),
            "n_gaps": self.n_gaps,
            "node_scores": {
                k: v.to_dict() for k, v in self.node_scores.items()
            },
        }


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------

def _normalise_pagerank(
    pr: float,
    all_pr: List[float],
) -> float:
    """Normalise PageRank to [0, 1] relative to the network max."""
    mx = max(all_pr) if all_pr else 1.0
    if mx <= 0:
        return 0.0
    return min(pr / mx, 1.0)


def _compute_collaboration_strength(
    normalised_pr: float,
    clustering_coeff: float,
    coauthor_ratio: float,
    weights: ScoringWeights,
) -> float:
    """Weighted blend → 0–100."""
    raw = (
        weights.w_pagerank * normalised_pr
        + weights.w_clustering * clustering_coeff
        + weights.w_coauthor_ratio * coauthor_ratio
    )
    return float(np.clip(raw * weights.score_scale, 0, 100))


def _compute_isolation_score(
    inv_coauthor_ratio: float,
    sparsity: float,
    gap_ratio: float,
    weights: ScoringWeights,
) -> float:
    """Weighted blend → 0–100.  Higher = more isolated."""
    raw = (
        weights.w_iso_inv_coauthor * inv_coauthor_ratio
        + weights.w_iso_sparsity * sparsity
        + weights.w_iso_gap * gap_ratio
    )
    return float(np.clip(raw * weights.score_scale, 0, 100))


# ---------------------------------------------------------------------------
# Main scoring entry-point
# ---------------------------------------------------------------------------

def analyse_network(
    citation_edges: Sequence[CitationEdge],
    coauthor_edges: Sequence[CoauthorEdge],
    *,
    target_nodes: Sequence[str] | None = None,
    weights: ScoringWeights | None = None,
) -> NetworkAnalysis:
    """
    Full pipeline: build graph → metrics → communities → gaps → scores.

    Parameters
    ----------
    citation_edges : sequence of CitationEdge
    coauthor_edges : sequence of CoauthorEdge
    target_nodes : sequence of str, optional
        If given, only produce scores & suggestions for these nodes.
        Otherwise score all nodes.
    weights : ScoringWeights, optional
        Override default scoring weights.

    Returns
    -------
    NetworkAnalysis
    """
    w = weights or WEIGHTS

    # 1. Build graph
    graph = build_graph(citation_edges, coauthor_edges)

    # 2. Compute metrics
    node_metrics = compute_metrics(graph)

    # 3. Detect communities
    comm_result = detect_communities(graph)

    # 4. Find gaps
    gaps = find_gaps(graph, comm_result)

    # 5. Find bridge nodes
    bridges = find_bridge_nodes(graph, comm_result)

    # 6. Score each node
    targets = list(target_nodes) if target_nodes else list(graph.nodes)
    all_pr = [m.pagerank for m in node_metrics.values()]

    node_scores: Dict[str, NodeScore] = {}
    for node in targets:
        m = node_metrics.get(node)
        if m is None:
            continue

        norm_pr = _normalise_pagerank(m.pagerank, all_pr)

        # co-author ratio: fraction of citation neighbours who are co-authors
        cit_neighbours = set(graph.citation_graph.predecessors(node)) | set(
            graph.citation_graph.successors(node)
        ) if node in graph.citation_graph else set()
        coauth_neighbours = set(
            graph.coauthor_graph.neighbors(node)
        ) if node in graph.coauthor_graph else set()

        if cit_neighbours:
            coauthor_ratio = len(cit_neighbours & coauth_neighbours) / len(cit_neighbours)
        else:
            coauthor_ratio = 1.0 if coauth_neighbours else 0.0

        collab_strength = _compute_collaboration_strength(
            norm_pr, m.clustering_coefficient, coauthor_ratio, w,
        )

        # Isolation signals
        inv_coauth = 1.0 - coauthor_ratio
        sparsity = 1.0 - m.clustering_coefficient

        # gap ratio: fraction of citation links that are gaps for this node
        node_gap_count = sum(
            1 for g in gaps if g.source == node or g.target == node
        )
        total_cit = len(cit_neighbours)
        gap_ratio = node_gap_count / max(total_cit, 1)

        isolation = _compute_isolation_score(
            inv_coauth, sparsity, gap_ratio, w,
        )

        # Suggestions
        suggestions = rank_suggestions(
            node, graph, node_metrics, comm_result, gaps,
        )

        node_scores[node] = NodeScore(
            researcher_id=node,
            collaboration_strength_score=collab_strength,
            isolation_score=isolation,
            metrics=m,
            community_id=comm_result.partition.get(node, -1),
            is_bridge=node in bridges,
            suggested_collaborators=suggestions,
        )

    return NetworkAnalysis(
        graph_summary=graph.summary(),
        community_result=comm_result,
        node_scores=node_scores,
        n_gaps=len(gaps),
    )
