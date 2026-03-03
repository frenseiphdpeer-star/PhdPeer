"""
Collaboration Network Service – public entry-point for the API layer.

Provides:
  * ``analyse()``                  – full network analysis
  * ``analyse_for_researcher()``   – single-researcher analysis
  * ``generate_synthetic_network()`` – deterministic synthetic graph
  * ``get_analysis_summary()``     – lightweight summary
"""

from __future__ import annotations

import logging
import random as _random
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from app.ml.collaboration_network.config import METRICS_CONFIG
from app.ml.collaboration_network.graph import CitationEdge, CoauthorEdge
from app.ml.collaboration_network.scorer import NetworkAnalysis, analyse_network

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Full analysis
# ---------------------------------------------------------------------------

def analyse(
    citation_edges: Sequence[CitationEdge],
    coauthor_edges: Sequence[CoauthorEdge],
    *,
    target_nodes: Sequence[str] | None = None,
) -> Dict[str, Any]:
    """Run full network analysis and return serialisable dict."""
    result = analyse_network(
        citation_edges, coauthor_edges, target_nodes=target_nodes,
    )
    return result.to_dict()


def analyse_for_researcher(
    researcher_id: str,
    citation_edges: Sequence[CitationEdge],
    coauthor_edges: Sequence[CoauthorEdge],
) -> Dict[str, Any]:
    """Run analysis scoped to one researcher; return their score dict."""
    result = analyse_network(
        citation_edges, coauthor_edges, target_nodes=[researcher_id],
    )
    node = result.node_scores.get(researcher_id)
    if node is None:
        return {"error": f"Researcher '{researcher_id}' not found in graph."}
    return {
        "graph_summary": result.graph_summary,
        "communities": result.community_result.to_dict(),
        "n_gaps": result.n_gaps,
        "researcher": node.to_dict(),
    }


def get_analysis_summary(
    citation_edges: Sequence[CitationEdge],
    coauthor_edges: Sequence[CoauthorEdge],
) -> Dict[str, Any]:
    """Lightweight summary: graph stats + community info only."""
    from app.ml.collaboration_network.graph import build_graph
    from app.ml.collaboration_network.communities import detect_communities

    graph = build_graph(citation_edges, coauthor_edges)
    comms = detect_communities(graph)
    return {
        "graph_summary": graph.summary(),
        "communities": comms.to_dict(),
    }


# ---------------------------------------------------------------------------
# Synthetic data generation
# ---------------------------------------------------------------------------

def generate_synthetic_network(
    n_researchers: int = 30,
    seed: int = 42,
) -> Dict[str, Any]:
    """
    Generate a synthetic citation + co-authorship network with
    realistic community structure.

    Returns dict with ``citation_edges``, ``coauthor_edges``, and
    ``researcher_ids``.
    """
    rng = np.random.RandomState(seed)
    py_rng = _random.Random(seed)

    researchers = [f"R{i:03d}" for i in range(n_researchers)]

    # Assign to ~3 communities
    n_comms = max(2, n_researchers // 10)
    community_map: Dict[str, int] = {}
    for r in researchers:
        community_map[r] = py_rng.randint(0, n_comms - 1)

    citation_edges: List[CitationEdge] = []
    coauthor_edges: List[CoauthorEdge] = []

    seen_coauthor = set()

    for i, r_a in enumerate(researchers):
        for j, r_b in enumerate(researchers):
            if i == j:
                continue
            same_comm = community_map[r_a] == community_map[r_b]
            # Citation probability
            cit_prob = 0.3 if same_comm else 0.05
            if rng.random() < cit_prob:
                w = float(rng.poisson(2) + 1)
                citation_edges.append(CitationEdge(
                    source=r_a, target=r_b, weight=w,
                ))

            # Co-authorship probability (undirected, avoid duplicates)
            pair = tuple(sorted([r_a, r_b]))
            if pair in seen_coauthor:
                continue
            coauth_prob = 0.25 if same_comm else 0.02
            if rng.random() < coauth_prob:
                w = float(rng.poisson(1) + 1)
                coauthor_edges.append(CoauthorEdge(
                    source=r_a, target=r_b, weight=w,
                ))
                seen_coauthor.add(pair)

    logger.info(
        "Generated synthetic network: %d researchers, %d citations, "
        "%d co-authorships",
        n_researchers,
        len(citation_edges),
        len(coauthor_edges),
    )

    return {
        "citation_edges": citation_edges,
        "coauthor_edges": coauthor_edges,
        "researcher_ids": researchers,
        "community_map": community_map,
    }
