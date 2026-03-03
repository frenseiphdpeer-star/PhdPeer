"""
Graph construction for Collaboration Network Intelligence.

Builds a unified NetworkX DiGraph / Graph from:
  * Citation edges  (directed: A → B means A cites B)
  * Co-authorship edges (undirected: A—B means joint paper)

Each edge carries:
  * ``edge_type``: "citation" | "coauthorship"
  * ``weight``: additive (multiple citations / papers increase weight)

The resulting multi-layer graph is consumed by metrics, community
detection, and gap-finding modules.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

import networkx as nx

from app.ml.collaboration_network.config import (
    DEFAULT_CITATION_WEIGHT,
    DEFAULT_COAUTHOR_WEIGHT,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Edge input dataclass
# ---------------------------------------------------------------------------

@dataclass
class CitationEdge:
    """Directed citation: *source* cites *target*."""

    source: str
    target: str
    weight: float = DEFAULT_CITATION_WEIGHT
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class CoauthorEdge:
    """Undirected co-authorship between two researchers."""

    source: str
    target: str
    weight: float = DEFAULT_COAUTHOR_WEIGHT
    metadata: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Graph container
# ---------------------------------------------------------------------------

@dataclass
class CollaborationGraph:
    """
    Holds the raw NetworkX graphs and convenience look-ups.

    Attributes
    ----------
    citation_graph : nx.DiGraph
        Directed citation graph.
    coauthor_graph : nx.Graph
        Undirected co-authorship graph.
    combined_graph : nx.Graph
        Undirected union of both layers (edges carry ``edge_type`` sets).
    nodes : set[str]
        All researcher IDs.
    """

    citation_graph: nx.DiGraph
    coauthor_graph: nx.Graph
    combined_graph: nx.Graph
    nodes: Set[str]

    @property
    def n_nodes(self) -> int:
        return len(self.nodes)

    @property
    def n_citation_edges(self) -> int:
        return self.citation_graph.number_of_edges()

    @property
    def n_coauthor_edges(self) -> int:
        return self.coauthor_graph.number_of_edges()

    def summary(self) -> Dict[str, Any]:
        return {
            "n_nodes": self.n_nodes,
            "n_citation_edges": self.n_citation_edges,
            "n_coauthor_edges": self.n_coauthor_edges,
            "n_combined_edges": self.combined_graph.number_of_edges(),
        }


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

def build_graph(
    citation_edges: Sequence[CitationEdge],
    coauthor_edges: Sequence[CoauthorEdge],
) -> CollaborationGraph:
    """
    Construct the multi-layer collaboration graph from edge lists.

    Parameters
    ----------
    citation_edges : sequence of CitationEdge
        Directed citations (source cites target).
    coauthor_edges : sequence of CoauthorEdge
        Undirected co-authorships.

    Returns
    -------
    CollaborationGraph
        A container with citation, co-author, and combined graphs.
    """
    cit_g = nx.DiGraph()
    coauth_g = nx.Graph()

    # ── Citation layer (directed) ─────────────────────────────────────
    for e in citation_edges:
        if cit_g.has_edge(e.source, e.target):
            cit_g[e.source][e.target]["weight"] += e.weight
        else:
            cit_g.add_edge(
                e.source, e.target,
                weight=e.weight,
                edge_type="citation",
            )

    # ── Co-authorship layer (undirected) ──────────────────────────────
    for e in coauthor_edges:
        if coauth_g.has_edge(e.source, e.target):
            coauth_g[e.source][e.target]["weight"] += e.weight
        else:
            coauth_g.add_edge(
                e.source, e.target,
                weight=e.weight,
                edge_type="coauthorship",
            )

    # ── Combined (undirected union) ───────────────────────────────────
    combined = nx.Graph()
    all_nodes: Set[str] = set(cit_g.nodes()) | set(coauth_g.nodes())
    combined.add_nodes_from(all_nodes)

    # Add citation edges (collapse direction)
    for u, v, d in cit_g.edges(data=True):
        if combined.has_edge(u, v):
            combined[u][v]["weight"] += d["weight"]
            combined[u][v]["edge_types"].add("citation")
        else:
            combined.add_edge(
                u, v,
                weight=d["weight"],
                edge_types={"citation"},
            )

    # Add co-author edges
    for u, v, d in coauth_g.edges(data=True):
        if combined.has_edge(u, v):
            combined[u][v]["weight"] += d["weight"]
            combined[u][v]["edge_types"].add("coauthorship")
        else:
            combined.add_edge(
                u, v,
                weight=d["weight"],
                edge_types={"coauthorship"},
            )

    logger.info(
        "Built collaboration graph: %d nodes, %d citation edges, "
        "%d co-author edges, %d combined edges",
        len(all_nodes),
        cit_g.number_of_edges(),
        coauth_g.number_of_edges(),
        combined.number_of_edges(),
    )

    return CollaborationGraph(
        citation_graph=cit_g,
        coauthor_graph=coauth_g,
        combined_graph=combined,
        nodes=all_nodes,
    )
