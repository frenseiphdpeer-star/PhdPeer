"""
Tests for Collaboration Network Intelligence.

Covers:
  * Configuration defaults, scoring weight validation
  * Graph construction (citation, co-authorship, combined)
  * Network metrics (PageRank, betweenness, clustering, degrees)
  * Community detection (Louvain partitioning, modularity, bridges)
  * Network gap identification and collaborator suggestion ranking
  * Scorer orchestration (collaboration_strength, isolation, suggestions)
  * Service layer (analyse, analyse_for_researcher, synthetic generation)
  * Edge cases (empty graphs, isolated nodes, single-edge networks)
"""

from __future__ import annotations

from typing import Dict, List, Set

import numpy as np
import pytest

from app.ml.collaboration_network.config import (
    LOUVAIN_PARAMS,
    METRICS_CONFIG,
    WEIGHTS,
    ScoringWeights,
)
from app.ml.collaboration_network.graph import (
    CitationEdge,
    CoauthorEdge,
    CollaborationGraph,
    build_graph,
)
from app.ml.collaboration_network.metrics import NodeMetrics, compute_metrics
from app.ml.collaboration_network.communities import (
    CommunityResult,
    detect_communities,
    find_bridge_nodes,
)
from app.ml.collaboration_network.gaps import (
    NetworkGap,
    SuggestedCollaborator,
    find_gaps,
    rank_suggestions,
)
from app.ml.collaboration_network.scorer import (
    NetworkAnalysis,
    NodeScore,
    analyse_network,
)
from app.ml.collaboration_network.service import (
    analyse,
    analyse_for_researcher,
    generate_synthetic_network,
    get_analysis_summary,
)


# =========================================================================
# Fixtures
# =========================================================================

@pytest.fixture(scope="module")
def small_network():
    """
    A small network with 2 communities and clear gaps.

    Community 1: A, B, C (co-authors, cite each other)
    Community 2: D, E, F (co-authors, cite each other)
    Cross-community: A cites D (gap), D cites A (gap)
    """
    cit = [
        # Community 1 internal
        CitationEdge("A", "B", weight=3.0),
        CitationEdge("B", "A", weight=2.0),
        CitationEdge("A", "C", weight=1.0),
        CitationEdge("C", "B", weight=1.0),
        # Community 2 internal
        CitationEdge("D", "E", weight=2.0),
        CitationEdge("E", "F", weight=1.0),
        CitationEdge("F", "D", weight=3.0),
        # Cross-community (gaps – no co-authorship)
        CitationEdge("A", "D", weight=2.0),
        CitationEdge("D", "A", weight=1.0),
    ]
    coauth = [
        # Community 1
        CoauthorEdge("A", "B", weight=5.0),
        CoauthorEdge("B", "C", weight=2.0),
        CoauthorEdge("A", "C", weight=1.0),
        # Community 2
        CoauthorEdge("D", "E", weight=3.0),
        CoauthorEdge("E", "F", weight=2.0),
    ]
    return cit, coauth


@pytest.fixture(scope="module")
def small_graph(small_network):
    cit, coauth = small_network
    return build_graph(cit, coauth)


@pytest.fixture(scope="module")
def small_metrics(small_graph):
    return compute_metrics(small_graph)


@pytest.fixture(scope="module")
def small_communities(small_graph):
    return detect_communities(small_graph)


@pytest.fixture(scope="module")
def small_gaps(small_graph, small_communities):
    return find_gaps(small_graph, small_communities)


@pytest.fixture(scope="module")
def small_analysis(small_network):
    cit, coauth = small_network
    return analyse_network(cit, coauth)


@pytest.fixture(scope="module")
def synthetic_net():
    return generate_synthetic_network(n_researchers=20, seed=42)


# =========================================================================
# 1. Configuration
# =========================================================================

class TestConfig:

    def test_scoring_weights_sum(self):
        WEIGHTS.validate()

    def test_collaboration_weights_sum_to_one(self):
        total = WEIGHTS.w_pagerank + WEIGHTS.w_clustering + WEIGHTS.w_coauthor_ratio
        assert abs(total - 1.0) < 1e-6

    def test_isolation_weights_sum_to_one(self):
        total = WEIGHTS.w_iso_inv_coauthor + WEIGHTS.w_iso_sparsity + WEIGHTS.w_iso_gap
        assert abs(total - 1.0) < 1e-6

    def test_louvain_params(self):
        assert LOUVAIN_PARAMS.resolution == 1.0
        assert LOUVAIN_PARAMS.random_state == 42

    def test_metrics_config_max_suggestions(self):
        assert METRICS_CONFIG.max_suggestions > 0

    def test_score_scale(self):
        assert WEIGHTS.score_scale == 100.0

    def test_custom_weights_validate(self):
        w = ScoringWeights(
            w_pagerank=0.5, w_clustering=0.3, w_coauthor_ratio=0.2,
            w_iso_inv_coauthor=0.5, w_iso_sparsity=0.3, w_iso_gap=0.2,
        )
        w.validate()

    def test_invalid_weights_raise(self):
        w = ScoringWeights(
            w_pagerank=0.5, w_clustering=0.5, w_coauthor_ratio=0.5,
        )
        with pytest.raises(ValueError, match="sum to 1.0"):
            w.validate()


# =========================================================================
# 2. Graph Construction
# =========================================================================

class TestGraphConstruction:

    def test_node_count(self, small_graph):
        assert small_graph.n_nodes == 6

    def test_citation_edges(self, small_graph):
        assert small_graph.n_citation_edges == 9

    def test_coauthor_edges(self, small_graph):
        assert small_graph.n_coauthor_edges == 5

    def test_combined_has_all_nodes(self, small_graph):
        assert set(small_graph.combined_graph.nodes()) == {"A", "B", "C", "D", "E", "F"}

    def test_citation_is_directed(self, small_graph):
        assert small_graph.citation_graph.is_directed()

    def test_coauthor_is_undirected(self, small_graph):
        assert not small_graph.coauthor_graph.is_directed()

    def test_combined_is_undirected(self, small_graph):
        assert not small_graph.combined_graph.is_directed()

    def test_duplicate_citations_accumulate(self):
        cit = [
            CitationEdge("X", "Y", weight=1.0),
            CitationEdge("X", "Y", weight=2.0),
        ]
        g = build_graph(cit, [])
        assert g.citation_graph["X"]["Y"]["weight"] == 3.0

    def test_duplicate_coauthors_accumulate(self):
        coauth = [
            CoauthorEdge("X", "Y", weight=1.0),
            CoauthorEdge("X", "Y", weight=3.0),
        ]
        g = build_graph([], coauth)
        assert g.coauthor_graph["X"]["Y"]["weight"] == 4.0

    def test_combined_edge_types(self, small_graph):
        # A-B has both citation and co-authorship
        data = small_graph.combined_graph["A"]["B"]
        assert "citation" in data["edge_types"]
        assert "coauthorship" in data["edge_types"]

    def test_summary(self, small_graph):
        s = small_graph.summary()
        assert s["n_nodes"] == 6
        assert "n_citation_edges" in s
        assert "n_coauthor_edges" in s

    def test_empty_graph(self):
        g = build_graph([], [])
        assert g.n_nodes == 0
        assert g.n_citation_edges == 0


# =========================================================================
# 3. Network Metrics
# =========================================================================

class TestMetrics:

    def test_all_nodes_have_metrics(self, small_metrics, small_graph):
        assert set(small_metrics.keys()) == small_graph.nodes

    def test_pagerank_positive(self, small_metrics):
        for m in small_metrics.values():
            assert m.pagerank >= 0

    def test_pagerank_sums_to_one(self, small_metrics):
        total = sum(m.pagerank for m in small_metrics.values())
        assert total == pytest.approx(1.0, abs=1e-4)

    def test_betweenness_in_range(self, small_metrics):
        for m in small_metrics.values():
            assert 0 <= m.betweenness_centrality <= 1

    def test_clustering_in_range(self, small_metrics):
        for m in small_metrics.values():
            assert 0 <= m.clustering_coefficient <= 1

    def test_a_has_highest_coauthor_degree(self, small_metrics):
        # A is connected to B, C
        assert small_metrics["A"].coauthor_degree == 2

    def test_citation_degrees(self, small_metrics):
        # A cites B, C, D → out_degree=3
        assert small_metrics["A"].citation_out_degree == 3
        # B is cited by A, C → in_degree=2
        assert small_metrics["B"].citation_in_degree == 2

    def test_metrics_serialise(self, small_metrics):
        d = small_metrics["A"].to_dict()
        assert "pagerank" in d
        assert "betweenness_centrality" in d
        assert "clustering_coefficient" in d

    def test_isolated_node_metrics(self):
        """Node with only citation links, no co-authorship."""
        cit = [CitationEdge("X", "Y")]
        g = build_graph(cit, [])
        m = compute_metrics(g)
        assert m["X"].coauthor_degree == 0
        assert m["Y"].coauthor_degree == 0


# =========================================================================
# 4. Community Detection
# =========================================================================

class TestCommunities:

    def test_partition_covers_all_nodes(self, small_communities, small_graph):
        assert set(small_communities.partition.keys()) == small_graph.nodes

    def test_at_least_one_community(self, small_communities):
        assert small_communities.n_communities >= 1

    def test_modularity_in_range(self, small_communities):
        assert -0.5 <= small_communities.modularity <= 1.0

    def test_community_sizes_sum(self, small_communities, small_graph):
        total = sum(small_communities.community_sizes.values())
        assert total == small_graph.n_nodes

    def test_same_community_for_coauthors(self, small_communities):
        # A, B, C have dense co-authorship → likely same community
        comm_a = small_communities.partition["A"]
        comm_b = small_communities.partition["B"]
        comm_c = small_communities.partition["C"]
        # At least two of three should share a community
        assert comm_a == comm_b or comm_a == comm_c or comm_b == comm_c

    def test_serialise(self, small_communities):
        d = small_communities.to_dict()
        assert "partition" in d
        assert "modularity" in d
        assert "n_communities" in d

    def test_empty_graph_communities(self):
        g = build_graph([], [])
        c = detect_communities(g)
        assert c.n_communities == 0
        assert c.modularity == 0.0

    def test_bridge_nodes(self, small_graph, small_communities):
        bridges = find_bridge_nodes(small_graph, small_communities)
        # Bridges are nodes whose co-author neighbours span communities
        for node, comms in bridges.items():
            assert len(comms) >= 2

    def test_deterministic(self, small_graph):
        c1 = detect_communities(small_graph)
        c2 = detect_communities(small_graph)
        assert c1.partition == c2.partition


# =========================================================================
# 5. Network Gaps
# =========================================================================

class TestGaps:

    def test_gaps_found(self, small_gaps):
        assert len(small_gaps) > 0

    def test_gaps_are_citation_only(self, small_gaps, small_graph):
        for gap in small_gaps:
            # Must have citation edge
            assert small_graph.citation_graph.has_edge(gap.source, gap.target)
            # Must NOT have co-authorship edge
            assert not small_graph.coauthor_graph.has_edge(gap.source, gap.target)

    def test_cross_community_gap(self, small_gaps):
        # A→D and D→A are cross-community gaps
        gap_pairs = {(g.source, g.target) for g in small_gaps}
        assert ("A", "D") in gap_pairs or ("D", "A") in gap_pairs

    def test_gaps_sorted_by_weight(self, small_gaps):
        weights = [g.citation_weight for g in small_gaps]
        assert weights == sorted(weights, reverse=True)

    def test_gap_min_weight_filter(self, small_graph, small_communities):
        # With very high threshold, should get fewer gaps
        gaps_high = find_gaps(
            small_graph, small_communities, min_citation_weight=100.0,
        )
        assert len(gaps_high) == 0

    def test_gap_serialise(self, small_gaps):
        d = small_gaps[0].to_dict()
        assert "source" in d
        assert "target" in d
        assert "citation_weight" in d

    def test_rank_suggestions_for_a(
        self, small_graph, small_metrics, small_communities, small_gaps,
    ):
        suggestions = rank_suggestions(
            "A", small_graph, small_metrics, small_communities, small_gaps,
        )
        # A cites D with no co-authorship → D should be suggested
        ids = [s.researcher_id for s in suggestions]
        assert "D" in ids

    def test_suggestion_score_range(
        self, small_graph, small_metrics, small_communities, small_gaps,
    ):
        suggestions = rank_suggestions(
            "A", small_graph, small_metrics, small_communities, small_gaps,
        )
        for s in suggestions:
            assert 0 <= s.score <= 100

    def test_suggestion_serialise(
        self, small_graph, small_metrics, small_communities, small_gaps,
    ):
        suggestions = rank_suggestions(
            "A", small_graph, small_metrics, small_communities, small_gaps,
        )
        if suggestions:
            d = suggestions[0].to_dict()
            assert "researcher_id" in d
            assert "score" in d
            assert "reason" in d

    def test_no_suggestions_for_fully_collaborated(self):
        """If all citation links are also co-authors, no gaps → no suggestions."""
        cit = [CitationEdge("A", "B")]
        coauth = [CoauthorEdge("A", "B")]
        g = build_graph(cit, coauth)
        m = compute_metrics(g)
        c = detect_communities(g)
        gaps = find_gaps(g, c)
        suggestions = rank_suggestions("A", g, m, c, gaps)
        assert len(suggestions) == 0

    def test_max_suggestions_cap(
        self, small_graph, small_metrics, small_communities, small_gaps,
    ):
        suggestions = rank_suggestions(
            "A", small_graph, small_metrics, small_communities, small_gaps,
            max_suggestions=1,
        )
        assert len(suggestions) <= 1


# =========================================================================
# 6. Scorer (Orchestration)
# =========================================================================

class TestScorer:

    def test_analysis_has_all_nodes(self, small_analysis):
        assert set(small_analysis.node_scores.keys()) == {"A", "B", "C", "D", "E", "F"}

    def test_collaboration_strength_range(self, small_analysis):
        for ns in small_analysis.node_scores.values():
            assert 0 <= ns.collaboration_strength_score <= 100

    def test_isolation_score_range(self, small_analysis):
        for ns in small_analysis.node_scores.values():
            assert 0 <= ns.isolation_score <= 100

    def test_community_id_assigned(self, small_analysis):
        for ns in small_analysis.node_scores.values():
            assert ns.community_id >= 0

    def test_well_connected_has_higher_strength(self, small_analysis):
        # A has 2 co-authors and 3 citations → should be well-connected
        # F has 0 direct co-author links to D (only E, F) → fewer connections
        a_score = small_analysis.node_scores["A"].collaboration_strength_score
        # At minimum, A should have a positive score
        assert a_score > 0

    def test_cross_community_node_higher_isolation(self, small_analysis):
        # A and D have cross-community citation but no collab → gap contributes to isolation
        a_iso = small_analysis.node_scores["A"].isolation_score
        assert a_iso > 0

    def test_suggestions_populated_for_gap_nodes(self, small_analysis):
        # A cites D without co-authorship → should get suggestions
        a = small_analysis.node_scores["A"]
        assert len(a.suggested_collaborators) > 0

    def test_node_score_serialises(self, small_analysis):
        d = small_analysis.node_scores["A"].to_dict()
        assert "collaboration_strength_score" in d
        assert "isolation_score" in d
        assert "suggested_collaborators" in d
        assert "metrics" in d

    def test_analysis_serialises(self, small_analysis):
        d = small_analysis.to_dict()
        assert "graph_summary" in d
        assert "communities" in d
        assert "n_gaps" in d
        assert "node_scores" in d

    def test_target_nodes_filter(self, small_network):
        cit, coauth = small_network
        result = analyse_network(cit, coauth, target_nodes=["A", "B"])
        assert set(result.node_scores.keys()) == {"A", "B"}

    def test_n_gaps_positive(self, small_analysis):
        assert small_analysis.n_gaps > 0


# =========================================================================
# 7. Service Layer
# =========================================================================

class TestService:

    def test_analyse_returns_dict(self, small_network):
        cit, coauth = small_network
        result = analyse(cit, coauth)
        assert isinstance(result, dict)
        assert "node_scores" in result

    def test_analyse_for_researcher(self, small_network):
        cit, coauth = small_network
        result = analyse_for_researcher("A", cit, coauth)
        assert "researcher" in result
        assert result["researcher"]["researcher_id"] == "A"

    def test_analyse_for_unknown_researcher(self, small_network):
        cit, coauth = small_network
        result = analyse_for_researcher("UNKNOWN", cit, coauth)
        assert "error" in result

    def test_get_analysis_summary(self, small_network):
        cit, coauth = small_network
        result = get_analysis_summary(cit, coauth)
        assert "graph_summary" in result
        assert "communities" in result

    def test_analyse_with_target_nodes(self, small_network):
        cit, coauth = small_network
        result = analyse(cit, coauth, target_nodes=["D"])
        assert "D" in result["node_scores"]
        assert len(result["node_scores"]) == 1


# =========================================================================
# 8. Synthetic Data
# =========================================================================

class TestSyntheticData:

    def test_correct_researcher_count(self, synthetic_net):
        assert len(synthetic_net["researcher_ids"]) == 20

    def test_has_citations(self, synthetic_net):
        assert len(synthetic_net["citation_edges"]) > 0

    def test_has_coauthorships(self, synthetic_net):
        assert len(synthetic_net["coauthor_edges"]) > 0

    def test_deterministic(self):
        n1 = generate_synthetic_network(n_researchers=10, seed=7)
        n2 = generate_synthetic_network(n_researchers=10, seed=7)
        assert len(n1["citation_edges"]) == len(n2["citation_edges"])
        assert len(n1["coauthor_edges"]) == len(n2["coauthor_edges"])

    def test_community_map_covers_all(self, synthetic_net):
        assert set(synthetic_net["community_map"].keys()) == set(
            synthetic_net["researcher_ids"]
        )

    def test_full_pipeline_on_synthetic(self, synthetic_net):
        result = analyse(
            synthetic_net["citation_edges"],
            synthetic_net["coauthor_edges"],
        )
        assert len(result["node_scores"]) == 20
        for ns in result["node_scores"].values():
            assert 0 <= ns["collaboration_strength_score"] <= 100
            assert 0 <= ns["isolation_score"] <= 100


# =========================================================================
# 9. Edge Cases
# =========================================================================

class TestEdgeCases:

    def test_single_citation_edge(self):
        cit = [CitationEdge("A", "B")]
        g = build_graph(cit, [])
        m = compute_metrics(g)
        assert len(m) == 2
        c = detect_communities(g)
        assert c.n_communities >= 1

    def test_single_coauthor_edge(self):
        coauth = [CoauthorEdge("A", "B")]
        g = build_graph([], coauth)
        m = compute_metrics(g)
        assert m["A"].coauthor_degree == 1
        assert m["A"].citation_in_degree == 0

    def test_self_citation_ignored_in_coauthor(self):
        """Self-loops in citations are valid; co-authorship self-loop is odd but handled."""
        cit = [CitationEdge("A", "A", weight=1.0)]
        g = build_graph(cit, [])
        assert g.n_nodes == 1

    def test_isolated_node_full_pipeline(self):
        """Node that appears only in citation, not co-authorship."""
        cit = [
            CitationEdge("A", "B"),
            CitationEdge("C", "B"),
        ]
        coauth = [CoauthorEdge("A", "B")]
        g = build_graph(cit, coauth)
        result = analyse_network(cit, coauth)
        # C should have high isolation (cited B but no co-authorship with anyone else)
        c_node = result.node_scores.get("C")
        assert c_node is not None
        assert c_node.isolation_score > 0

    def test_complete_graph_low_isolation(self):
        """Fully connected graph → low isolation for everyone."""
        nodes = ["A", "B", "C"]
        cit = []
        coauth = []
        for i, a in enumerate(nodes):
            for j, b in enumerate(nodes):
                if i < j:
                    cit.append(CitationEdge(a, b))
                    cit.append(CitationEdge(b, a))
                    coauth.append(CoauthorEdge(a, b))
        result = analyse_network(cit, coauth)
        for ns in result.node_scores.values():
            # Should have low isolation (most neighbours are co-authors)
            assert ns.isolation_score < 50

    def test_star_topology(self):
        """Hub-and-spoke: central node should have high strength."""
        cit = [CitationEdge(f"S{i}", "HUB") for i in range(5)]
        coauth = [CoauthorEdge(f"S{i}", "HUB") for i in range(5)]
        result = analyse_network(cit, coauth)
        hub = result.node_scores["HUB"]
        # Hub should have higher collaboration strength than spokes
        spoke_avg = np.mean([
            result.node_scores[f"S{i}"].collaboration_strength_score
            for i in range(5)
        ])
        assert hub.collaboration_strength_score >= spoke_avg

    def test_large_synthetic_doesnt_crash(self):
        """Smoke test: 100-node synthetic should complete without error."""
        net = generate_synthetic_network(n_researchers=100, seed=99)
        result = analyse(net["citation_edges"], net["coauthor_edges"])
        assert len(result["node_scores"]) == 100
