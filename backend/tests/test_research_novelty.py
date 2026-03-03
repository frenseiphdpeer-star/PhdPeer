"""
Tests for the Research Novelty Scoring module.

Covers:
  * SciBERT embedding generation
  * FAISS corpus index (add, search, centroid, persistence)
  * TF-IDF terminology scoring
  * End-to-end novelty scorer
  * Service layer (score_text, build_corpus_index)
  * Configuration validation
  * Edge cases (empty text, single document corpus, no citations)

The SciBERT model is loaded once per session (module-scoped fixture)
to avoid repeated downloads.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import List

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def embedder():
    """Module-scoped SciBERT embedder (downloaded once)."""
    from app.ml.research_novelty.embeddings import SciBERTEmbedder
    return SciBERTEmbedder()


@pytest.fixture()
def corpus_texts() -> List[str]:
    """Small corpus of 6 clearly-different topic papers."""
    return [
        (
            "We propose a deep learning architecture for image classification "
            "using residual connections and batch normalisation. Our experiments "
            "on CIFAR-10 and ImageNet demonstrate competitive accuracy."
        ),
        (
            "This paper investigates the impact of reinforcement learning "
            "on robotic manipulation tasks. We train a policy network using "
            "proximal policy optimisation in a simulated environment."
        ),
        (
            "We study the effects of ocean acidification on coral reef "
            "ecosystems using long-term monitoring data from the Great "
            "Barrier Reef. Our analysis reveals declining calcification rates."
        ),
        (
            "Genome-wide association studies have identified multiple risk "
            "loci for type 2 diabetes. We perform a meta-analysis of 50 "
            "cohorts comprising 100,000 individuals."
        ),
        (
            "We examine the causal relationship between monetary policy and "
            "inflation expectations using a structural vector autoregression "
            "framework applied to US macroeconomic data."
        ),
        (
            "This study presents a novel catalyst for hydrogen evolution "
            "reactions based on transition-metal dichalcogenides. We "
            "achieve a Tafel slope of 45 mV/dec in acidic electrolyte."
        ),
    ]


@pytest.fixture()
def novel_text() -> str:
    """A manuscript with intentionally novel / cross-field content."""
    return (
        "We introduce a quantum variational eigensolver "
        "for simulating protein folding pathways on a 72-qubit "
        "superconducting processor. Our hybrid quantum-classical "
        "algorithm achieves chemical accuracy for small peptides "
        "and demonstrates polynomial speedup over classical methods. "
        "The approach combines topological error correction with "
        "adaptive circuit compilation."
    )


@pytest.fixture()
def similar_text() -> str:
    """A manuscript that closely matches the corpus."""
    return (
        "We propose a deep learning architecture for object detection "
        "using convolutional layers and skip connections. Our experiments "
        "on CIFAR-10 demonstrate state-of-the-art performance."
    )


# ---------------------------------------------------------------------------
# SciBERT embedding tests
# ---------------------------------------------------------------------------

class TestSciBERTEmbeddings:

    def test_single_text_shape(self, embedder):
        vec = embedder.encode("Hello world")
        assert vec.shape == (1, embedder.dimension)
        assert vec.dtype == np.float32

    def test_batch_encoding_shape(self, embedder):
        texts = ["Paper A.", "Paper B.", "Paper C."]
        vecs = embedder.encode(texts)
        assert vecs.shape == (3, embedder.dimension)

    def test_normalised_vectors(self, embedder):
        vecs = embedder.encode(["Test sentence for normalisation."])
        norms = np.linalg.norm(vecs, axis=1)
        np.testing.assert_allclose(norms, 1.0, atol=1e-5)

    def test_similar_texts_close(self, embedder):
        a = embedder.encode("Deep learning for image classification.")
        b = embedder.encode("Neural networks for visual recognition tasks.")
        c = embedder.encode("Freshwater ecology of Amazonian river basins.")
        sim_ab = float(a @ b.T)
        sim_ac = float(a @ c.T)
        assert sim_ab > sim_ac

    def test_dimension_is_768(self, embedder):
        # SciBERT default hidden size
        assert embedder.dimension == 768


# ---------------------------------------------------------------------------
# FAISS corpus index tests
# ---------------------------------------------------------------------------

class TestCorpusIndex:

    def test_add_and_size(self):
        from app.ml.research_novelty.corpus_index import CorpusIndex

        idx = CorpusIndex(dimension=16, index_type="Flat")
        vecs = np.random.randn(20, 16).astype(np.float32)
        idx.add(vecs)
        assert idx.size == 20

    def test_search_returns_k_results(self):
        from app.ml.research_novelty.corpus_index import CorpusIndex

        idx = CorpusIndex(dimension=16, index_type="Flat")
        vecs = np.random.randn(50, 16).astype(np.float32)
        idx.add(vecs)

        query = np.random.randn(1, 16).astype(np.float32)
        distances, indices, ids = idx.search(query, k=5)

        assert distances.shape == (1, 5)
        assert indices.shape == (1, 5)
        assert len(ids) == 5

    def test_centroid_shape(self):
        from app.ml.research_novelty.corpus_index import CorpusIndex

        idx = CorpusIndex(dimension=8, index_type="Flat")
        vecs = np.ones((10, 8), dtype=np.float32)
        idx.add(vecs)
        assert idx.centroid.shape == (8,)
        np.testing.assert_allclose(idx.centroid, 1.0)

    def test_centroid_distance(self):
        from app.ml.research_novelty.corpus_index import CorpusIndex

        idx = CorpusIndex(dimension=4, index_type="Flat")
        vecs = np.zeros((5, 4), dtype=np.float32)
        idx.add(vecs)

        query = np.ones(4, dtype=np.float32)
        dist = idx.centroid_distance(query)
        assert dist == pytest.approx(2.0, abs=1e-5)  # sqrt(4)

    def test_ids_mapping(self):
        from app.ml.research_novelty.corpus_index import CorpusIndex

        idx = CorpusIndex(dimension=4, index_type="Flat")
        vecs = np.eye(4, dtype=np.float32)
        idx.add(vecs, ids=["A", "B", "C", "D"])

        query = vecs[0:1]
        _, _, ids = idx.search(query, k=1)
        assert ids[0] == "A"

    def test_save_and_load(self):
        from app.ml.research_novelty.corpus_index import CorpusIndex

        idx = CorpusIndex(dimension=8, index_type="Flat")
        vecs = np.random.randn(10, 8).astype(np.float32)
        idx.add(vecs, ids=[f"paper_{i}" for i in range(10)])

        with tempfile.TemporaryDirectory() as tmpdir:
            idx.save(Path(tmpdir))
            loaded = CorpusIndex.load(Path(tmpdir))

            assert loaded.size == 10
            assert loaded.dimension == 8
            np.testing.assert_allclose(loaded.centroid, idx.centroid, atol=1e-5)

    def test_from_embeddings_convenience(self):
        from app.ml.research_novelty.corpus_index import CorpusIndex

        vecs = np.random.randn(30, 16).astype(np.float32)
        idx = CorpusIndex.from_embeddings(vecs, index_type="Flat")
        assert idx.size == 30

    def test_ivfflat_fallback_when_small(self):
        from app.ml.research_novelty.corpus_index import CorpusIndex

        # nlist=100 but only 10 vectors → should fall back to Flat
        idx = CorpusIndex(dimension=8, index_type="IVFFlat", nlist=100)
        vecs = np.random.randn(10, 8).astype(np.float32)
        idx.add(vecs)
        assert idx.index_type == "Flat"
        assert idx.size == 10

    def test_mean_knn_distance(self):
        from app.ml.research_novelty.corpus_index import CorpusIndex

        idx = CorpusIndex(dimension=4, index_type="Flat")
        vecs = np.zeros((10, 4), dtype=np.float32)
        idx.add(vecs)

        query = np.zeros(4, dtype=np.float32)
        mean_d = idx.mean_knn_distance(query, k=5)
        assert mean_d == pytest.approx(0.0, abs=1e-5)


# ---------------------------------------------------------------------------
# TF-IDF terminology scorer tests
# ---------------------------------------------------------------------------

class TestTfidfScorer:

    def test_fit_and_score(self, corpus_texts):
        from app.ml.research_novelty.tfidf import TerminologyScorer

        scorer = TerminologyScorer()
        scorer.fit(corpus_texts)

        result = scorer.score(corpus_texts[0])
        assert 0 <= result.terminology_uniqueness_index <= 100
        assert result.n_query_terms > 0

    def test_novel_text_scores_higher(self, corpus_texts, novel_text, similar_text):
        from app.ml.research_novelty.tfidf import TerminologyScorer

        scorer = TerminologyScorer()
        scorer.fit(corpus_texts)

        novel_result = scorer.score(novel_text)
        similar_result = scorer.score(similar_text)

        assert novel_result.terminology_uniqueness_index >= similar_result.terminology_uniqueness_index

    def test_oov_ratio_range(self, corpus_texts, novel_text):
        from app.ml.research_novelty.tfidf import TerminologyScorer

        scorer = TerminologyScorer()
        scorer.fit(corpus_texts)

        result = scorer.score(novel_text)
        assert 0.0 <= result.oov_ratio <= 1.0

    def test_top_rare_terms_returned(self, corpus_texts):
        from app.ml.research_novelty.tfidf import TerminologyScorer

        scorer = TerminologyScorer()
        scorer.fit(corpus_texts)

        result = scorer.score(corpus_texts[0], top_n=5)
        assert len(result.top_rare_terms) <= 5
        # Each entry is (term, idf_value)
        for term, idf in result.top_rare_terms:
            assert isinstance(term, str)
            assert idf > 0

    def test_unfitted_raises(self):
        from app.ml.research_novelty.tfidf import TerminologyScorer

        scorer = TerminologyScorer()
        with pytest.raises(RuntimeError, match="not fitted"):
            scorer.score("Some text")

    def test_empty_query_returns_zero(self, corpus_texts):
        from app.ml.research_novelty.tfidf import TerminologyScorer

        scorer = TerminologyScorer()
        scorer.fit(corpus_texts)

        # All stop words → should be filtered out
        result = scorer.score("the the the the")
        assert result.terminology_uniqueness_index == 0.0
        assert result.n_query_terms == 0


# ---------------------------------------------------------------------------
# End-to-end novelty scorer tests
# ---------------------------------------------------------------------------

class TestNoveltyScorer:

    def test_score_manuscript_returns_all_fields(self, embedder, corpus_texts):
        from app.ml.research_novelty.corpus_index import CorpusIndex
        from app.ml.research_novelty.scorer import score_manuscript
        from app.ml.research_novelty.tfidf import TerminologyScorer

        corpus_embs = embedder.encode(corpus_texts)
        index = CorpusIndex.from_embeddings(corpus_embs, index_type="Flat")

        tfidf = TerminologyScorer()
        tfidf.fit(corpus_texts)

        query = "We study transformer models for scientific text mining."
        query_emb = embedder.encode(query)

        result = score_manuscript(query_emb, index, tfidf, query)

        assert 0 <= result.novelty_score <= 100
        assert result.field_distance >= 0
        assert result.mean_knn_distance >= 0
        assert 0 <= result.terminology_uniqueness_index <= 100
        assert result.corpus_size == len(corpus_texts)

    def test_novel_text_scores_higher_than_similar(
        self, embedder, corpus_texts, novel_text, similar_text
    ):
        from app.ml.research_novelty.corpus_index import CorpusIndex
        from app.ml.research_novelty.scorer import score_manuscript
        from app.ml.research_novelty.tfidf import TerminologyScorer

        corpus_embs = embedder.encode(corpus_texts)
        index = CorpusIndex.from_embeddings(corpus_embs, index_type="Flat")

        tfidf = TerminologyScorer()
        tfidf.fit(corpus_texts)

        novel_emb = embedder.encode(novel_text)
        similar_emb = embedder.encode(similar_text)

        novel_score = score_manuscript(novel_emb, index, tfidf, novel_text)
        similar_score = score_manuscript(similar_emb, index, tfidf, similar_text)

        assert novel_score.novelty_score > similar_score.novelty_score

    def test_citation_novelty_component(self, embedder, corpus_texts):
        from app.ml.research_novelty.corpus_index import CorpusIndex
        from app.ml.research_novelty.scorer import score_manuscript
        from app.ml.research_novelty.tfidf import TerminologyScorer

        corpus_embs = embedder.encode(corpus_texts)
        ids = [f"paper_{i}" for i in range(len(corpus_texts))]
        index = CorpusIndex.from_embeddings(corpus_embs, ids=ids, index_type="Flat")

        tfidf = TerminologyScorer()
        tfidf.fit(corpus_texts)

        query = "A study on neural architecture search."
        query_emb = embedder.encode(query)

        # Citations all inside the corpus
        result_inside = score_manuscript(
            query_emb, index, tfidf, query,
            citations=["paper_0", "paper_1"],
        )
        # Citations all outside the corpus
        result_outside = score_manuscript(
            query_emb, index, tfidf, query,
            citations=["external_1", "external_2"],
        )

        assert result_outside.citation_novelty > result_inside.citation_novelty

    def test_to_dict_serialisable(self, embedder, corpus_texts):
        from app.ml.research_novelty.corpus_index import CorpusIndex
        from app.ml.research_novelty.scorer import score_manuscript
        from app.ml.research_novelty.tfidf import TerminologyScorer
        import json

        corpus_embs = embedder.encode(corpus_texts)
        index = CorpusIndex.from_embeddings(corpus_embs, index_type="Flat")

        tfidf = TerminologyScorer()
        tfidf.fit(corpus_texts)

        query_emb = embedder.encode("Test text.")
        result = score_manuscript(query_emb, index, tfidf, "Test text.")

        d = result.to_dict()
        serialised = json.dumps(d)
        assert isinstance(serialised, str)

    def test_no_citations_zero_component(self, embedder, corpus_texts):
        from app.ml.research_novelty.corpus_index import CorpusIndex
        from app.ml.research_novelty.scorer import score_manuscript
        from app.ml.research_novelty.tfidf import TerminologyScorer

        corpus_embs = embedder.encode(corpus_texts)
        index = CorpusIndex.from_embeddings(corpus_embs, index_type="Flat")

        tfidf = TerminologyScorer()
        tfidf.fit(corpus_texts)

        query_emb = embedder.encode("Some query.")
        result = score_manuscript(query_emb, index, tfidf, "Some query.")

        assert result.citation_novelty == 0.0


# ---------------------------------------------------------------------------
# Service layer tests
# ---------------------------------------------------------------------------

class TestService:

    def test_build_and_score(self, embedder, corpus_texts):
        from app.ml.research_novelty import service
        from app.ml.research_novelty.corpus_index import CorpusIndex
        from app.ml.research_novelty.tfidf import TerminologyScorer

        # Build index via service (using injected embedder)
        info = service.build_corpus_index(
            corpus_texts, save=False, _embedder=embedder,
        )
        assert info["corpus_size"] == len(corpus_texts)

        # Score a novel text
        result = service.score_text(
            "We study quantum error correction on superconducting qubits.",
            _embedder=embedder,
        )
        assert "novelty_score" in result
        assert 0 <= result["novelty_score"] <= 100

    def test_score_with_citations(self, embedder, corpus_texts):
        from app.ml.research_novelty import service

        service.build_corpus_index(
            corpus_texts, save=False, _embedder=embedder,
        )
        result = service.score_text(
            "Novel approach to protein structure prediction.",
            citations=["external_doi_1", "external_doi_2"],
            _embedder=embedder,
        )
        assert result["citation_novelty"] > 0

    def test_corpus_status_before_build(self):
        from app.ml.research_novelty import service

        service.reload()
        status = service.get_corpus_status()
        assert status["loaded"] is False

    def test_demo_corpus_generation(self):
        from app.ml.research_novelty import service

        papers = service.generate_demo_corpus(n=20)
        assert len(papers) == 20
        assert all(isinstance(p, str) for p in papers)
        assert all(len(p) > 10 for p in papers)


# ---------------------------------------------------------------------------
# Config tests
# ---------------------------------------------------------------------------

class TestConfig:

    def test_default_weights_sum_to_one(self):
        from app.ml.research_novelty.config import CONFIG

        CONFIG.validate()  # Should not raise

    def test_invalid_weights_raises(self):
        from app.ml.research_novelty.config import NoveltyConfig

        bad = NoveltyConfig(
            weight_field_distance=0.5,
            weight_terminology=0.5,
            weight_citation_novelty=0.5,
        )
        with pytest.raises(ValueError, match="must sum to 1.0"):
            bad.validate()

    def test_score_scale_default(self):
        from app.ml.research_novelty.config import CONFIG

        assert CONFIG.score_scale == 100.0
