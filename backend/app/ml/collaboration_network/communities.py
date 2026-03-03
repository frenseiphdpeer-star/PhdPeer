"""
Community detection for Collaboration Network Intelligence.

Uses the **Louvain** algorithm (``community`` / ``python-louvain``
package) to partition the combined graph into communities.

Provides:
  * ``detect_communities()`` – returns partition and modularity
  * Per-node community labels
  * Cross-community bridge identification
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Set

import community as community_louvain  # python-louvain
import networkx as nx

from app.ml.collaboration_network.config import LOUVAIN_PARAMS, LouvainParams
from app.ml.collaboration_network.graph import CollaborationGraph

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

@dataclass
class CommunityResult:
    """Output of Louvain community detection."""

    partition: Dict[str, int]        # node → community_id
    n_communities: int
    modularity: float                # Q ∈ [-0.5, 1]
    community_sizes: Dict[int, int]  # community_id → member count

    def to_dict(self) -> dict:
        return {
            "partition": self.partition,
            "n_communities": self.n_communities,
            "modularity": round(self.modularity, 4),
            "community_sizes": self.community_sizes,
        }


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

def detect_communities(
    graph: CollaborationGraph,
    *,
    params: LouvainParams | None = None,
) -> CommunityResult:
    """
    Detect communities in the **combined** graph using Louvain.

    Parameters
    ----------
    graph : CollaborationGraph
        The multi-layer collaboration graph.
    params : LouvainParams, optional
        Louvain hyper-parameters (resolution, random_state).

    Returns
    -------
    CommunityResult
        Partition mapping, community count, and modularity score.
    """
    hp = params or LOUVAIN_PARAMS
    combined = graph.combined_graph

    if combined.number_of_nodes() == 0:
        return CommunityResult(
            partition={},
            n_communities=0,
            modularity=0.0,
            community_sizes={},
        )

    # Louvain requires a connected graph component for best results;
    # we run it on whatever we have (disconnected components are OK).
    partition: Dict[str, int] = community_louvain.best_partition(
        combined,
        weight="weight",
        resolution=hp.resolution,
        random_state=hp.random_state,
    )

    modularity = community_louvain.modularity(
        partition, combined, weight="weight",
    )

    # Community sizes
    sizes: Dict[int, int] = {}
    for comm_id in partition.values():
        sizes[comm_id] = sizes.get(comm_id, 0) + 1

    logger.info(
        "Louvain detected %d communities (Q=%.3f)",
        len(sizes),
        modularity,
    )

    return CommunityResult(
        partition=partition,
        n_communities=len(sizes),
        modularity=modularity,
        community_sizes=sizes,
    )


# ---------------------------------------------------------------------------
# Bridge nodes
# ---------------------------------------------------------------------------

def find_bridge_nodes(
    graph: CollaborationGraph,
    community_result: CommunityResult,
) -> Dict[str, Set[int]]:
    """
    Identify *bridge nodes* — researchers whose co-author neighbours
    span multiple communities.

    Returns
    -------
    dict[str, set[int]]
        node → set of community IDs connected via co-authorship.
        Only nodes touching ≥2 communities are included.
    """
    partition = community_result.partition
    bridges: Dict[str, Set[int]] = {}

    for node in graph.coauthor_graph.nodes():
        neighbour_comms = {
            partition.get(nbr) for nbr in graph.coauthor_graph.neighbors(node)
            if partition.get(nbr) is not None
        }
        own_comm = partition.get(node)
        if own_comm is not None:
            neighbour_comms.add(own_comm)
        if len(neighbour_comms) >= 2:
            bridges[node] = neighbour_comms

    return bridges
