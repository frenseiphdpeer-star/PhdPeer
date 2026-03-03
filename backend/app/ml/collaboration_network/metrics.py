"""
Network metrics for Collaboration Network Intelligence.

Computes per-node centrality metrics on the combined or individual
graph layers:

  * **PageRank**               – global influence / prestige
  * **Betweenness centrality** – bridging role between clusters
  * **Clustering coefficient** – local cohesion (triangle density)

All metrics are scaled to [0, 1].
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict

import networkx as nx

from app.ml.collaboration_network.graph import CollaborationGraph

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class NodeMetrics:
    """Centrality metrics for one researcher node."""

    pagerank: float                 # [0, 1] – proportional
    betweenness_centrality: float   # [0, 1]
    clustering_coefficient: float   # [0, 1]
    citation_in_degree: int         # incoming citations
    citation_out_degree: int        # outgoing citations
    coauthor_degree: int            # number of co-authors

    def to_dict(self) -> dict:
        return {
            "pagerank": round(self.pagerank, 6),
            "betweenness_centrality": round(self.betweenness_centrality, 6),
            "clustering_coefficient": round(self.clustering_coefficient, 6),
            "citation_in_degree": self.citation_in_degree,
            "citation_out_degree": self.citation_out_degree,
            "coauthor_degree": self.coauthor_degree,
        }


# ---------------------------------------------------------------------------
# Computation
# ---------------------------------------------------------------------------

def compute_metrics(
    graph: CollaborationGraph,
) -> Dict[str, NodeMetrics]:
    """
    Compute centrality metrics for every node in the combined graph.

    PageRank is computed on the **citation** graph (directed);
    betweenness and clustering on the **combined** undirected graph.

    Returns
    -------
    dict[str, NodeMetrics]
        Keyed by researcher ID.
    """
    cit = graph.citation_graph
    combined = graph.combined_graph
    coauth = graph.coauthor_graph

    # ── PageRank on citation graph ────────────────────────────────────
    if cit.number_of_nodes() == 0:
        pr: Dict[str, float] = {}
    else:
        pr = nx.pagerank(cit, weight="weight")

    # ── Betweenness on combined graph ─────────────────────────────────
    if combined.number_of_edges() == 0:
        bc: Dict[str, float] = {n: 0.0 for n in graph.nodes}
    else:
        bc = nx.betweenness_centrality(combined, weight="weight")

    # ── Clustering coefficient on combined graph ──────────────────────
    cc: Dict[str, float] = nx.clustering(combined, weight="weight")

    # ── Build per-node results ────────────────────────────────────────
    results: Dict[str, NodeMetrics] = {}
    for node in graph.nodes:
        results[node] = NodeMetrics(
            pagerank=pr.get(node, 0.0),
            betweenness_centrality=bc.get(node, 0.0),
            clustering_coefficient=cc.get(node, 0.0),
            citation_in_degree=cit.in_degree(node) if node in cit else 0,
            citation_out_degree=cit.out_degree(node) if node in cit else 0,
            coauthor_degree=coauth.degree(node) if node in coauth else 0,
        )

    logger.info("Computed centrality metrics for %d nodes", len(results))
    return results
