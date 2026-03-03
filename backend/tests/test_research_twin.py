"""
Comprehensive test suite for the AI Research Twin Behavioural Modelling System.

Covers:
 • config validation
 • temporal feature engineering (hourly binning, cyclic encodings, smoothing)
 • sequence slicing & padding
 • LSTM training, prediction, embedding extraction, persistence
 • user embedding aggregation & similarity
 • procrastination / productive-window / submission-window detection
 • nudge recommendation generation
 • scorer orchestration (full pipeline)
 • service layer + synthetic data
 • Pydantic schema contracts
 • API endpoint response shapes
"""

from __future__ import annotations

import json
import math
import shutil
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd
import pytest
import torch

# ---------------------------------------------------------------------------
# Module imports
# ---------------------------------------------------------------------------
from app.ml.research_twin import config as _cfg
from app.ml.research_twin.config import (
    EMBED_CFG,
    EVENT_TYPES,
    FEATURE_CHANNELS,
    LSTM_CFG,
    LSTM_FILENAME,
    LSTMConfig,
    METADATA_FILENAME,
    OUTPUT_NAMES,
    RECOMMENDER_CFG,
    RecommenderConfig,
    SEQ_CFG,
    TEMPORAL_CFG,
    TWIN_ARTIFACTS_DIR,
    EmbeddingConfig,
    SequenceConfig,
    TemporalFeatureConfig,
)
from app.ml.research_twin.embedding import (
    EmbeddingAnalysis,
    UserEmbedding,
    analyse_embeddings,
    build_user_embedding,
    compute_similarity_matrix,
    cosine_similarity,
    find_similar_users,
)
from app.ml.research_twin.lstm import (
    LSTMTrainingResult,
    ProductivityLSTM,
    extract_embeddings,
    predict_productivity,
    reload_model,
    train_lstm,
)
from app.ml.research_twin.recommender import (
    Nudge,
    ProcrastinationPattern,
    TimeWindow,
    TwinRecommendation,
    detect_procrastination,
    detect_productive_windows,
    find_submission_windows,
    generate_nudges,
    generate_recommendation,
)
from app.ml.research_twin.scorer import (
    TwinAnalysis,
    analyse,
    analyse_single,
)
from app.ml.research_twin.service import (
    analyse as service_analyse,
    analyse_researcher as service_analyse_researcher,
    generate_synthetic_events,
    get_model_status,
)
from app.ml.research_twin.temporal import (
    BehaviourEvent,
    add_cyclic_encodings,
    apply_rolling_smooth,
    build_multi_researcher,
    build_temporal_features,
    events_to_hourly_rates,
    slice_sequences,
)


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def _isolate_artifacts(tmp_path: Path, monkeypatch):
    """Redirect artifact writes to a temp dir and ensure caches are cleared."""
    monkeypatch.setattr(_cfg, "TWIN_ARTIFACTS_DIR", tmp_path)
    reload_model()
    yield
    reload_model()


def _make_events(
    n_days: int = 14,
    researcher_id: str = "R001",
    seed: int = 42,
    peak_hour: int = 10,
    activity: float = 0.7,
) -> List[BehaviourEvent]:
    """Helper: generate realistic behavioural events for one researcher."""
    rng = np.random.RandomState(seed)
    start = pd.Timestamp("2023-06-01")
    events: List[BehaviourEvent] = []

    for day in range(n_days):
        dt = start + pd.Timedelta(days=day)
        dow = dt.dayofweek
        day_scale = 0.3 if dow >= 5 else 1.0

        for hour in range(24):
            ts = (dt + pd.Timedelta(hours=hour)).isoformat()
            prob = (
                np.exp(-0.5 * ((hour - peak_hour) / 3.0) ** 2)
                * activity
                * day_scale
            )

            if rng.random() < prob * 0.6:
                events.append(BehaviourEvent(
                    timestamp=ts, event_type="writing", researcher_id=researcher_id,
                ))
            if rng.random() < prob * 0.4:
                events.append(BehaviourEvent(
                    timestamp=ts, event_type="revision", researcher_id=researcher_id,
                ))
            if rng.random() < prob * 0.1:
                events.append(BehaviourEvent(
                    timestamp=ts, event_type="opportunity_engagement",
                    researcher_id=researcher_id,
                ))
            if 9 <= hour <= 17 and rng.random() < 0.02 * day_scale:
                events.append(BehaviourEvent(
                    timestamp=ts, event_type="supervision",
                    researcher_id=researcher_id,
                ))

        if rng.random() < 0.15 * day_scale:
            sub_hour = rng.choice([15, 16, 17, 18, 23])
            ts = (dt + pd.Timedelta(hours=sub_hour)).isoformat()
            events.append(BehaviourEvent(
                timestamp=ts, event_type="submission",
                researcher_id=researcher_id,
            ))

    return events


def _make_multi_events(
    n_researchers: int = 3,
    n_days: int = 14,
    seed: int = 42,
) -> List[BehaviourEvent]:
    """Helper: generate events for multiple researchers."""
    rng = np.random.RandomState(seed)
    all_events: List[BehaviourEvent] = []
    for i in range(n_researchers):
        peak = rng.randint(8, 16)
        activity = rng.uniform(0.4, 1.0)
        evts = _make_events(
            n_days=n_days,
            researcher_id=f"R{i:03d}",
            seed=seed + i,
            peak_hour=peak,
            activity=activity,
        )
        all_events.extend(evts)
    return all_events


# ═══════════════════════════════════════════════════════════════════════════
# 1 – CONFIG
# ═══════════════════════════════════════════════════════════════════════════

class TestConfig:
    """Validate all configuration objects."""

    def test_event_types_list(self):
        assert len(EVENT_TYPES) == 5
        for et in EVENT_TYPES:
            assert isinstance(et, str)

    def test_feature_channels_list(self):
        assert len(FEATURE_CHANNELS) == 5
        for ch in FEATURE_CHANNELS:
            assert isinstance(ch, str)

    def test_output_names_list(self):
        assert len(OUTPUT_NAMES) == 4
        for o in OUTPUT_NAMES:
            assert isinstance(o, str)

    def test_temporal_cfg_defaults(self):
        assert TEMPORAL_CFG.bin_hours >= 1
        assert TEMPORAL_CFG.rolling_window >= 1
        assert TEMPORAL_CFG.history_days >= 1

    def test_seq_cfg_defaults(self):
        assert SEQ_CFG.seq_length > 0
        assert SEQ_CFG.stride > 0

    def test_lstm_cfg_defaults(self):
        assert LSTM_CFG.input_size == len(FEATURE_CHANNELS) + 4
        assert LSTM_CFG.hidden_size > 0
        assert LSTM_CFG.num_layers >= 1
        assert 0 <= LSTM_CFG.dropout < 1
        assert LSTM_CFG.output_size > 0
        assert LSTM_CFG.learning_rate > 0
        assert LSTM_CFG.epochs > 0
        assert LSTM_CFG.batch_size > 0

    def test_embed_cfg_defaults(self):
        assert EMBED_CFG.embedding_dim > 0
        assert EMBED_CFG.pca_components >= 0

    def test_recommender_cfg_defaults(self):
        assert 0 < RECOMMENDER_CFG.productive_threshold <= 1
        assert RECOMMENDER_CFG.procrastination_gap_hours >= 1
        assert RECOMMENDER_CFG.top_submission_windows >= 1
        assert RECOMMENDER_CFG.max_nudges >= 1

    def test_artifact_paths(self):
        assert TWIN_ARTIFACTS_DIR is not None
        assert LSTM_FILENAME.endswith(".pt")
        assert METADATA_FILENAME.endswith(".json")

    def test_input_size_matches_channels_plus_cyclic(self):
        """input_size should be feature_channels + 4 cyclic encodings."""
        assert LSTM_CFG.input_size == len(FEATURE_CHANNELS) + 4


# ═══════════════════════════════════════════════════════════════════════════
# 2 – TEMPORAL FEATURE ENGINEERING
# ═══════════════════════════════════════════════════════════════════════════

class TestTemporalFeatures:
    """Validate temporal feature construction pipeline."""

    def test_events_to_hourly_rates_basic(self):
        events = _make_events(n_days=3)
        df = events_to_hourly_rates(events)
        assert not df.empty
        assert set(FEATURE_CHANNELS).issubset(set(df.columns))
        assert isinstance(df.index, pd.DatetimeIndex)

    def test_events_to_hourly_rates_all_channels(self):
        events = _make_events(n_days=7)
        df = events_to_hourly_rates(events)
        for ch in FEATURE_CHANNELS:
            assert ch in df.columns
            assert (df[ch] >= 0).all()

    def test_events_to_hourly_rates_empty(self):
        df = events_to_hourly_rates([])
        assert df.empty

    def test_unknown_event_type_skipped(self):
        events = [
            BehaviourEvent(timestamp="2023-06-01T10:00:00", event_type="unknown"),
        ]
        df = events_to_hourly_rates(events)
        assert df.empty

    def test_cyclic_encodings_shape(self):
        events = _make_events(n_days=3)
        rates = events_to_hourly_rates(events)
        with_cyclic = add_cyclic_encodings(rates)
        assert "hour_sin" in with_cyclic.columns
        assert "hour_cos" in with_cyclic.columns
        assert "dow_sin" in with_cyclic.columns
        assert "dow_cos" in with_cyclic.columns
        assert with_cyclic.shape[1] == len(FEATURE_CHANNELS) + 4

    def test_cyclic_values_bounded(self):
        events = _make_events(n_days=3)
        rates = events_to_hourly_rates(events)
        enc = add_cyclic_encodings(rates)
        for col in ["hour_sin", "hour_cos", "dow_sin", "dow_cos"]:
            assert enc[col].between(-1, 1).all()

    def test_rolling_smooth_reduces_variance(self):
        events = _make_events(n_days=7)
        rates = events_to_hourly_rates(events)
        enc = add_cyclic_encodings(rates)
        smoothed = apply_rolling_smooth(enc)
        # Smoothing should not increase std on any rate channel
        for ch in FEATURE_CHANNELS:
            if ch in rates.columns and rates[ch].std() > 0:
                assert smoothed[ch].std() <= rates[ch].std() + 1e-6

    def test_build_temporal_features_pipeline(self):
        events = _make_events(n_days=7)
        df = build_temporal_features(events)
        assert not df.empty
        assert df.shape[1] == len(FEATURE_CHANNELS) + 4

    def test_build_temporal_features_empty(self):
        df = build_temporal_features([])
        assert df.empty


class TestSequenceSlicing:
    """Validate sequence slicing for LSTM input."""

    def test_slice_basic_shape(self):
        events = _make_events(n_days=14)
        df = build_temporal_features(events)
        seqs = slice_sequences(df)
        assert seqs.ndim == 3
        assert seqs.shape[1] == SEQ_CFG.seq_length
        assert seqs.shape[2] == df.shape[1]

    def test_slice_short_data_pads(self):
        """If data shorter than seq_length, we get 1 padded sequence."""
        events = _make_events(n_days=2)  # ~48h < 168
        df = build_temporal_features(events)
        short_cfg = SequenceConfig(seq_length=168, stride=24)
        seqs = slice_sequences(df, seq_cfg=short_cfg)
        assert seqs.shape[0] == 1
        assert seqs.shape[1] == 168

    def test_slice_stride_overlap(self):
        events = _make_events(n_days=14)
        df = build_temporal_features(events)
        cfg1 = SequenceConfig(seq_length=48, stride=12)
        cfg2 = SequenceConfig(seq_length=48, stride=48)
        seqs1 = slice_sequences(df, seq_cfg=cfg1)
        seqs2 = slice_sequences(df, seq_cfg=cfg2)
        assert seqs1.shape[0] >= seqs2.shape[0]

    def test_slice_sequences_dtype(self):
        events = _make_events(n_days=7)
        df = build_temporal_features(events)
        seqs = slice_sequences(df, seq_cfg=SequenceConfig(seq_length=48, stride=24))
        assert seqs.dtype == np.float32


class TestMultiResearcher:
    """Validate multi-researcher temporal feature building."""

    def test_build_multi_researcher(self):
        events = _make_multi_events(n_researchers=3, n_days=7)
        result = build_multi_researcher(events)
        assert len(result) == 3
        for rid, df in result.items():
            assert isinstance(df, pd.DataFrame)
            assert not df.empty

    def test_build_multi_researcher_assigns_default(self):
        events = [
            BehaviourEvent(timestamp="2023-06-01T10:00:00", event_type="writing"),
            BehaviourEvent(timestamp="2023-06-01T11:00:00", event_type="revision"),
        ]
        result = build_multi_researcher(events)
        assert "__default__" in result


# ═══════════════════════════════════════════════════════════════════════════
# 3 – LSTM MODEL
# ═══════════════════════════════════════════════════════════════════════════

class TestProductivityLSTM:
    """Validate LSTM model architecture."""

    def test_forward_shape(self):
        cfg = LSTMConfig(
            input_size=9, hidden_size=32, num_layers=1,
            dropout=0.0, output_size=24,
        )
        model = ProductivityLSTM(cfg)
        x = torch.randn(4, 48, 9)
        forecast, embedding = model(x)
        assert forecast.shape == (4, 24)
        assert embedding.shape == (4, 32)

    def test_forecast_bounded_0_1(self):
        cfg = LSTMConfig(
            input_size=9, hidden_size=16, num_layers=1,
            dropout=0.0, output_size=12,
        )
        model = ProductivityLSTM(cfg)
        x = torch.randn(8, 24, 9)
        forecast, _ = model(x)
        assert (forecast >= 0).all()
        assert (forecast <= 1).all()

    def test_extract_embedding(self):
        cfg = LSTMConfig(
            input_size=9, hidden_size=16, num_layers=1,
            dropout=0.0, output_size=12,
        )
        model = ProductivityLSTM(cfg)
        x = torch.randn(4, 24, 9)
        emb = model.extract_embedding(x)
        assert emb.shape == (4, 16)

    def test_dropout_only_when_multi_layer(self):
        cfg1 = LSTMConfig(
            input_size=5, hidden_size=8, num_layers=1,
            dropout=0.5, output_size=4,
        )
        model1 = ProductivityLSTM(cfg1)
        assert model1.lstm.dropout == 0.0  # single layer ignores dropout

        cfg2 = LSTMConfig(
            input_size=5, hidden_size=8, num_layers=2,
            dropout=0.5, output_size=4,
        )
        model2 = ProductivityLSTM(cfg2)
        assert model2.lstm.dropout == 0.5


class TestLSTMTraining:
    """Validate LSTM training pipeline."""

    def _make_sequences(self, n=20, seq_len=48, n_feat=9):
        rng = np.random.RandomState(42)
        return rng.randn(n, seq_len, n_feat).astype(np.float32)

    def test_train_lstm_self_supervised(self):
        seqs = self._make_sequences()
        cfg = LSTMConfig(
            input_size=9, hidden_size=16, num_layers=1,
            dropout=0.0, output_size=12, epochs=3, batch_size=8,
        )
        model, result = train_lstm(seqs, cfg=cfg, save=False)
        assert isinstance(model, ProductivityLSTM)
        assert isinstance(result, LSTMTrainingResult)
        assert result.epochs_trained == 3
        assert len(result.history) == 3
        assert result.best_loss <= result.final_loss + 1e-6

    def test_train_lstm_with_targets(self):
        seqs = self._make_sequences(n=16)
        targets = np.random.rand(16, 12).astype(np.float32)
        cfg = LSTMConfig(
            input_size=9, hidden_size=16, num_layers=1,
            dropout=0.0, output_size=12, epochs=2, batch_size=8,
        )
        model, result = train_lstm(seqs, targets=targets, cfg=cfg, save=False)
        assert result.epochs_trained == 2
        assert result.n_sequences == 16

    def test_train_loss_decreases(self):
        seqs = self._make_sequences(n=32, seq_len=48)
        cfg = LSTMConfig(
            input_size=9, hidden_size=32, num_layers=1,
            dropout=0.0, output_size=12, epochs=15, batch_size=16,
        )
        _, result = train_lstm(seqs, cfg=cfg, save=False)
        # Loss should generally decrease (best < first epoch)
        assert result.best_loss <= result.history[0]

    def test_train_saves_model(self, tmp_path):
        seqs = self._make_sequences()
        cfg = LSTMConfig(
            input_size=9, hidden_size=16, num_layers=1,
            dropout=0.0, output_size=12, epochs=2, batch_size=8,
        )
        train_lstm(seqs, cfg=cfg, save=True)
        assert (_cfg.TWIN_ARTIFACTS_DIR / LSTM_FILENAME).exists()
        assert (_cfg.TWIN_ARTIFACTS_DIR / METADATA_FILENAME).exists()

    def test_train_updates_in_memory_cache(self):
        seqs = self._make_sequences()
        cfg = LSTMConfig(
            input_size=9, hidden_size=16, num_layers=1,
            dropout=0.0, output_size=12, epochs=2, batch_size=8,
        )
        model, _ = train_lstm(seqs, cfg=cfg, save=False)
        # predict_productivity should work without save (uses cached model)
        preds = predict_productivity(seqs[:2], model=model)
        assert preds.shape == (2, 12)

    def test_training_result_to_dict(self):
        seqs = self._make_sequences(n=10)
        cfg = LSTMConfig(
            input_size=9, hidden_size=16, num_layers=1,
            dropout=0.0, output_size=12, epochs=2, batch_size=8,
        )
        _, result = train_lstm(seqs, cfg=cfg, save=False)
        d = result.to_dict()
        assert "epochs_trained" in d
        assert "final_loss" in d
        assert "best_loss" in d
        assert "history" in d
        assert len(d["history"]) == 2


class TestLSTMInference:
    """Validate prediction and embedding extraction."""

    def _train_quick(self):
        rng = np.random.RandomState(42)
        seqs = rng.randn(12, 48, 9).astype(np.float32)
        cfg = LSTMConfig(
            input_size=9, hidden_size=16, num_layers=1,
            dropout=0.0, output_size=12, epochs=2, batch_size=8,
        )
        model, _ = train_lstm(seqs, cfg=cfg, save=False)
        return model, seqs

    def test_predict_productivity_shape(self):
        model, seqs = self._train_quick()
        preds = predict_productivity(seqs[:4], model=model)
        assert preds.shape == (4, 12)
        assert np.all(preds >= 0)
        assert np.all(preds <= 1)

    def test_extract_embeddings_shape(self):
        model, seqs = self._train_quick()
        embs = extract_embeddings(seqs[:4], model=model)
        assert embs.shape == (4, 16)

    def test_predict_deterministic(self):
        model, seqs = self._train_quick()
        p1 = predict_productivity(seqs[:2], model=model)
        p2 = predict_productivity(seqs[:2], model=model)
        np.testing.assert_array_almost_equal(p1, p2)

    def test_embeddings_deterministic(self):
        model, seqs = self._train_quick()
        e1 = extract_embeddings(seqs[:2], model=model)
        e2 = extract_embeddings(seqs[:2], model=model)
        np.testing.assert_array_almost_equal(e1, e2)


class TestLSTMPersistence:
    """Validate model save / load cycle."""

    def test_save_load_roundtrip(self):
        rng = np.random.RandomState(42)
        seqs = rng.randn(10, 48, 9).astype(np.float32)
        cfg = LSTMConfig(
            input_size=9, hidden_size=16, num_layers=1,
            dropout=0.0, output_size=12, epochs=2, batch_size=8,
        )
        model, _ = train_lstm(seqs, cfg=cfg, save=True)

        # Predictions before reload
        pred_before = predict_productivity(seqs[:2], model=model)

        # Clear cache and reload
        reload_model()
        pred_after = predict_productivity(seqs[:2])
        np.testing.assert_array_almost_equal(pred_before, pred_after, decimal=4)

    def test_reload_clears_cache(self):
        rng = np.random.RandomState(42)
        seqs = rng.randn(10, 48, 9).astype(np.float32)
        cfg = LSTMConfig(
            input_size=9, hidden_size=16, num_layers=1,
            dropout=0.0, output_size=12, epochs=2, batch_size=8,
        )
        train_lstm(seqs, cfg=cfg, save=True)
        reload_model()
        # Should still be able to predict (loads from disk)
        pred = predict_productivity(seqs[:1])
        assert pred.shape == (1, 12)

    def test_no_model_raises(self):
        reload_model()
        rng = np.random.RandomState(42)
        seqs = rng.randn(2, 48, 9).astype(np.float32)
        with pytest.raises(RuntimeError, match="No trained LSTM"):
            predict_productivity(seqs)


# ═══════════════════════════════════════════════════════════════════════════
# 4 – EMBEDDINGS
# ═══════════════════════════════════════════════════════════════════════════

class TestEmbedding:
    """Validate user embedding extraction and analysis."""

    def test_build_user_embedding_shape(self):
        raw = np.random.randn(5, 64).astype(np.float64)
        emb = build_user_embedding("R001", raw)
        assert emb.researcher_id == "R001"
        assert len(emb.vector) == 64
        assert emb.norm >= 0

    def test_build_user_embedding_mean_pools(self):
        raw = np.ones((3, 16), dtype=np.float64) * 2.0
        emb = build_user_embedding("R001", raw)
        np.testing.assert_array_almost_equal(emb.vector, np.full(16, 2.0))

    def test_pca_truncation(self):
        raw = np.random.randn(5, 64).astype(np.float64)
        cfg = EmbeddingConfig(embedding_dim=64, pca_components=16)
        emb = build_user_embedding("R001", raw, cfg=cfg)
        assert len(emb.vector) == 16

    def test_cosine_similarity_identical(self):
        v = np.array([1.0, 2.0, 3.0])
        assert cosine_similarity(v, v) == pytest.approx(1.0)

    def test_cosine_similarity_orthogonal(self):
        a = np.array([1.0, 0.0])
        b = np.array([0.0, 1.0])
        assert cosine_similarity(a, b) == pytest.approx(0.0)

    def test_cosine_similarity_zero_vector(self):
        a = np.array([1.0, 0.0])
        b = np.zeros(2)
        assert cosine_similarity(a, b) == 0.0

    def test_compute_similarity_matrix_shape(self):
        embeddings = [
            UserEmbedding("R001", np.array([1.0, 0.0]), 1.0),
            UserEmbedding("R002", np.array([0.0, 1.0]), 1.0),
            UserEmbedding("R003", np.array([1.0, 1.0]), math.sqrt(2)),
        ]
        mat = compute_similarity_matrix(embeddings)
        assert mat.shape == (3, 3)
        # Diagonal should be 1.0
        np.testing.assert_array_almost_equal(np.diag(mat), [1.0, 1.0, 1.0])

    def test_similarity_matrix_symmetric(self):
        embeddings = [
            UserEmbedding("R001", np.random.randn(8), 1.0),
            UserEmbedding("R002", np.random.randn(8), 1.0),
        ]
        mat = compute_similarity_matrix(embeddings)
        np.testing.assert_array_almost_equal(mat, mat.T)

    def test_analyse_embeddings_empty(self):
        analysis = analyse_embeddings([])
        assert analysis.embeddings == []
        assert analysis.similarity_matrix.shape == (0, 0)

    def test_analyse_embeddings_structure(self):
        embs = [
            UserEmbedding("R001", np.random.randn(16), 1.0),
            UserEmbedding("R002", np.random.randn(16), 1.0),
        ]
        analysis = analyse_embeddings(embs)
        assert len(analysis.embeddings) == 2
        assert len(analysis.mean_vector) == 16
        assert analysis.similarity_matrix.shape == (2, 2)

    def test_analyse_embeddings_to_dict(self):
        embs = [
            UserEmbedding("R001", np.ones(4), 2.0),
            UserEmbedding("R002", np.zeros(4), 0.0),
        ]
        analysis = analyse_embeddings(embs)
        d = analysis.to_dict()
        assert d["n_users"] == 2
        assert d["embedding_dim"] == 4
        assert len(d["embeddings"]) == 2
        assert len(d["similarity_matrix"]) == 2

    def test_find_similar_users(self):
        target = UserEmbedding("R001", np.array([1.0, 0.0, 0.0]), 1.0)
        candidates = [
            UserEmbedding("R002", np.array([0.9, 0.1, 0.0]), 1.0),  # similar
            UserEmbedding("R003", np.array([0.0, 1.0, 0.0]), 1.0),  # different
            UserEmbedding("R004", np.array([0.95, 0.05, 0.0]), 1.0),  # most similar
        ]
        result = find_similar_users(target, candidates, top_k=2)
        assert len(result) == 2
        assert result[0]["researcher_id"] == "R004"
        assert result[0]["similarity"] > result[1]["similarity"]

    def test_find_similar_excludes_self(self):
        target = UserEmbedding("R001", np.array([1.0, 0.0]), 1.0)
        candidates = [
            target,
            UserEmbedding("R002", np.array([0.5, 0.5]), 1.0),
        ]
        result = find_similar_users(target, candidates, top_k=5)
        ids = [r["researcher_id"] for r in result]
        assert "R001" not in ids

    def test_user_embedding_to_dict(self):
        emb = UserEmbedding("R001", np.array([1.0, 2.0, 3.0]), 3.742)
        d = emb.to_dict()
        assert d["researcher_id"] == "R001"
        assert d["dim"] == 3
        assert isinstance(d["vector"], list)
        assert isinstance(d["norm"], float)


# ═══════════════════════════════════════════════════════════════════════════
# 5 – RECOMMENDER
# ═══════════════════════════════════════════════════════════════════════════

class TestProductiveWindows:
    """Validate productive time-window detection."""

    def test_detect_above_threshold(self):
        # All high → one big window
        forecast = np.ones(24) * 0.8
        windows = detect_productive_windows(forecast)
        assert len(windows) >= 1
        assert windows[0].start_hour == 0
        assert windows[0].end_hour == 23

    def test_detect_below_threshold(self):
        forecast = np.ones(24) * 0.1
        windows = detect_productive_windows(forecast)
        assert len(windows) == 0

    def test_detect_mixed(self):
        forecast = np.zeros(24)
        forecast[9:13] = 0.8
        windows = detect_productive_windows(forecast)
        assert len(windows) >= 1
        assert windows[0].start_hour == 9

    def test_window_score_bounded(self):
        forecast = np.random.rand(24)
        windows = detect_productive_windows(forecast)
        for w in windows:
            assert 0 <= w.score <= 1

    def test_window_to_dict(self):
        tw = TimeWindow(start_hour=9, end_hour=12, day_of_week=None, score=0.85)
        d = tw.to_dict()
        assert d["start_hour"] == 9
        assert d["end_hour"] == 12
        assert d["day_name"] == "any"
        assert abs(d["score"] - 0.85) < 0.01

    def test_window_day_name(self):
        tw = TimeWindow(start_hour=10, end_hour=14, day_of_week=0, score=0.7)
        d = tw.to_dict()
        assert d["day_name"] == "Monday"


class TestProcrastination:
    """Validate procrastination pattern detection."""

    def test_long_idle_detected(self):
        forecast = np.zeros(24)
        patterns = detect_procrastination(forecast)
        types = [p.pattern_type for p in patterns]
        assert "long-idle" in types

    def test_late_surge_detected(self):
        forecast = np.zeros(24)
        forecast[12:] = 0.8
        patterns = detect_procrastination(forecast)
        types = [p.pattern_type for p in patterns]
        assert "late-surge" in types

    def test_morning_avoidance_detected(self):
        forecast = np.full(24, 0.7)
        forecast[9:13] = 0.05  # morning avoidance
        patterns = detect_procrastination(forecast)
        types = [p.pattern_type for p in patterns]
        assert "morning-avoidance" in types

    def test_no_patterns_when_consistent(self):
        forecast = np.full(24, 0.7)
        patterns = detect_procrastination(forecast)
        assert len(patterns) == 0

    def test_pattern_severity_levels(self):
        forecast = np.zeros(24)
        patterns = detect_procrastination(forecast)
        for p in patterns:
            assert p.severity in ("high", "medium", "low")

    def test_pattern_to_dict(self):
        p = ProcrastinationPattern(
            pattern_type="long-idle", description="test",
            severity="high", evidence={"hours": 12},
        )
        d = p.to_dict()
        assert d["pattern_type"] == "long-idle"
        assert d["severity"] == "high"
        assert d["evidence"]["hours"] == 12


class TestSubmissionWindows:
    """Validate submission window selection."""

    def test_returns_top_n(self):
        forecast = np.random.rand(24)
        cfg = RecommenderConfig(top_submission_windows=3)
        windows = find_submission_windows(forecast, cfg=cfg)
        assert len(windows) == 3

    def test_sorted_by_score_descending(self):
        forecast = np.random.rand(24)
        windows = find_submission_windows(forecast)
        scores = [w.score for w in windows]
        assert scores == sorted(scores, reverse=True)

    def test_submission_window_hours_valid(self):
        forecast = np.random.rand(24)
        windows = find_submission_windows(forecast)
        for w in windows:
            assert 0 <= w.start_hour <= 23


class TestNudges:
    """Validate nudge recommendation generation."""

    def test_timing_nudge_from_productive_window(self):
        windows = [TimeWindow(9, 12, None, 0.9)]
        nudges = generate_nudges(windows, [], [])
        assert any(n.category == "timing" for n in nudges)

    def test_consistency_nudge_from_idle(self):
        patterns = [ProcrastinationPattern(
            pattern_type="long-idle", description="test",
            severity="high", evidence={},
        )]
        nudges = generate_nudges([], patterns, [])
        assert any(n.category == "consistency" for n in nudges)

    def test_late_surge_timing_nudge(self):
        patterns = [ProcrastinationPattern(
            pattern_type="late-surge", description="test",
            severity="medium", evidence={},
        )]
        nudges = generate_nudges([], patterns, [])
        assert any(n.category == "timing" for n in nudges)

    def test_submission_nudge(self):
        subs = [TimeWindow(15, 15, None, 0.9)]
        nudges = generate_nudges([], [], subs)
        assert any(n.category == "submission" for n in nudges)

    def test_low_engagement_nudge(self):
        nudges = generate_nudges([], [], [], embedding_norm=0.1)
        assert any(n.category == "engagement" for n in nudges)

    def test_max_nudges_respected(self):
        windows = [TimeWindow(i, i, None, 0.9) for i in range(10)]
        patterns = [
            ProcrastinationPattern("long-idle", "x", "high", {}),
            ProcrastinationPattern("late-surge", "x", "medium", {}),
            ProcrastinationPattern("morning-avoidance", "x", "low", {}),
        ]
        cfg = RecommenderConfig(max_nudges=3)
        nudges = generate_nudges(windows, patterns, windows, cfg=cfg)
        assert len(nudges) <= 3

    def test_nudge_to_dict(self):
        n = Nudge("timing", "Work at 10 AM", "high", "daily_start")
        d = n.to_dict()
        assert d["category"] == "timing"
        assert d["message"] == "Work at 10 AM"
        assert d["priority"] == "high"
        assert d["trigger"] == "daily_start"


class TestGenerateRecommendation:
    """Validate top-level recommendation generation."""

    def test_recommendation_structure(self):
        forecast = np.random.rand(24).astype(np.float32)
        rec = generate_recommendation("R001", forecast, embedding_norm=1.0)
        assert isinstance(rec, TwinRecommendation)
        assert rec.researcher_id == "R001"
        assert isinstance(rec.productive_time_windows, list)
        assert isinstance(rec.procrastination_patterns, list)
        assert isinstance(rec.optimal_submission_windows, list)
        assert isinstance(rec.nudges, list)

    def test_recommendation_to_dict(self):
        forecast = np.random.rand(24).astype(np.float32)
        rec = generate_recommendation("R001", forecast)
        d = rec.to_dict()
        assert d["researcher_id"] == "R001"
        assert "productive_time_window" in d
        assert "procrastination_pattern" in d
        assert "optimal_submission_window" in d
        assert "personalized_nudge_recommendations" in d

    def test_recommendation_with_low_norm_includes_engagement(self):
        forecast = np.full(24, 0.1)
        rec = generate_recommendation("R001", forecast, embedding_norm=0.1)
        nudge_cats = [n.category for n in rec.nudges]
        assert "engagement" in nudge_cats


# ═══════════════════════════════════════════════════════════════════════════
# 6 – SCORER (ORCHESTRATION)
# ═══════════════════════════════════════════════════════════════════════════

class TestScorer:
    """Validate end-to-end Research Twin scoring pipeline."""

    def _fast_lstm_cfg(self):
        return LSTMConfig(
            input_size=9, hidden_size=16, num_layers=1,
            dropout=0.0, output_size=12, epochs=3, batch_size=8,
        )

    def _fast_seq_cfg(self):
        return SequenceConfig(seq_length=48, stride=24)

    def test_analyse_single_researcher(self):
        events = _make_events(n_days=7)
        result = analyse(
            events,
            seq_cfg=self._fast_seq_cfg(),
            lstm_cfg=self._fast_lstm_cfg(),
            save_model=False,
        )
        assert isinstance(result, TwinAnalysis)
        assert result.n_researchers == 1
        assert result.n_events == len(events)
        assert result.training_result is not None
        assert "R001" in result.recommendations

    def test_analyse_multi_researcher(self):
        events = _make_multi_events(n_researchers=3, n_days=7)
        result = analyse(
            events,
            seq_cfg=self._fast_seq_cfg(),
            lstm_cfg=self._fast_lstm_cfg(),
            save_model=False,
        )
        assert result.n_researchers == 3
        assert len(result.recommendations) == 3
        assert result.embedding_analysis is not None
        assert result.embedding_analysis.similarity_matrix.shape == (3, 3)

    def test_analyse_empty_events(self):
        result = analyse([], save_model=False)
        assert result.n_researchers == 0
        assert result.recommendations == {}

    def test_analyse_saves_model_when_requested(self):
        events = _make_events(n_days=7)
        analyse(
            events,
            seq_cfg=self._fast_seq_cfg(),
            lstm_cfg=self._fast_lstm_cfg(),
            save_model=True,
        )
        assert (_cfg.TWIN_ARTIFACTS_DIR / LSTM_FILENAME).exists()

    def test_analyse_to_dict(self):
        events = _make_events(n_days=7)
        result = analyse(
            events,
            seq_cfg=self._fast_seq_cfg(),
            lstm_cfg=self._fast_lstm_cfg(),
            save_model=False,
        )
        d = result.to_dict()
        assert "training_result" in d
        assert "recommendations" in d
        assert "embedding_analysis" in d
        assert "n_events" in d
        assert "n_researchers" in d

    def test_analyse_recommendations_contain_all_outputs(self):
        events = _make_events(n_days=7)
        result = analyse(
            events,
            seq_cfg=self._fast_seq_cfg(),
            lstm_cfg=self._fast_lstm_cfg(),
            save_model=False,
        )
        rec_dict = result.recommendations["R001"].to_dict()
        assert "productive_time_window" in rec_dict
        assert "procrastination_pattern" in rec_dict
        assert "optimal_submission_window" in rec_dict
        assert "personalized_nudge_recommendations" in rec_dict

    def test_analyse_single_convenience(self):
        events = _make_events(n_days=7)
        rec = analyse_single(
            events, "R001",
            seq_cfg=self._fast_seq_cfg(),
            lstm_cfg=self._fast_lstm_cfg(),
            save_model=False,
        )
        assert isinstance(rec, TwinRecommendation)
        assert rec.researcher_id == "R001"

    def test_analyse_single_not_found(self):
        events = _make_events(n_days=7, researcher_id="R001")
        rec = analyse_single(
            events, "DOES_NOT_EXIST",
            seq_cfg=self._fast_seq_cfg(),
            lstm_cfg=self._fast_lstm_cfg(),
            save_model=False,
        )
        assert rec is None

    def test_training_result_loss_is_positive(self):
        events = _make_events(n_days=7)
        result = analyse(
            events,
            seq_cfg=self._fast_seq_cfg(),
            lstm_cfg=self._fast_lstm_cfg(),
            save_model=False,
        )
        assert result.training_result.final_loss > 0
        assert result.training_result.best_loss > 0


# ═══════════════════════════════════════════════════════════════════════════
# 7 – SERVICE LAYER
# ═══════════════════════════════════════════════════════════════════════════

class TestService:
    """Validate public service layer."""

    def _fast_events(self, n_days=7):
        return _make_events(n_days=n_days)

    def test_service_analyse(self):
        events = self._fast_events()
        result = service_analyse(events, save_model=False)
        assert isinstance(result, dict)
        assert "recommendations" in result
        assert "n_events" in result
        assert "n_researchers" in result

    def test_service_analyse_researcher(self):
        events = self._fast_events()
        result = service_analyse_researcher(events, "R001", save_model=False)
        assert isinstance(result, dict)
        assert "researcher_id" in result

    def test_service_analyse_researcher_not_found(self):
        events = self._fast_events()
        result = service_analyse_researcher(events, "MISSING", save_model=False)
        assert "error" in result

    def test_get_model_status_no_model(self):
        status = get_model_status()
        assert status["model_trained"] is False
        assert "model_path" in status
        assert "artifacts_dir" in status

    def test_get_model_status_after_training(self):
        events = self._fast_events()
        service_analyse(events, save_model=True)
        status = get_model_status()
        assert status["model_trained"] is True

    def test_generate_synthetic_events(self):
        synth = generate_synthetic_events(n_researchers=2, n_days=7, seed=42)
        assert synth["n_events"] > 0
        assert len(synth["events"]) == synth["n_events"]
        assert len(synth["researcher_ids"]) == 2

    def test_synthetic_events_deterministic(self):
        s1 = generate_synthetic_events(n_researchers=2, n_days=7, seed=99)
        s2 = generate_synthetic_events(n_researchers=2, n_days=7, seed=99)
        assert s1["n_events"] == s2["n_events"]

    def test_synthetic_event_types_valid(self):
        synth = generate_synthetic_events(n_researchers=1, n_days=10)
        for ev in synth["events"]:
            assert ev.event_type in EVENT_TYPES

    def test_synthetic_researcher_ids(self):
        synth = generate_synthetic_events(n_researchers=3, n_days=5)
        rids = set(ev.researcher_id for ev in synth["events"])
        assert len(rids) == 3

    def test_end_to_end_synthetic_to_analysis(self):
        """Full integration: generate synthetic → analyse → verify output."""
        synth = generate_synthetic_events(n_researchers=2, n_days=10, seed=42)
        result = service_analyse(synth["events"], save_model=False)
        assert result["n_researchers"] == 2
        assert result["training_result"] is not None
        for rid in synth["researcher_ids"]:
            assert rid in result["recommendations"]
            rec = result["recommendations"][rid]
            assert "productive_time_window" in rec
            assert "procrastination_pattern" in rec
            assert "optimal_submission_window" in rec
            assert "personalized_nudge_recommendations" in rec


# ═══════════════════════════════════════════════════════════════════════════
# 8 – PYDANTIC SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════

class TestSchemas:
    """Validate Pydantic request / response schemas."""

    def test_behaviour_event_in(self):
        from app.schemas.research_twin import BehaviourEventIn
        ev = BehaviourEventIn(
            timestamp="2023-06-01T10:00:00",
            event_type="writing",
            researcher_id="R001",
        )
        assert ev.timestamp == "2023-06-01T10:00:00"
        assert ev.event_type == "writing"

    def test_behaviour_event_in_optional_rid(self):
        from app.schemas.research_twin import BehaviourEventIn
        ev = BehaviourEventIn(
            timestamp="2023-06-01T10:00:00",
            event_type="revision",
        )
        assert ev.researcher_id is None

    def test_analyse_request(self):
        from app.schemas.research_twin import AnalyseRequest, BehaviourEventIn
        req = AnalyseRequest(
            events=[
                BehaviourEventIn(
                    timestamp="2023-06-01T10:00:00",
                    event_type="writing",
                ),
            ],
            save_model=False,
        )
        assert len(req.events) == 1

    def test_analyse_request_min_length(self):
        from app.schemas.research_twin import AnalyseRequest
        with pytest.raises(Exception):
            AnalyseRequest(events=[], save_model=True)

    def test_researcher_analyse_request(self):
        from app.schemas.research_twin import ResearcherAnalyseRequest, BehaviourEventIn
        req = ResearcherAnalyseRequest(
            researcher_id="R001",
            events=[
                BehaviourEventIn(
                    timestamp="2023-06-01T10:00:00",
                    event_type="writing",
                ),
            ],
        )
        assert req.researcher_id == "R001"

    def test_synthetic_request_defaults(self):
        from app.schemas.research_twin import SyntheticRequest
        req = SyntheticRequest()
        assert req.n_researchers == 3
        assert req.n_days == 30
        assert req.seed == 42
        assert req.run_analysis is True

    def test_synthetic_request_validation(self):
        from app.schemas.research_twin import SyntheticRequest
        with pytest.raises(Exception):
            SyntheticRequest(n_researchers=0)

    def test_time_window_out(self):
        from app.schemas.research_twin import TimeWindowOut
        tw = TimeWindowOut(start_hour=9, end_hour=12, score=0.85)
        assert tw.start_hour == 9
        assert tw.day_name == "any"

    def test_procrastination_pattern_out(self):
        from app.schemas.research_twin import ProcrastinationPatternOut
        p = ProcrastinationPatternOut(
            pattern_type="long-idle",
            description="…",
            severity="high",
        )
        assert p.pattern_type == "long-idle"

    def test_nudge_out(self):
        from app.schemas.research_twin import NudgeOut
        n = NudgeOut(
            category="timing",
            message="Work at 10 AM",
            priority="high",
            trigger="daily_start",
        )
        assert n.category == "timing"

    def test_recommendation_out(self):
        from app.schemas.research_twin import (
            NudgeOut, ProcrastinationPatternOut, RecommendationOut, TimeWindowOut,
        )
        rec = RecommendationOut(
            researcher_id="R001",
            productive_time_window=[
                TimeWindowOut(start_hour=9, end_hour=12, score=0.85),
            ],
            procrastination_pattern=[],
            optimal_submission_window=[],
            personalized_nudge_recommendations=[
                NudgeOut(
                    category="timing", message="test",
                    priority="high", trigger="daily_start",
                ),
            ],
        )
        assert rec.researcher_id == "R001"

    def test_training_result_out(self):
        from app.schemas.research_twin import TrainingResultOut
        tr = TrainingResultOut(
            epochs_trained=30, final_loss=0.01, best_loss=0.005,
            n_sequences=100, n_features=9, history=[0.1, 0.05, 0.01],
        )
        assert tr.epochs_trained == 30

    def test_embedding_out(self):
        from app.schemas.research_twin import EmbeddingOut
        e = EmbeddingOut(
            researcher_id="R001",
            vector=[0.1, 0.2, 0.3],
            norm=0.374,
            dim=3,
        )
        assert e.dim == 3

    def test_analyse_response(self):
        from app.schemas.research_twin import AnalyseResponse
        resp = AnalyseResponse(
            training_result=None,
            recommendations={},
            n_events=100,
            n_researchers=2,
        )
        assert resp.n_events == 100

    def test_model_status_response(self):
        from app.schemas.research_twin import ModelStatusResponse
        ms = ModelStatusResponse(
            model_trained=False,
            model_path="/tmp/model.pt",
            artifacts_dir="/tmp",
        )
        assert ms.model_trained is False


# ═══════════════════════════════════════════════════════════════════════════
# 9 – API ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

class TestEndpoints:
    """Validate API endpoint contracts (unit-level, no live server)."""

    def test_router_exists(self):
        from app.api.v1.endpoints.research_twin import router
        assert router is not None

    def test_router_has_analyse_route(self):
        from app.api.v1.endpoints.research_twin import router
        paths = [r.path for r in router.routes]
        assert "/analyse" in paths

    def test_router_has_researcher_route(self):
        from app.api.v1.endpoints.research_twin import router
        paths = [r.path for r in router.routes]
        assert "/analyse/researcher" in paths

    def test_router_has_synthetic_route(self):
        from app.api.v1.endpoints.research_twin import router
        paths = [r.path for r in router.routes]
        assert "/synthetic" in paths

    def test_router_has_status_route(self):
        from app.api.v1.endpoints.research_twin import router
        paths = [r.path for r in router.routes]
        assert "/status" in paths

    def test_router_registered_in_api(self):
        from app.api.v1 import api_router
        prefixes = [r.path for r in api_router.routes if hasattr(r, "path")]
        # The mount prefix `/research-twin` should appear
        assert any("research-twin" in p for p in prefixes)


# ═══════════════════════════════════════════════════════════════════════════
# 10 – INVARIANTS & CROSS-CUTTING
# ═══════════════════════════════════════════════════════════════════════════

class TestInvariants:
    """Cross-cutting invariant checks."""

    def test_event_to_channel_mapping_complete(self):
        """Every event type should map to a feature channel."""
        from app.ml.research_twin.temporal import _EVENT_TO_CHANNEL
        for et in EVENT_TYPES:
            assert et in _EVENT_TO_CHANNEL

    def test_feature_channels_in_temporal_output(self):
        events = _make_events(n_days=3)
        df = build_temporal_features(events)
        for ch in FEATURE_CHANNELS:
            assert ch in df.columns

    def test_all_rate_columns_non_negative(self):
        events = _make_events(n_days=7)
        df = build_temporal_features(events)
        for ch in FEATURE_CHANNELS:
            assert (df[ch] >= 0).all()

    def test_forecast_range_after_full_pipeline(self):
        events = _make_events(n_days=7)
        features = build_temporal_features(events)
        seqs = slice_sequences(features, seq_cfg=SequenceConfig(seq_length=48, stride=24))
        cfg = LSTMConfig(
            input_size=seqs.shape[2], hidden_size=16, num_layers=1,
            dropout=0.0, output_size=12, epochs=2, batch_size=8,
        )
        model, _ = train_lstm(seqs, cfg=cfg, save=False)
        preds = predict_productivity(seqs, model=model)
        assert np.all(preds >= 0)
        assert np.all(preds <= 1)

    def test_embedding_norm_non_negative(self):
        events = _make_events(n_days=7)
        features = build_temporal_features(events)
        seqs = slice_sequences(features, seq_cfg=SequenceConfig(seq_length=48, stride=24))
        cfg = LSTMConfig(
            input_size=seqs.shape[2], hidden_size=16, num_layers=1,
            dropout=0.0, output_size=12, epochs=2, batch_size=8,
        )
        model, _ = train_lstm(seqs, cfg=cfg, save=False)
        raw = extract_embeddings(seqs, model=model)
        emb = build_user_embedding("R001", raw)
        assert emb.norm >= 0

    def test_similarity_diagonal_is_one(self):
        embs = [
            UserEmbedding("R001", np.random.randn(16), 1.0),
            UserEmbedding("R002", np.random.randn(16), 1.0),
            UserEmbedding("R003", np.random.randn(16), 1.0),
        ]
        mat = compute_similarity_matrix(embs)
        np.testing.assert_array_almost_equal(np.diag(mat), np.ones(3))

    def test_similarity_bounded(self):
        embs = [
            UserEmbedding("R001", np.random.randn(16), 1.0),
            UserEmbedding("R002", np.random.randn(16), 1.0),
        ]
        mat = compute_similarity_matrix(embs)
        assert np.all(mat >= -1 - 1e-6)
        assert np.all(mat <= 1 + 1e-6)

    def test_recommendation_all_four_output_keys(self):
        """Every recommendation dict must have the four output keys."""
        events = _make_events(n_days=7)
        seq_cfg = SequenceConfig(seq_length=48, stride=24)
        lstm_cfg = LSTMConfig(
            input_size=9, hidden_size=16, num_layers=1,
            dropout=0.0, output_size=12, epochs=2, batch_size=8,
        )
        result = analyse(events, seq_cfg=seq_cfg, lstm_cfg=lstm_cfg, save_model=False)
        for rid, rec in result.recommendations.items():
            d = rec.to_dict()
            for key in OUTPUT_NAMES:
                assert key in d, f"Missing '{key}' in recommendation for {rid}"

    def test_idempotent_analysis(self):
        """Same events + same seed → same n_researchers, n_events."""
        events = _make_events(n_days=7, seed=42)
        seq_cfg = SequenceConfig(seq_length=48, stride=24)
        lstm_cfg = LSTMConfig(
            input_size=9, hidden_size=16, num_layers=1,
            dropout=0.0, output_size=12, epochs=2, batch_size=8,
        )
        r1 = analyse(events, seq_cfg=seq_cfg, lstm_cfg=lstm_cfg, save_model=False)
        reload_model()
        r2 = analyse(events, seq_cfg=seq_cfg, lstm_cfg=lstm_cfg, save_model=False)
        assert r1.n_events == r2.n_events
        assert r1.n_researchers == r2.n_researchers

    def test_twin_analysis_to_dict_serialisable(self):
        """to_dict() output should be JSON-serialisable."""
        events = _make_events(n_days=7)
        seq_cfg = SequenceConfig(seq_length=48, stride=24)
        lstm_cfg = LSTMConfig(
            input_size=9, hidden_size=16, num_layers=1,
            dropout=0.0, output_size=12, epochs=2, batch_size=8,
        )
        result = analyse(events, seq_cfg=seq_cfg, lstm_cfg=lstm_cfg, save_model=False)
        d = result.to_dict()
        json_str = json.dumps(d)
        assert isinstance(json_str, str)

    def test_metadata_file_valid_json(self):
        events = _make_events(n_days=7)
        seq_cfg = SequenceConfig(seq_length=48, stride=24)
        lstm_cfg = LSTMConfig(
            input_size=9, hidden_size=16, num_layers=1,
            dropout=0.0, output_size=12, epochs=2, batch_size=8,
        )
        analyse(events, seq_cfg=seq_cfg, lstm_cfg=lstm_cfg, save_model=True)
        meta_path = _cfg.TWIN_ARTIFACTS_DIR / METADATA_FILENAME
        assert meta_path.exists()
        meta = json.loads(meta_path.read_text())
        assert "epochs_trained" in meta
        assert "final_loss" in meta
