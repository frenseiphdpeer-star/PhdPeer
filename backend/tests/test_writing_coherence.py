"""
Tests for the Writing Coherence Scoring module.

Covers:
  * Paragraph segmentation
  * Coherence computation (cosine similarity)
  * Topic drift detection (KMeans + switch penalty)
  * End-to-end scorer
  * Service layer
  * Edge cases (empty text, single paragraph, identical paragraphs)

The sentence-transformer model is loaded once per session (module-scoped
fixture) to avoid repeated downloads.
"""

from __future__ import annotations

from typing import List

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def embedder():
    """Module-scoped sentence-transformer instance (downloaded once)."""
    from app.ml.writing_coherence.embeddings import ParagraphEmbedder
    return ParagraphEmbedder()


@pytest.fixture()
def academic_text() -> str:
    """Multi-paragraph academic-ish text with a coherent theme."""
    return (
        "Machine learning has transformed the field of natural language "
        "processing in the last decade. Pre-trained language models such as "
        "BERT and GPT have achieved state-of-the-art results on many benchmarks.\n\n"
        "Transfer learning allows researchers to fine-tune these models on "
        "domain-specific tasks with relatively small datasets. This has "
        "democratised access to powerful NLP capabilities.\n\n"
        "However, the computational cost of training large models remains a "
        "significant barrier. Green AI initiatives advocate for more efficient "
        "training methods and smaller model architectures.\n\n"
        "In this paper we propose a lightweight distillation approach that "
        "reduces model size by 60% while retaining 95% of task performance.\n\n"
        "Our experiments on three benchmark datasets confirm that the "
        "distilled model generalises well across domains."
    )


@pytest.fixture()
def drifting_text() -> str:
    """Text with abrupt topic changes to test drift detection."""
    return (
        "Quantum computing leverages superposition and entanglement to "
        "perform computations that are intractable for classical machines.\n\n"
        "The French Revolution of 1789 fundamentally altered the political "
        "landscape of Europe and inspired democratic movements worldwide.\n\n"
        "Photosynthesis is the process by which green plants convert sunlight "
        "into chemical energy stored in glucose molecules.\n\n"
        "Modern portfolio theory suggests that investors can minimise risk "
        "by diversifying their asset allocation across uncorrelated markets.\n\n"
        "Recent advances in CRISPR gene-editing technology have opened new "
        "avenues for treating genetic disorders."
    )


# ---------------------------------------------------------------------------
# Paragraph segmentation tests
# ---------------------------------------------------------------------------

class TestSegmentation:

    def test_double_newline_split(self):
        from app.ml.writing_coherence.scorer import segment_paragraphs

        text = "Paragraph one content here.\n\nParagraph two content here."
        paras = segment_paragraphs(text, min_length=10)
        assert len(paras) == 2

    def test_single_newline_fallback(self):
        from app.ml.writing_coherence.scorer import segment_paragraphs

        text = "Line one is long enough.\nLine two is also long enough."
        paras = segment_paragraphs(text, min_length=10)
        assert len(paras) == 2

    def test_short_paragraphs_filtered(self):
        from app.ml.writing_coherence.scorer import segment_paragraphs

        text = "Hi.\n\nThis is a sufficiently long paragraph for testing."
        paras = segment_paragraphs(text, min_length=20)
        assert len(paras) == 1
        assert "sufficiently" in paras[0]

    def test_empty_text_returns_empty(self):
        from app.ml.writing_coherence.scorer import segment_paragraphs

        assert segment_paragraphs("") == []
        assert segment_paragraphs("   \n\n  ") == []

    def test_windows_line_endings(self):
        from app.ml.writing_coherence.scorer import segment_paragraphs

        text = "Paragraph one content here.\r\n\r\nParagraph two content here."
        paras = segment_paragraphs(text, min_length=10)
        assert len(paras) == 2


# ---------------------------------------------------------------------------
# Embedding tests
# ---------------------------------------------------------------------------

class TestEmbeddings:

    def test_single_string(self, embedder):
        vec = embedder.encode("Hello world")
        assert vec.ndim == 1
        assert vec.shape[0] == embedder.dimension

    def test_batch_encoding(self, embedder):
        texts = ["First paragraph.", "Second paragraph.", "Third paragraph."]
        vecs = embedder.encode(texts)
        assert vecs.shape == (3, embedder.dimension)

    def test_normalised_vectors(self, embedder):
        vec = embedder.encode("Some text", normalize=True)
        norm = float(np.linalg.norm(vec))
        assert abs(norm - 1.0) < 1e-4

    def test_similar_texts_high_cosine(self, embedder):
        a = embedder.encode("Machine learning is a subfield of AI.")
        b = embedder.encode("Artificial intelligence includes machine learning.")
        sim = float(np.dot(a, b))
        assert sim > 0.5

    def test_dissimilar_texts_lower_cosine(self, embedder):
        a = embedder.encode("Machine learning is a subfield of AI.")
        b = embedder.encode("The Great Wall of China is a historic structure.")
        sim = float(np.dot(a, b))
        assert sim < 0.5


# ---------------------------------------------------------------------------
# Coherence computation tests
# ---------------------------------------------------------------------------

class TestCoherence:

    def test_identical_paragraphs_perfect_score(self, embedder):
        from app.ml.writing_coherence.coherence import compute_coherence

        # Same vector repeated → cosine sim = 1.0
        vec = embedder.encode("Repeated paragraph content here.")
        embs = np.stack([vec, vec, vec])
        result = compute_coherence(embs)

        assert result.coherence_score == pytest.approx(100.0, abs=0.5)
        assert result.mean_similarity == pytest.approx(1.0, abs=0.01)
        assert len(result.transition_similarities) == 2

    def test_single_paragraph_perfect(self, embedder):
        from app.ml.writing_coherence.coherence import compute_coherence

        vec = embedder.encode("Only one paragraph.")
        embs = vec.reshape(1, -1)
        result = compute_coherence(embs)

        assert result.coherence_score == 100.0
        assert result.n_paragraphs == 1

    def test_coherent_text_higher_than_random(self, embedder, academic_text):
        from app.ml.writing_coherence.coherence import compute_coherence
        from app.ml.writing_coherence.scorer import segment_paragraphs

        paras = segment_paragraphs(academic_text)
        embs = embedder.encode(paras)
        coherent_result = compute_coherence(embs)

        # Random embeddings
        rng = np.random.RandomState(42)
        random_embs = rng.randn(5, embedder.dimension).astype(np.float32)
        random_embs /= np.linalg.norm(random_embs, axis=1, keepdims=True)
        random_result = compute_coherence(random_embs)

        assert coherent_result.coherence_score > random_result.coherence_score

    def test_transition_count_matches(self, embedder):
        from app.ml.writing_coherence.coherence import compute_coherence

        embs = embedder.encode(["A.", "B.", "C.", "D."])
        result = compute_coherence(embs)
        assert len(result.transition_similarities) == 3
        assert result.n_paragraphs == 4


# ---------------------------------------------------------------------------
# Topic drift detection tests
# ---------------------------------------------------------------------------

class TestTopicDrift:

    def test_focused_text_low_drift(self, embedder, academic_text):
        from app.ml.writing_coherence.scorer import segment_paragraphs
        from app.ml.writing_coherence.topic_drift import detect_topic_drift

        paras = segment_paragraphs(academic_text)
        embs = embedder.encode(paras)
        result = detect_topic_drift(embs)

        # Focused text should have high topic_drift_score (= low drift)
        assert result.topic_drift_score >= 50.0
        assert result.structural_consistency_score >= 30.0

    def test_drifting_text_higher_drift(self, embedder, academic_text, drifting_text):
        from app.ml.writing_coherence.scorer import segment_paragraphs
        from app.ml.writing_coherence.topic_drift import detect_topic_drift

        focused_paras = segment_paragraphs(academic_text)
        focused_embs = embedder.encode(focused_paras)
        focused = detect_topic_drift(focused_embs)

        drift_paras = segment_paragraphs(drifting_text)
        drift_embs = embedder.encode(drift_paras)
        drifted = detect_topic_drift(drift_embs)

        # Drifting text should have lower score (more drift)
        assert drifted.topic_drift_score < focused.topic_drift_score

    def test_cluster_labels_length(self, embedder, academic_text):
        from app.ml.writing_coherence.scorer import segment_paragraphs
        from app.ml.writing_coherence.topic_drift import detect_topic_drift

        paras = segment_paragraphs(academic_text)
        embs = embedder.encode(paras)
        result = detect_topic_drift(embs)

        assert len(result.cluster_labels) == len(paras)
        assert result.optimal_k >= 2

    def test_two_paragraphs_returns_perfect(self, embedder):
        from app.ml.writing_coherence.topic_drift import detect_topic_drift

        embs = embedder.encode(["Paragraph A content.", "Paragraph B content."])
        result = detect_topic_drift(embs)

        # < 3 paragraphs → returns perfect scores
        assert result.topic_drift_score == 100.0
        assert result.structural_consistency_score == 100.0

    def test_switch_ratio_range(self, embedder, drifting_text):
        from app.ml.writing_coherence.scorer import segment_paragraphs
        from app.ml.writing_coherence.topic_drift import detect_topic_drift

        paras = segment_paragraphs(drifting_text)
        embs = embedder.encode(paras)
        result = detect_topic_drift(embs)

        assert 0.0 <= result.switch_ratio <= 1.0
        assert result.n_switches >= 0


# ---------------------------------------------------------------------------
# End-to-end scorer tests
# ---------------------------------------------------------------------------

class TestScorer:

    def test_score_text_returns_all_fields(self, embedder, academic_text):
        from app.ml.writing_coherence.scorer import score_text

        result = score_text(academic_text, embedder=embedder)

        assert 0 <= result.coherence_score <= 100
        assert 0 <= result.topic_drift_score <= 100
        assert 0 <= result.structural_consistency_score <= 100
        assert 0 <= result.composite_score <= 100
        assert result.n_paragraphs >= 1
        assert result.paragraphs_used >= 1

    def test_composite_is_weighted_sum(self, embedder, academic_text):
        from app.ml.writing_coherence.config import CONFIG
        from app.ml.writing_coherence.scorer import score_text

        result = score_text(academic_text, embedder=embedder)

        expected = (
            CONFIG.weight_coherence * result.coherence_score
            + CONFIG.weight_topic_drift * result.topic_drift_score
            + CONFIG.weight_structural * result.structural_consistency_score
        )
        assert result.composite_score == pytest.approx(expected, abs=0.1)

    def test_empty_text_zero_scores(self, embedder):
        from app.ml.writing_coherence.scorer import score_text

        result = score_text("", embedder=embedder)

        assert result.coherence_score == 0.0
        assert result.topic_drift_score == 0.0
        assert result.composite_score == 0.0
        assert result.n_paragraphs == 0

    def test_pre_segmented_paragraphs(self, embedder):
        from app.ml.writing_coherence.scorer import score_text

        paras = [
            "First paragraph about neural networks and deep learning.",
            "Second paragraph continues discussing model architectures.",
            "Third paragraph covers training procedures and optimization.",
        ]
        result = score_text("ignored", paragraphs=paras, embedder=embedder)

        assert result.paragraphs_used == 3
        assert result.coherence_score > 0

    def test_to_dict_serialisable(self, embedder, academic_text):
        import json
        from app.ml.writing_coherence.scorer import score_text

        result = score_text(academic_text, embedder=embedder)
        d = result.to_dict()

        # Should be JSON-serialisable
        json_str = json.dumps(d)
        assert isinstance(json_str, str)

        # Check all expected top-level keys
        assert "coherence_score" in d
        assert "topic_drift_score" in d
        assert "structural_consistency_score" in d
        assert "composite_score" in d
        assert "coherence_detail" in d
        assert "topic_drift_detail" in d

    def test_coherent_text_scores_higher(self, embedder, academic_text, drifting_text):
        from app.ml.writing_coherence.scorer import score_text

        coherent = score_text(academic_text, embedder=embedder)
        drifted = score_text(drifting_text, embedder=embedder)

        assert coherent.composite_score > drifted.composite_score


# ---------------------------------------------------------------------------
# Service layer tests
# ---------------------------------------------------------------------------

class TestService:

    def test_score_document_text(self, embedder, academic_text):
        from app.ml.writing_coherence import service
        # Monkey-patch the embedder so we don't re-load
        import app.ml.writing_coherence.embeddings as emb_mod
        original = emb_mod._model
        emb_mod._model = embedder
        try:
            result = service.score_document_text(academic_text)
            assert "coherence_score" in result
            assert "topic_drift_score" in result
            assert "structural_consistency_score" in result
            assert "composite_score" in result
            assert result["coherence_score"] > 0
        finally:
            emb_mod._model = original

    def test_score_document_text_with_paragraphs(self, embedder):
        from app.ml.writing_coherence import service
        import app.ml.writing_coherence.embeddings as emb_mod
        original = emb_mod._model
        emb_mod._model = embedder
        try:
            paras = [
                "Deep learning revolutionised computer vision tasks.",
                "Convolutional neural networks are widely used.",
                "ResNet introduced skip connections for deeper networks.",
            ]
            result = service.score_document_text("ignored", paragraphs=paras)
            assert result["paragraphs_used"] == 3
        finally:
            emb_mod._model = original


# ---------------------------------------------------------------------------
# Config validation tests
# ---------------------------------------------------------------------------

class TestConfig:

    def test_default_weights_valid(self):
        from app.ml.writing_coherence.config import CONFIG
        CONFIG.validate()  # should not raise

    def test_invalid_weights_raises(self):
        from app.ml.writing_coherence.config import CoherenceConfig

        bad = CoherenceConfig(
            weight_coherence=0.5,
            weight_topic_drift=0.5,
            weight_structural=0.5,  # sums to 1.5
        )
        with pytest.raises(ValueError, match="must sum to 1.0"):
            bad.validate()
