"""
Network-gap identification for Collaboration Network Intelligence.

A *gap* is a pair (A, B) where A cites B (or vice-versa) at significant
weight but they have **no** co-authorship edge.  These are high-value
collaboration opportunities: intellectual engagement already exists but
formal collaboration has not yet materialised.

Provides:
  * ``find_gaps()``              – enumerate citation-only edges
  * ``rank_suggestions()``       – rank gap targets by citation weight,
                                   PageRank, and community proximity
  * ``SuggestedCollaborator``    – result container per suggestion
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np

from app.ml.collaboration_network.communities import CommunityResult
from app.ml.collaboration_network.config import METRICS_CONFIG, MetricsConfig
from app.ml.collaboration_network.graph import CollaborationGraph
from app.ml.collaboration_network.metrics import NodeMetrics

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class NetworkGap:
    """A citation-only edge that represents a collaboration gap."""

    source: str
    target: str
    citation_weight: float
    same_community: bool

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "target": self.target,
            "citation_weight": self.citation_weight,
            "same_community": self.same_community,
        }


@dataclass(frozen=True)
class SuggestedCollaborator:
    """
    A recommended collaborator for a target researcher.

    Fields
    ------
    researcher_id : str
        The suggested collaborator's ID.
    score : float
        Recommendation strength (0–100).
    citation_weight : float
        Total citation weight between the pair.
    same_community : bool
        Whether both are in the same Louvain community.
    reason : str
        Human-readable explanation.
    """

    researcher_id: str
    score: float
    citation_weight: float
    same_community: bool
    reason: str

    def to_dict(self) -> dict:
        return {
            "researcher_id": self.researcher_id,
            "score": round(self.score, 2),
            "citation_weight": self.citation_weight,
            "same_community": self.same_community,
            "reason": self.reason,
        }


# ---------------------------------------------------------------------------
# Gap detection
# ---------------------------------------------------------------------------

def find_gaps(
    graph: CollaborationGraph,
    community_result: CommunityResult,
    *,
    min_citation_weight: float | None = None,
) -> List[NetworkGap]:
    """
    Find all citation edges with no corresponding co-authorship link.

    Parameters
    ----------
    graph : CollaborationGraph
    community_result : CommunityResult
        Used to label same_community.
    min_citation_weight : float, optional
        Minimum citation weight to be flagged (default from config).

    Returns
    -------
    list[NetworkGap]
        Sorted by citation_weight descending.
    """
    min_w = min_citation_weight if min_citation_weight is not None else METRICS_CONFIG.gap_min_citation_weight
    partition = community_result.partition

    gaps: List[NetworkGap] = []
    for u, v, d in graph.citation_graph.edges(data=True):
        w = d.get("weight", 1.0)
        if w < min_w:
            continue
        # Check if there is NO co-authorship link
        if not graph.coauthor_graph.has_edge(u, v):
            same_comm = partition.get(u) == partition.get(v) and partition.get(u) is not None
            gaps.append(NetworkGap(
                source=u,
                target=v,
                citation_weight=w,
                same_community=same_comm,
            ))

    gaps.sort(key=lambda g: g.citation_weight, reverse=True)
    logger.info("Found %d network gaps (citation-only edges)", len(gaps))
    return gaps


# ---------------------------------------------------------------------------
# Suggestion ranking
# ---------------------------------------------------------------------------

def rank_suggestions(
    target_node: str,
    graph: CollaborationGraph,
    node_metrics: Dict[str, NodeMetrics],
    community_result: CommunityResult,
    gaps: List[NetworkGap],
    *,
    max_suggestions: int | None = None,
) -> List[SuggestedCollaborator]:
    """
    Rank suggested collaborators for *target_node* from network gaps.

    Ranking signal = citation_weight × (1 + target's PageRank) ×
                     (1.5 if same community, else 1.0)

    Parameters
    ----------
    target_node : str
        The researcher seeking collaborator suggestions.
    max_suggestions : int, optional
        Cap on number of suggestions (default from config).

    Returns
    -------
    list[SuggestedCollaborator]
        Sorted by score descending.
    """
    max_k = max_suggestions if max_suggestions is not None else METRICS_CONFIG.max_suggestions
    partition = community_result.partition
    target_comm = partition.get(target_node)

    # Collect candidate nodes from gaps involving target
    candidates: Dict[str, Dict[str, Any]] = {}
    for gap in gaps:
        other: Optional[str] = None
        if gap.source == target_node:
            other = gap.target
        elif gap.target == target_node:
            other = gap.source
        if other is None:
            continue
        if other in candidates:
            candidates[other]["citation_weight"] += gap.citation_weight
        else:
            candidates[other] = {
                "citation_weight": gap.citation_weight,
                "same_community": gap.same_community,
            }

    if not candidates:
        return []

    # Score candidates
    suggestions: List[SuggestedCollaborator] = []
    for cand_id, info in candidates.items():
        cand_metrics = node_metrics.get(cand_id)
        cand_pr = cand_metrics.pagerank if cand_metrics else 0.0

        cw = info["citation_weight"]
        same_comm = info["same_community"]
        comm_bonus = 1.5 if same_comm else 1.0

        raw_score = cw * (1.0 + cand_pr * 100) * comm_bonus
        # Normalise to 0-100 via sigmoid-like capping
        score = float(np.clip(raw_score * 10, 0, 100))

        if same_comm:
            reason = (
                f"You cite {cand_id} (weight={cw:.1f}) and share a community. "
                f"Formalising collaboration could strengthen both research agendas."
            )
        else:
            reason = (
                f"You cite {cand_id} (weight={cw:.1f}) across community boundaries. "
                f"An interdisciplinary collaboration could bridge knowledge gaps."
            )

        suggestions.append(SuggestedCollaborator(
            researcher_id=cand_id,
            score=score,
            citation_weight=cw,
            same_community=same_comm,
            reason=reason,
        ))

    suggestions.sort(key=lambda s: s.score, reverse=True)
    return suggestions[:max_k]
