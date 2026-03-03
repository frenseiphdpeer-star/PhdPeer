"""
Comprehensive test suite for the Cross-Feature Intelligence Fusion Engine.

Covers:
 • config validation
 • signal alignment (temporal)
 • lag / rolling / roc feature engineering
 • correlation matrix computation
 • multi-target LightGBM training & prediction
 • feature importance ranking
 • automated insight generation
 • scorer orchestration
 • service layer + synthetic data
 • schemas & API endpoint contracts
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

# ---------------------------------------------------------------------------
# Module imports
# ---------------------------------------------------------------------------
from app.ml.fusion_engine import config as _cfg
from app.ml.fusion_engine.config import (
    FUSION_ARTIFACTS_DIR,
    HYPERPARAMS,
    INSIGHT_CFG,
    LAGS,
    LagConfig,
    LGBMFusionParams,
    InsightConfig,
    METADATA_FILENAME,
    MODEL_FILENAME,
    SIGNAL_NAMES,
    TARGET_NAMES,
    TEMPORAL,
    TemporalConfig,
)
from app.ml.fusion_engine.features import (
    CorrelationMatrix,
    build_lag_features,
    compute_correlation_matrix,
)
from app.ml.fusion_engine.insights import (
    Insight,
    _correlation_insights,
    _extract_base_signal,
    _extract_lag_period,
    _extract_lag_type,
    _leading_indicator_insights,
    _model_quality_insights,
    _predictor_insights,
    generate_insights,
)
from app.ml.fusion_engine.model import (
    FusionPrediction,
    FusionTrainingResult,
    TargetMetrics,
    predict,
    rank_feature_importance,
    reload_models,
    train,
)
from app.ml.fusion_engine.scorer import (
    FusionAnalysis,
    analyse,
    analyse_from_dataframe,
)
from app.ml.fusion_engine.service import (
    analyse as service_analyse,
    analyse_dataframe as service_analyse_dataframe,
    generate_synthetic_dataset,
    get_model_status,
)
from app.ml.fusion_engine.signals import (
    SignalObservation,
    align_multi_researcher,
    align_signals,
)


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def _isolate_artifacts(tmp_path: Path, monkeypatch):
    """Redirect artifact writes to a temp dir and ensure caches are cleared."""
    monkeypatch.setattr(_cfg, "FUSION_ARTIFACTS_DIR", tmp_path)
    reload_models()
    yield
    reload_models()


def _make_observations(
    n_weeks: int = 30,
    signals: List[str] | None = None,
    targets: List[str] | None = None,
    researcher_id: str | None = None,
    seed: int = 42,
) -> List[SignalObservation]:
    """Helper: generate weekly signal observations."""
    rng = np.random.RandomState(seed)
    sigs = signals or SIGNAL_NAMES
    tgts = targets or TARGET_NAMES
    start = pd.Timestamp("2023-01-01")
    obs: List[SignalObservation] = []

    for week in range(n_weeks):
        ts = (start + pd.Timedelta(weeks=week)).isoformat()
        for sig in sigs:
            obs.append(SignalObservation(
                timestamp=ts,
                signal_name=sig,
                value=float(rng.rand()),
                researcher_id=researcher_id,
            ))
        for tgt in tgts:
            obs.append(SignalObservation(
                timestamp=ts,
                signal_name=tgt,
                value=float(rng.rand()),
                researcher_id=researcher_id,
            ))
    return obs


def _make_aligned_df(
    n_weeks: int = 30,
    seed: int = 42,
) -> pd.DataFrame:
    """Helper: build an already-aligned DataFrame with signals + targets."""
    rng = np.random.RandomState(seed)
    index = pd.date_range("2023-01-01", periods=n_weeks, freq="W")
    data = {}
    for sig in SIGNAL_NAMES:
        data[sig] = rng.rand(n_weeks)
    for tgt in TARGET_NAMES:
        data[tgt] = rng.rand(n_weeks)
    return pd.DataFrame(data, index=index)


# ═══════════════════════════════════════════════════════════════════════════
# 1. Config tests
# ═══════════════════════════════════════════════════════════════════════════

class TestConfig:
    """Verify configuration constants and dataclass defaults."""

    def test_signal_names_count(self):
        assert len(SIGNAL_NAMES) == 6

    def test_target_names_count(self):
        assert len(TARGET_NAMES) == 3

    def test_signal_names_are_strings(self):
        for s in SIGNAL_NAMES:
            assert isinstance(s, str) and len(s) > 0

    def test_target_names_are_strings(self):
        for t in TARGET_NAMES:
            assert isinstance(t, str) and len(t) > 0

    def test_no_overlap(self):
        assert set(SIGNAL_NAMES).isdisjoint(set(TARGET_NAMES))

    def test_temporal_defaults(self):
        assert TEMPORAL.resample_period == "W"
        assert TEMPORAL.aggregation == "mean"
        assert TEMPORAL.ffill_limit == 4

    def test_lag_defaults(self):
        assert LAGS.lag_periods == [1, 2, 4]
        assert LAGS.rolling_windows == [3, 6]
        assert LAGS.roc_periods == [1, 3]

    def test_hyperparams_defaults(self):
        assert HYPERPARAMS.n_estimators == 200
        assert HYPERPARAMS.learning_rate == 0.05
        assert HYPERPARAMS.max_depth == 5
        assert HYPERPARAMS.n_jobs == 1  # macOS safe
        assert HYPERPARAMS.verbosity == -1

    def test_hyperparams_to_dict(self):
        d = HYPERPARAMS.to_dict()
        assert isinstance(d, dict)
        assert d["n_estimators"] == 200
        assert d["n_jobs"] == 1

    def test_insight_defaults(self):
        assert INSIGHT_CFG.strong_correlation == 0.6
        assert INSIGHT_CFG.moderate_correlation == 0.3
        assert INSIGHT_CFG.top_importance_threshold == 0.08
        assert INSIGHT_CFG.max_insights == 20

    def test_artifact_paths(self):
        assert MODEL_FILENAME.endswith(".joblib")
        assert METADATA_FILENAME.endswith(".json")


# ═══════════════════════════════════════════════════════════════════════════
# 2. Signal alignment tests
# ═══════════════════════════════════════════════════════════════════════════

class TestSignalAlignment:
    """Verify temporal alignment of raw observations."""

    def test_empty_observations(self):
        df = align_signals([])
        assert df.empty

    def test_unknown_signal_skipped(self):
        obs = [
            SignalObservation(
                timestamp="2023-01-01", signal_name="nonexistent", value=1.0,
            ),
        ]
        df = align_signals(obs)
        assert df.empty

    def test_single_signal_alignment(self):
        obs = _make_observations(n_weeks=10, signals=["writing_coherence"], targets=[])
        df = align_signals(obs)
        assert not df.empty
        assert "writing_coherence" in df.columns

    def test_all_signals_present(self):
        obs = _make_observations(n_weeks=20, targets=[])
        df = align_signals(obs)
        for sig in SIGNAL_NAMES:
            assert sig in df.columns

    def test_targets_preserved(self):
        """Targets in observations should survive alignment."""
        obs = _make_observations(n_weeks=20)
        df = align_signals(obs)
        for tgt in TARGET_NAMES:
            assert tgt in df.columns

    def test_regular_time_index(self):
        obs = _make_observations(n_weeks=15, targets=[])
        df = align_signals(obs)
        assert isinstance(df.index, pd.DatetimeIndex)

    def test_forward_fill_works(self):
        """Create gaps and verify ffill up to limit."""
        obs = []
        start = pd.Timestamp("2023-01-01")
        for w in range(20):
            ts = (start + pd.Timedelta(weeks=w)).isoformat()
            # Only report every 3rd week for one signal
            if w % 3 == 0:
                obs.append(SignalObservation(
                    timestamp=ts,
                    signal_name="writing_coherence",
                    value=float(w),
                ))
            # Always report another
            obs.append(SignalObservation(
                timestamp=ts,
                signal_name="health_score",
                value=50.0,
            ))
        df = align_signals(obs, min_coverage=0.3)
        # writing_coherence should have some ffilled values
        assert not df.empty
        assert df["writing_coherence"].notna().sum() > 5

    def test_min_coverage_filter(self):
        """With high min_coverage, sparse data rows should be dropped."""
        obs = [
            SignalObservation(
                timestamp="2023-01-01",
                signal_name="writing_coherence",
                value=0.8,
            ),
        ]
        df = align_signals(obs, min_coverage=1.0)
        # Only 1 signal, 1 row, coverage = 1/1 = 100% → should survive
        assert len(df) >= 1

    def test_custom_temporal_config(self):
        obs = _make_observations(n_weeks=30, targets=[])
        cfg = TemporalConfig(resample_period="2W", aggregation="mean", ffill_limit=2)
        df = align_signals(obs, config=cfg)
        assert not df.empty
        # ~15 periods for 30 weeks with 2W resample
        assert len(df) <= 20

    def test_multi_researcher(self):
        obs_a = _make_observations(n_weeks=10, targets=[], researcher_id="R001")
        obs_b = _make_observations(n_weeks=12, targets=[], researcher_id="R002", seed=99)
        result = align_multi_researcher(obs_a + obs_b)
        assert "R001" in result
        assert "R002" in result
        assert isinstance(result["R001"], pd.DataFrame)

    def test_multi_researcher_default_id(self):
        """Observations without researcher_id go to __default__."""
        obs = _make_observations(n_weeks=10, targets=[])
        result = align_multi_researcher(obs)
        assert "__default__" in result


# ═══════════════════════════════════════════════════════════════════════════
# 3. Feature engineering tests
# ═══════════════════════════════════════════════════════════════════════════

class TestFeatureEngineering:
    """Verify lag, rolling, and roc feature construction."""

    def test_build_features_shape(self):
        df = _make_aligned_df(n_weeks=30)
        featured, feat_names = build_lag_features(df)
        assert len(feat_names) > len(SIGNAL_NAMES)
        assert len(featured) < 30  # rows removed by lag

    def test_feature_names_exclude_targets(self):
        df = _make_aligned_df()
        _, feat_names = build_lag_features(df)
        for tgt in TARGET_NAMES:
            assert tgt not in feat_names

    def test_lag_columns_created(self):
        df = _make_aligned_df()
        featured, feat_names = build_lag_features(df)
        for sig in SIGNAL_NAMES:
            for lag in LAGS.lag_periods:
                assert f"{sig}_lag_{lag}" in feat_names

    def test_rolling_columns_created(self):
        df = _make_aligned_df()
        featured, feat_names = build_lag_features(df)
        for sig in SIGNAL_NAMES:
            for win in LAGS.rolling_windows:
                assert f"{sig}_roll_{win}" in feat_names

    def test_roc_columns_created(self):
        df = _make_aligned_df()
        featured, feat_names = build_lag_features(df)
        for sig in SIGNAL_NAMES:
            for roc in LAGS.roc_periods:
                assert f"{sig}_roc_{roc}" in feat_names

    def test_no_nans_in_features(self):
        df = _make_aligned_df()
        featured, feat_names = build_lag_features(df)
        assert featured[feat_names].isna().sum().sum() == 0

    def test_feature_count(self):
        """Verify total feature count matches formula."""
        df = _make_aligned_df()
        _, feat_names = build_lag_features(df)
        n_sig = len(SIGNAL_NAMES)
        expected = n_sig * (
            1 + len(LAGS.lag_periods)
            + len(LAGS.rolling_windows)
            + len(LAGS.roc_periods)
        )
        assert len(feat_names) == expected

    def test_custom_lag_config(self):
        df = _make_aligned_df()
        custom = LagConfig(
            lag_periods=[1],
            rolling_windows=[2],
            roc_periods=[1],
        )
        _, feat_names = build_lag_features(df, lag_config=custom)
        n_sig = len(SIGNAL_NAMES)
        expected = n_sig * (1 + 1 + 1 + 1)
        assert len(feat_names) == expected

    def test_targets_preserved_in_featured(self):
        df = _make_aligned_df()
        featured, _ = build_lag_features(df)
        for tgt in TARGET_NAMES:
            assert tgt in featured.columns


# ═══════════════════════════════════════════════════════════════════════════
# 4. Correlation matrix tests
# ═══════════════════════════════════════════════════════════════════════════

class TestCorrelationMatrix:
    """Verify pair-wise Pearson correlation computation."""

    def test_shape(self):
        df = _make_aligned_df()
        corr = compute_correlation_matrix(df)
        assert corr.matrix.shape == (len(SIGNAL_NAMES), len(SIGNAL_NAMES))

    def test_diagonal_is_one(self):
        df = _make_aligned_df()
        corr = compute_correlation_matrix(df)
        for sig in corr.signal_names:
            assert abs(corr.matrix.loc[sig, sig] - 1.0) < 1e-6

    def test_symmetric(self):
        df = _make_aligned_df()
        corr = compute_correlation_matrix(df)
        mat = corr.matrix.values
        np.testing.assert_allclose(mat, mat.T, atol=1e-10)

    def test_values_in_range(self):
        df = _make_aligned_df()
        corr = compute_correlation_matrix(df)
        assert (corr.matrix.values >= -1.0001).all()
        assert (corr.matrix.values <= 1.0001).all()

    def test_to_dict(self):
        df = _make_aligned_df()
        corr = compute_correlation_matrix(df)
        d = corr.to_dict()
        assert "signal_names" in d
        assert "matrix" in d
        assert isinstance(d["matrix"], dict)

    def test_strongest_pairs(self):
        df = _make_aligned_df()
        corr = compute_correlation_matrix(df)
        pairs = corr.strongest_pairs(threshold=0.0, top_k=5)
        assert len(pairs) <= 5
        for p in pairs:
            assert "signal_a" in p
            assert "signal_b" in p
            assert "correlation" in p

    def test_strongest_pairs_sorted_desc(self):
        df = _make_aligned_df()
        corr = compute_correlation_matrix(df)
        pairs = corr.strongest_pairs(threshold=0.0, top_k=20)
        for i in range(1, len(pairs)):
            assert pairs[i]["abs_correlation"] <= pairs[i - 1]["abs_correlation"]

    def test_single_signal_identity(self):
        df = pd.DataFrame({"writing_coherence": [0.5, 0.6, 0.7]})
        corr = compute_correlation_matrix(df)
        assert len(corr.signal_names) == 1
        assert abs(corr.matrix.iloc[0, 0] - 1.0) < 1e-6


# ═══════════════════════════════════════════════════════════════════════════
# 5. Model training tests
# ═══════════════════════════════════════════════════════════════════════════

class TestModelTraining:
    """Verify multi-target LightGBM training."""

    def test_train_returns_result(self):
        df = _make_aligned_df(n_weeks=30)
        featured, feat_names = build_lag_features(df)
        result = train(featured, feat_names, save=False)
        assert isinstance(result, FusionTrainingResult)

    def test_metrics_per_target(self):
        df = _make_aligned_df(n_weeks=30)
        featured, feat_names = build_lag_features(df)
        result = train(featured, feat_names, save=False)
        targets_trained = {m.target for m in result.target_metrics}
        for tgt in TARGET_NAMES:
            assert tgt in targets_trained

    def test_r2_is_finite(self):
        df = _make_aligned_df(n_weeks=30)
        featured, feat_names = build_lag_features(df)
        result = train(featured, feat_names, save=False)
        for m in result.target_metrics:
            assert math.isfinite(m.r2)

    def test_mae_non_negative(self):
        df = _make_aligned_df(n_weeks=30)
        featured, feat_names = build_lag_features(df)
        result = train(featured, feat_names, save=False)
        for m in result.target_metrics:
            assert m.mae >= 0

    def test_rmse_non_negative(self):
        df = _make_aligned_df(n_weeks=30)
        featured, feat_names = build_lag_features(df)
        result = train(featured, feat_names, save=False)
        for m in result.target_metrics:
            assert m.rmse >= 0

    def test_feature_importances_present(self):
        df = _make_aligned_df(n_weeks=30)
        featured, feat_names = build_lag_features(df)
        result = train(featured, feat_names, save=False)
        assert len(result.feature_importances) >= 1
        for tgt, imp in result.feature_importances.items():
            assert len(imp) == len(feat_names)

    def test_to_dict(self):
        df = _make_aligned_df(n_weeks=30)
        featured, feat_names = build_lag_features(df)
        result = train(featured, feat_names, save=False)
        d = result.to_dict()
        assert "target_metrics" in d
        assert "feature_importances" in d
        assert "n_samples" in d

    def test_model_save_and_load(self):
        df = _make_aligned_df(n_weeks=30)
        featured, feat_names = build_lag_features(df)
        result = train(featured, feat_names, save=True)
        # Files should exist
        assert (_cfg.FUSION_ARTIFACTS_DIR / MODEL_FILENAME).exists()
        assert (_cfg.FUSION_ARTIFACTS_DIR / METADATA_FILENAME).exists()

    def test_no_target_columns_raises(self):
        df = _make_aligned_df(n_weeks=30)
        featured, feat_names = build_lag_features(df)
        # Remove all targets
        for tgt in TARGET_NAMES:
            if tgt in featured.columns:
                featured = featured.drop(columns=[tgt])
        with pytest.raises(ValueError, match="No target"):
            train(featured, feat_names, save=False)

    def test_small_dataset_no_split(self):
        """With <10 samples, train on full data."""
        df = _make_aligned_df(n_weeks=10)
        featured, feat_names = build_lag_features(df)
        # Very few rows after lag
        result = train(featured, feat_names, save=False)
        # Should still produce metrics
        assert len(result.target_metrics) > 0

    def test_deterministic_training(self):
        """Same data → same metrics."""
        df = _make_aligned_df(n_weeks=30)
        featured, feat_names = build_lag_features(df)
        r1 = train(featured, feat_names, save=False)
        reload_models()
        r2 = train(featured, feat_names, save=False)
        for m1, m2 in zip(r1.target_metrics, r2.target_metrics):
            assert abs(m1.r2 - m2.r2) < 1e-6

    def test_custom_params(self):
        df = _make_aligned_df(n_weeks=30)
        featured, feat_names = build_lag_features(df)
        hp = LGBMFusionParams(n_estimators=50, learning_rate=0.1, max_depth=3)
        result = train(featured, feat_names, params=hp, save=False)
        assert isinstance(result, FusionTrainingResult)

    def test_custom_test_size(self):
        df = _make_aligned_df(n_weeks=30)
        featured, feat_names = build_lag_features(df)
        result = train(featured, feat_names, test_size=0.3, save=False)
        assert isinstance(result, FusionTrainingResult)


# ═══════════════════════════════════════════════════════════════════════════
# 6. Prediction tests
# ═══════════════════════════════════════════════════════════════════════════

class TestPrediction:
    """Verify multi-target prediction."""

    def test_predict_after_train(self):
        df = _make_aligned_df(n_weeks=30)
        featured, feat_names = build_lag_features(df)
        train(featured, feat_names, save=True)
        reload_models()
        preds = predict(featured, feat_names)
        assert len(preds) == len(featured)

    def test_prediction_has_all_targets(self):
        df = _make_aligned_df(n_weeks=30)
        featured, feat_names = build_lag_features(df)
        train(featured, feat_names, save=True)
        reload_models()
        preds = predict(featured, feat_names)
        for p in preds:
            for tgt in TARGET_NAMES:
                assert tgt in p.predictions

    def test_prediction_values_finite(self):
        df = _make_aligned_df(n_weeks=30)
        featured, feat_names = build_lag_features(df)
        train(featured, feat_names, save=True)
        reload_models()
        preds = predict(featured, feat_names)
        for p in preds:
            for v in p.predictions.values():
                assert math.isfinite(v)

    def test_predict_with_bundle_injection(self):
        """Use _bundle parameter to avoid disk persistence."""
        df = _make_aligned_df(n_weeks=30)
        featured, feat_names = build_lag_features(df)
        result = train(featured, feat_names, save=True)
        reload_models()
        # Load the bundle manually
        import joblib
        bundle = joblib.load(_cfg.FUSION_ARTIFACTS_DIR / MODEL_FILENAME)
        preds = predict(featured, feat_names, _bundle=bundle)
        assert len(preds) > 0

    def test_predict_without_training_raises(self):
        df = _make_aligned_df(n_weeks=30)
        featured, feat_names = build_lag_features(df)
        reload_models()
        with pytest.raises(RuntimeError, match="No trained"):
            predict(featured, feat_names)

    def test_prediction_to_dict(self):
        df = _make_aligned_df(n_weeks=30)
        featured, feat_names = build_lag_features(df)
        train(featured, feat_names, save=True)
        reload_models()
        preds = predict(featured, feat_names)
        d = preds[0].to_dict()
        assert isinstance(d, dict)
        for v in d.values():
            assert isinstance(v, float)


# ═══════════════════════════════════════════════════════════════════════════
# 7. Feature importance ranking tests
# ═══════════════════════════════════════════════════════════════════════════

class TestFeatureImportanceRanking:
    """Verify feature importance ranking."""

    def _train_result(self) -> FusionTrainingResult:
        df = _make_aligned_df(n_weeks=30)
        featured, feat_names = build_lag_features(df)
        return train(featured, feat_names, save=False)

    def test_ranked_desc_by_importance(self):
        result = self._train_result()
        ranked = rank_feature_importance(result)
        for i in range(1, len(ranked)):
            assert ranked[i]["importance"] <= ranked[i - 1]["importance"]

    def test_per_target_ranking(self):
        result = self._train_result()
        for tgt in TARGET_NAMES:
            ranked = rank_feature_importance(result, target=tgt)
            assert len(ranked) > 0
            assert ranked[0]["rank"] == 1

    def test_relative_importance_sums_to_one(self):
        result = self._train_result()
        ranked = rank_feature_importance(result)
        total = sum(r["relative_importance"] for r in ranked)
        assert abs(total - 1.0) < 0.01

    def test_rank_is_sequential(self):
        result = self._train_result()
        ranked = rank_feature_importance(result)
        for i, r in enumerate(ranked):
            assert r["rank"] == i + 1


# ═══════════════════════════════════════════════════════════════════════════
# 8. Insight generation tests
# ═══════════════════════════════════════════════════════════════════════════

class TestInsightGeneration:
    """Verify automated insight generation."""

    # ── Helper extraction ─────────────────────────────────────────────

    def test_extract_base_signal_known(self):
        assert _extract_base_signal("writing_coherence_lag_2") == "writing_coherence"

    def test_extract_base_signal_unknown(self):
        assert _extract_base_signal("unknown_feature") == "unknown_feature"

    def test_extract_lag_type_lag(self):
        assert _extract_lag_type("writing_coherence_lag_2") == "lag-2"

    def test_extract_lag_type_roll(self):
        assert _extract_lag_type("health_score_roll_3") == "rolling-3"

    def test_extract_lag_type_roc(self):
        assert _extract_lag_type("network_centrality_roc_1") == "rate-of-change-1"

    def test_extract_lag_type_base(self):
        assert _extract_lag_type("writing_coherence") is None

    def test_extract_lag_period(self):
        assert _extract_lag_period("writing_coherence_lag_4") == 4

    def test_extract_lag_period_none_for_base(self):
        assert _extract_lag_period("writing_coherence") is None

    # ── Correlation insights ──────────────────────────────────────────

    def test_correlation_insights_from_strong(self):
        """A perfect correlation should produce a high-priority insight."""
        mat = pd.DataFrame(
            [[1.0, 0.9], [0.9, 1.0]],
            index=["writing_coherence", "health_score"],
            columns=["writing_coherence", "health_score"],
        )
        corr = CorrelationMatrix(
            matrix=mat,
            signal_names=["writing_coherence", "health_score"],
        )
        insights = _correlation_insights(corr, INSIGHT_CFG)
        assert len(insights) >= 1
        assert insights[0].priority == "high"
        assert insights[0].category == "correlation"

    def test_correlation_insights_moderate(self):
        mat = pd.DataFrame(
            [[1.0, 0.4], [0.4, 1.0]],
            index=["writing_coherence", "health_score"],
            columns=["writing_coherence", "health_score"],
        )
        corr = CorrelationMatrix(
            matrix=mat,
            signal_names=["writing_coherence", "health_score"],
        )
        insights = _correlation_insights(corr, INSIGHT_CFG)
        assert len(insights) >= 1
        assert insights[0].priority == "medium"

    def test_correlation_insights_weak_skipped(self):
        mat = pd.DataFrame(
            [[1.0, 0.1], [0.1, 1.0]],
            index=["writing_coherence", "health_score"],
            columns=["writing_coherence", "health_score"],
        )
        corr = CorrelationMatrix(
            matrix=mat,
            signal_names=["writing_coherence", "health_score"],
        )
        insights = _correlation_insights(corr, INSIGHT_CFG)
        assert len(insights) == 0

    # ── Predictor insights ────────────────────────────────────────────

    def test_predictor_insights_exist(self):
        df = _make_aligned_df(n_weeks=30)
        featured, feat_names = build_lag_features(df)
        result = train(featured, feat_names, save=False)
        insights = _predictor_insights(result, INSIGHT_CFG)
        # At least some features should be above threshold
        assert len(insights) >= 1

    # ── Model quality insights ────────────────────────────────────────

    def test_model_quality_high_r2(self):
        m = TargetMetrics(
            target="publication_success", r2=0.85, mae=0.1, rmse=0.12,
            n_train=100, n_test=25,
        )
        result = FusionTrainingResult(
            target_metrics=[m],
            feature_importances={"publication_success": {}},
            feature_names=[], n_samples=125, n_features=10,
        )
        insights = _model_quality_insights(result)
        assert any(i.priority == "high" for i in insights)

    def test_model_quality_low_r2(self):
        m = TargetMetrics(
            target="dropout_risk", r2=0.02, mae=0.5, rmse=0.6,
            n_train=100, n_test=25,
        )
        result = FusionTrainingResult(
            target_metrics=[m],
            feature_importances={"dropout_risk": {}},
            feature_names=[], n_samples=125, n_features=10,
        )
        insights = _model_quality_insights(result)
        assert any("low predictive" in i.message for i in insights)

    # ── Top-level generate_insights ───────────────────────────────────

    def test_generate_insights_empty_inputs(self):
        insights = generate_insights()
        assert insights == []

    def test_generate_insights_with_correlation_only(self):
        mat = pd.DataFrame(
            [[1.0, 0.8], [0.8, 1.0]],
            index=["writing_coherence", "health_score"],
            columns=["writing_coherence", "health_score"],
        )
        corr = CorrelationMatrix(
            matrix=mat,
            signal_names=["writing_coherence", "health_score"],
        )
        insights = generate_insights(correlation=corr)
        assert len(insights) >= 1

    def test_generate_insights_max_cap(self):
        """Insights should be capped at max_insights."""
        df = _make_aligned_df(n_weeks=30)
        featured, feat_names = build_lag_features(df)
        result = train(featured, feat_names, save=False)
        corr = compute_correlation_matrix(df)
        cfg = InsightConfig(
            strong_correlation=0.0,
            moderate_correlation=0.0,
            top_importance_threshold=0.0,
            max_insights=3,
        )
        insights = generate_insights(
            correlation=corr, training_result=result, cfg=cfg,
        )
        assert len(insights) <= 3

    def test_insights_sorted_by_priority(self):
        df = _make_aligned_df(n_weeks=30)
        featured, feat_names = build_lag_features(df)
        result = train(featured, feat_names, save=False)
        corr = compute_correlation_matrix(df)
        insights = generate_insights(
            correlation=corr, training_result=result,
        )
        prio_order = {"high": 0, "medium": 1, "low": 2}
        for i in range(1, len(insights)):
            assert prio_order.get(insights[i].priority, 9) >= prio_order.get(
                insights[i - 1].priority, 9
            )

    def test_insight_to_dict(self):
        ins = Insight(
            category="correlation", priority="high",
            message="Test insight", evidence={"val": 0.9},
        )
        d = ins.to_dict()
        assert d["category"] == "correlation"
        assert d["priority"] == "high"


# ═══════════════════════════════════════════════════════════════════════════
# 9. Scorer orchestration tests
# ═══════════════════════════════════════════════════════════════════════════

class TestScorer:
    """Verify full pipeline orchestration."""

    def test_analyse_full_pipeline(self):
        obs = _make_observations(n_weeks=30)
        result = analyse(obs, save_model=False)
        assert isinstance(result, FusionAnalysis)

    def test_analyse_has_correlation(self):
        obs = _make_observations(n_weeks=30)
        result = analyse(obs, save_model=False)
        assert result.correlation is not None

    def test_analyse_has_training_result(self):
        obs = _make_observations(n_weeks=30)
        result = analyse(obs, save_model=False)
        assert result.training_result is not None

    def test_analyse_has_predictions(self):
        obs = _make_observations(n_weeks=30)
        result = analyse(obs, save_model=True)
        assert result.predictions is not None
        assert len(result.predictions) > 0

    def test_analyse_has_insights(self):
        obs = _make_observations(n_weeks=30)
        result = analyse(obs, save_model=False)
        # Should produce at least some insights
        assert isinstance(result.insights, list)

    def test_analyse_empty_observations(self):
        result = analyse([], save_model=False)
        assert result.n_aligned_periods == 0

    def test_analyse_to_dict(self):
        obs = _make_observations(n_weeks=30)
        result = analyse(obs, save_model=False)
        d = result.to_dict()
        assert "correlation" in d
        assert "insights" in d
        assert "n_observations" in d

    def test_analyse_from_dataframe(self):
        df = _make_aligned_df(n_weeks=30)
        result = analyse_from_dataframe(df, save_model=False)
        assert isinstance(result, FusionAnalysis)
        assert result.training_result is not None

    def test_analyse_skip_train(self):
        obs = _make_observations(n_weeks=30)
        result = analyse(obs, do_train=False, save_model=False)
        assert result.training_result is None

    def test_analyse_skip_predict(self):
        obs = _make_observations(n_weeks=30)
        result = analyse(obs, do_predict=False, save_model=False)
        assert result.predictions is None

    def test_n_observations_tracked(self):
        obs = _make_observations(n_weeks=20)
        result = analyse(obs, save_model=False)
        assert result.n_observations == len(obs)


# ═══════════════════════════════════════════════════════════════════════════
# 10. Service layer tests
# ═══════════════════════════════════════════════════════════════════════════

class TestService:
    """Verify the public service API."""

    def test_service_analyse(self):
        obs = _make_observations(n_weeks=30)
        result = service_analyse(obs, save_model=False)
        assert isinstance(result, dict)
        assert "correlation" in result

    def test_service_analyse_dataframe(self):
        df = _make_aligned_df(n_weeks=30)
        result = service_analyse_dataframe(df, save_model=False)
        assert isinstance(result, dict)
        assert "correlation" in result

    def test_model_status_untrained(self):
        status = get_model_status()
        assert status["model_trained"] is False

    def test_model_status_after_training(self):
        obs = _make_observations(n_weeks=30)
        service_analyse(obs, save_model=True)
        status = get_model_status()
        assert status["model_trained"] is True


# ═══════════════════════════════════════════════════════════════════════════
# 11. Synthetic data generation tests
# ═══════════════════════════════════════════════════════════════════════════

class TestSyntheticData:
    """Verify synthetic dataset generation."""

    def test_generate_returns_observations(self):
        synth = generate_synthetic_dataset(n_researchers=2, n_weeks=10)
        assert "observations" in synth
        assert len(synth["observations"]) > 0

    def test_generate_researcher_ids(self):
        synth = generate_synthetic_dataset(n_researchers=3, n_weeks=10)
        assert len(synth["researcher_ids"]) == 3

    def test_generate_observation_count(self):
        n_r, n_w = 2, 10
        synth = generate_synthetic_dataset(n_researchers=n_r, n_weeks=n_w)
        # 6 signals + 3 targets = 9 per week per researcher
        expected = n_r * n_w * (len(SIGNAL_NAMES) + len(TARGET_NAMES))
        assert synth["n_observations"] == expected

    def test_generate_deterministic(self):
        s1 = generate_synthetic_dataset(n_researchers=2, n_weeks=10, seed=42)
        s2 = generate_synthetic_dataset(n_researchers=2, n_weeks=10, seed=42)
        for o1, o2 in zip(s1["observations"], s2["observations"]):
            assert o1.value == o2.value

    def test_generate_different_seeds(self):
        s1 = generate_synthetic_dataset(n_researchers=2, n_weeks=10, seed=1)
        s2 = generate_synthetic_dataset(n_researchers=2, n_weeks=10, seed=2)
        values1 = [o.value for o in s1["observations"]]
        values2 = [o.value for o in s2["observations"]]
        assert values1 != values2

    def test_synthetic_end_to_end(self):
        """Generate synthetic data, then analyse it."""
        synth = generate_synthetic_dataset(n_researchers=3, n_weeks=30)
        result = service_analyse(synth["observations"], save_model=False)
        assert "correlation" in result
        assert "insights" in result


# ═══════════════════════════════════════════════════════════════════════════
# 12. Target metrics container tests
# ═══════════════════════════════════════════════════════════════════════════

class TestTargetMetrics:
    """Verify TargetMetrics dataclass."""

    def test_to_dict(self):
        m = TargetMetrics(
            target="publication_success", r2=0.85, mae=0.1, rmse=0.12,
            n_train=80, n_test=20,
        )
        d = m.to_dict()
        assert d["target"] == "publication_success"
        assert d["r2"] == 0.85
        assert d["n_train"] == 80

    def test_frozen(self):
        m = TargetMetrics(
            target="t", r2=0.5, mae=0.1, rmse=0.2, n_train=10, n_test=5,
        )
        with pytest.raises(AttributeError):
            m.target = "other"  # type: ignore[misc]


# ═══════════════════════════════════════════════════════════════════════════
# 13. Schemas tests
# ═══════════════════════════════════════════════════════════════════════════

class TestSchemas:
    """Verify Pydantic schema contracts."""

    def test_signal_observation_in(self):
        from app.schemas.fusion_engine import SignalObservationIn
        obj = SignalObservationIn(
            timestamp="2023-01-01",
            signal_name="writing_coherence",
            value=0.8,
        )
        assert obj.signal_name == "writing_coherence"

    def test_analyse_request(self):
        from app.schemas.fusion_engine import AnalyseRequest, SignalObservationIn
        req = AnalyseRequest(
            observations=[
                SignalObservationIn(
                    timestamp="2023-01-01",
                    signal_name="writing_coherence",
                    value=0.8,
                ),
            ],
        )
        assert len(req.observations) == 1

    def test_synthetic_request_defaults(self):
        from app.schemas.fusion_engine import SyntheticRequest
        req = SyntheticRequest()
        assert req.n_researchers == 5
        assert req.n_weeks == 52
        assert req.seed == 42
        assert req.run_analysis is True

    def test_analyse_response_model(self):
        from app.schemas.fusion_engine import AnalyseResponse
        # Just verify the class is importable and constructible
        assert AnalyseResponse is not None

    def test_model_status_response(self):
        from app.schemas.fusion_engine import ModelStatusResponse
        resp = ModelStatusResponse(
            model_trained=False,
            model_path="/tmp/model.joblib",
            artifacts_dir="/tmp",
        )
        assert resp.model_trained is False

    def test_insight_out(self):
        from app.schemas.fusion_engine import InsightOut
        ins = InsightOut(
            category="correlation",
            priority="high",
            message="strong correlation detected",
            evidence={"val": 0.9},
        )
        assert ins.category == "correlation"


# ═══════════════════════════════════════════════════════════════════════════
# 14. API endpoint tests
# ═══════════════════════════════════════════════════════════════════════════

class TestEndpoints:
    """Verify API endpoint wiring (import + router existence)."""

    def test_router_exists(self):
        from app.api.v1.endpoints.fusion_engine import router
        assert router is not None

    def test_router_has_analyse_route(self):
        from app.api.v1.endpoints.fusion_engine import router
        paths = [r.path for r in router.routes]
        assert "/analyse" in paths

    def test_router_has_synthetic_route(self):
        from app.api.v1.endpoints.fusion_engine import router
        paths = [r.path for r in router.routes]
        assert "/synthetic" in paths

    def test_router_has_status_route(self):
        from app.api.v1.endpoints.fusion_engine import router
        paths = [r.path for r in router.routes]
        assert "/status" in paths

    def test_router_registered_in_api_v1(self):
        from app.api.v1 import api_router
        prefixes = [r.path for r in api_router.routes]
        # Should contain /fusion prefix routes
        assert any("/fusion" in p for p in prefixes)


# ═══════════════════════════════════════════════════════════════════════════
# 15. Edge cases and integration
# ═══════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    """Edge-case and integration tests."""

    def test_single_week_observations(self):
        obs = _make_observations(n_weeks=1)
        result = analyse(obs, save_model=False, do_train=False)
        # Should not crash even with minimal data
        assert isinstance(result, FusionAnalysis)

    def test_sparse_signals(self):
        """Only a few signals, not all six."""
        obs = _make_observations(
            n_weeks=20,
            signals=["writing_coherence", "health_score"],
            targets=[],
        )
        result = analyse(obs, save_model=False, do_train=False)
        assert result.correlation is not None

    def test_all_same_values(self):
        """Constant signals → zero-variance → should not crash."""
        obs = []
        start = pd.Timestamp("2023-01-01")
        for w in range(20):
            ts = (start + pd.Timedelta(weeks=w)).isoformat()
            for sig in SIGNAL_NAMES:
                obs.append(SignalObservation(
                    timestamp=ts, signal_name=sig, value=1.0,
                ))
            for tgt in TARGET_NAMES:
                obs.append(SignalObservation(
                    timestamp=ts, signal_name=tgt, value=0.5,
                ))
        result = analyse(obs, save_model=False)
        assert isinstance(result, FusionAnalysis)

    def test_reload_clears_cache(self):
        df = _make_aligned_df(n_weeks=30)
        featured, feat_names = build_lag_features(df)
        train(featured, feat_names, save=True)
        reload_models()
        # Should force re-read from disk on next predict
        preds = predict(featured, feat_names)
        assert len(preds) > 0

    def test_fusion_analysis_to_dict_keys(self):
        obs = _make_observations(n_weeks=30)
        result = analyse(obs, save_model=False)
        d = result.to_dict()
        expected_keys = {
            "correlation", "training_result", "predictions",
            "insights", "n_observations", "n_aligned_periods",
            "n_features", "feature_names",
        }
        assert expected_keys.issubset(d.keys())

    def test_negative_correlation(self):
        """Perfectly anti-correlated signals → negative r."""
        n = 30
        index = pd.date_range("2023-01-01", periods=n, freq="W")
        vals = np.linspace(0, 1, n)
        df = pd.DataFrame({
            "writing_coherence": vals,
            "health_score": 1 - vals,
        }, index=index)
        corr = compute_correlation_matrix(df)
        r = corr.matrix.loc["writing_coherence", "health_score"]
        assert r < -0.9

    def test_metadata_json_valid(self):
        df = _make_aligned_df(n_weeks=30)
        featured, feat_names = build_lag_features(df)
        train(featured, feat_names, save=True)
        meta_path = _cfg.FUSION_ARTIFACTS_DIR / METADATA_FILENAME
        with open(meta_path) as f:
            meta = json.load(f)
        assert "target_metrics" in meta
        assert "feature_importances" in meta
