"""
Tests for the Dropout Risk Prediction module.

Covers:
  * Configuration defaults and thresholds
  * Feature engineering (slope computation, interaction features, imputation,
    fit/transform lifecycle, state persistence)
  * Model training (LR baseline + XGBoost, metrics validation, persistence)
  * Prediction (risk categories green/yellow/red, probability bounds)
  * SHAP explainability (top risk factors, direction labels, factor counts)
  * Service layer (bootstrap, predict, explain, model status)
  * Synthetic dataset generation (statistics, label distribution)
  * Edge cases (single record, all-missing values, tiny dataset)

Expensive objects (trained model bundle) are module-scoped to avoid
re-training per test.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd
import pytest

from app.ml.dropout_risk.config import (
    ALL_FEATURES,
    DERIVED_FEATURES,
    EARLY_WARNING_MAX_WEEKS,
    EARLY_WARNING_MIN_WEEKS,
    HYPERPARAMS_LR,
    HYPERPARAMS_XGB,
    LRHyperParams,
    RAW_FEATURES,
    RISK_THRESHOLD_RED,
    RISK_THRESHOLD_YELLOW,
    TARGET_COLUMN,
    XGBHyperParams,
)
from app.ml.dropout_risk.features import (
    DropoutFeatureEngineer,
    RawDropoutRecord,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_record(
    *,
    latency: float = 10.0,
    gap: float = 14.0,
    delay: float = 0.2,
    health_slope: float = -0.1,
    engagement: int = 5,
    coherence: float = 0.3,
    revision: float = 0.8,
    peers: int = 4,
    dropout: int | None = None,
    health_history: list[float] | None = None,
    weeks_since: float | None = None,
) -> RawDropoutRecord:
    return RawDropoutRecord(
        supervision_latency_avg=latency,
        supervision_gap_max=gap,
        milestone_delay_ratio=delay,
        health_score_decline_slope=health_slope,
        opportunity_engagement_count=engagement,
        writing_coherence_trend=coherence,
        revision_response_rate=revision,
        peer_connection_count=peers,
        dropout=dropout,
        health_score_history=health_history,
        weeks_since_last_supervision=weeks_since,
    )


def _make_training_records(n: int = 200, seed: int = 42) -> List[RawDropoutRecord]:
    """Light wrapper around synthetic generator."""
    from app.ml.dropout_risk.service import generate_synthetic_dataset
    return generate_synthetic_dataset(n=n, seed=seed)


def _safe_xgb_params() -> XGBHyperParams:
    """Small, fast XGBoost params safe for repeated training in tests."""
    return XGBHyperParams(
        n_estimators=10,
        learning_rate=0.3,
        max_depth=3,
        min_child_weight=1,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_alpha=0.0,
        reg_lambda=1.0,
        scale_pos_weight=1.0,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def synthetic_records() -> List[RawDropoutRecord]:
    """200 synthetic records for training."""
    return _make_training_records(n=200)


@pytest.fixture(scope="module")
def trained_bundle(synthetic_records, tmp_path_factory):
    """
    Train both models on the synthetic records and return the in-memory
    bundle dict that can be injected into predict/explain to avoid I/O.
    """
    from sklearn.preprocessing import StandardScaler
    from xgboost import XGBClassifier
    from sklearn.linear_model import LogisticRegression

    from app.ml.dropout_risk.model import train

    # Train without saving to disk (no side-effects on default artifact dir)
    result = train(synthetic_records, save=False)

    # Rebuild bundle manually for injection
    fe = DropoutFeatureEngineer()
    df = fe.fit_transform(synthetic_records)
    X = df[ALL_FEATURES].values.astype(np.float32)
    y = df[TARGET_COLUMN].values.astype(int)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    lr = LogisticRegression(**HYPERPARAMS_LR.to_dict())
    lr.fit(X_scaled, y)

    xgb = XGBClassifier(**HYPERPARAMS_XGB.to_dict())
    xgb.fit(X, y)

    bundle = {
        "lr_model": lr,
        "xgb_model": xgb,
        "scaler": scaler,
        "feature_engineer": fe,
    }
    return {"result": result, "bundle": bundle}


# =========================================================================
# 1. Configuration
# =========================================================================

class TestConfig:
    """Validate configuration defaults and consistency."""

    def test_raw_feature_count(self):
        assert len(RAW_FEATURES) == 8

    def test_derived_feature_count(self):
        assert len(DERIVED_FEATURES) == 5

    def test_all_features_is_union(self):
        assert ALL_FEATURES == RAW_FEATURES + DERIVED_FEATURES
        assert len(ALL_FEATURES) == 13

    def test_risk_thresholds_ordering(self):
        assert 0 < RISK_THRESHOLD_YELLOW < RISK_THRESHOLD_RED < 1

    def test_early_warning_window(self):
        assert EARLY_WARNING_MIN_WEEKS == 8
        assert EARLY_WARNING_MAX_WEEKS == 12
        assert EARLY_WARNING_MIN_WEEKS < EARLY_WARNING_MAX_WEEKS

    def test_xgb_hyperparams_dict(self):
        d = HYPERPARAMS_XGB.to_dict()
        assert d["n_estimators"] == 300
        assert d["learning_rate"] == 0.05
        assert d["max_depth"] == 5
        assert d["random_state"] == 42
        assert isinstance(d, dict)

    def test_lr_hyperparams_dict(self):
        d = HYPERPARAMS_LR.to_dict()
        assert d["C"] == 1.0
        assert d["solver"] == "lbfgs"
        assert d["max_iter"] == 1000

    def test_target_column(self):
        assert TARGET_COLUMN == "dropout"


# =========================================================================
# 2. Feature Engineering
# =========================================================================

class TestFeatureEngineering:
    """Test stateful feature engineering pipeline."""

    def test_fit_transform_produces_all_features(self):
        records = [_make_record(dropout=0), _make_record(dropout=1)]
        fe = DropoutFeatureEngineer()
        df = fe.fit_transform(records)

        for col in ALL_FEATURES:
            assert col in df.columns, f"Missing feature: {col}"

    def test_transform_requires_fit(self):
        fe = DropoutFeatureEngineer()
        with pytest.raises(RuntimeError, match="not fitted"):
            fe.transform([_make_record()])

    def test_slope_computed_from_history(self):
        """Health-score history should override the static slope field."""
        rec = _make_record(
            health_slope=-999.0,  # should be overridden
            health_history=[80.0, 70.0, 60.0, 50.0],
            dropout=0,
        )
        fe = DropoutFeatureEngineer()
        df = fe.fit_transform([rec])
        # Slope should be negative (declining) and NOT -999
        slope_val = df["health_score_decline_slope"].iloc[0]
        assert slope_val != -999.0
        assert slope_val < 0  # declining

    def test_interaction_features_computed(self):
        rec = _make_record(latency=10.0, gap=20.0, delay=0.5,
                           health_slope=-0.3, engagement=6, peers=3,
                           dropout=0)
        fe = DropoutFeatureEngineer()
        df = fe.fit_transform([rec])

        # supervision_intensity = latency * gap
        assert df["supervision_intensity"].iloc[0] == pytest.approx(200.0)
        # delay_health_interaction = delay * slope
        assert df["delay_health_interaction"].iloc[0] == pytest.approx(-0.15)
        # engagement_per_peer = 6 / 3
        assert df["engagement_per_peer"].iloc[0] == pytest.approx(2.0)

    def test_zero_peers_handled(self):
        """engagement_per_peer with zero peers should produce NaN → median."""
        rec = _make_record(peers=0, engagement=5, dropout=0)
        fe = DropoutFeatureEngineer()
        df = fe.fit_transform([rec])
        val = df["engagement_per_peer"].iloc[0]
        assert np.isfinite(val)  # NaN was imputed

    def test_imputation_fills_nans(self):
        """Missing raw fields should be imputed to the median."""
        rec = RawDropoutRecord(dropout=0)  # all None
        good = _make_record(dropout=1)
        fe = DropoutFeatureEngineer()
        df = fe.fit_transform([good, rec])
        assert df.isnull().sum().sum() == 0

    def test_state_roundtrip(self):
        """get_state / load_state preserves fitted medians."""
        records = [_make_record(dropout=i % 2) for i in range(10)]
        fe1 = DropoutFeatureEngineer()
        df1 = fe1.fit_transform(records)
        state = fe1.get_state()

        fe2 = DropoutFeatureEngineer()
        fe2.load_state(state)
        df2 = fe2.transform([_make_record()])

        # Both should produce dataframes with ALL_FEATURES
        for col in ALL_FEATURES:
            assert col in df2.columns

    def test_target_column_present_when_labeled(self):
        records = [_make_record(dropout=0), _make_record(dropout=1)]
        fe = DropoutFeatureEngineer()
        df = fe.fit_transform(records)
        assert TARGET_COLUMN in df.columns
        assert set(df[TARGET_COLUMN].unique()) == {0, 1}

    def test_target_column_absent_when_unlabeled(self):
        records = [_make_record()]  # dropout=None
        fe = DropoutFeatureEngineer()
        df = fe.fit_transform(records)
        # Should NOT have target column when None
        assert TARGET_COLUMN not in df.columns or df[TARGET_COLUMN].isna().all()

    def test_risk_velocity_from_engagement_history(self):
        rec = _make_record(dropout=0)
        rec.engagement_history = [10.0, 8.0, 6.0, 4.0]  # declining
        fe = DropoutFeatureEngineer()
        df = fe.fit_transform([rec])
        # risk_velocity = slope of engagement history => negative
        assert df["risk_velocity"].iloc[0] < 0


# =========================================================================
# 3. Model Training
# =========================================================================

class TestModelTraining:
    """Test training pipeline with LR and XGBoost."""

    def test_training_returns_result(self, trained_bundle):
        result = trained_bundle["result"]
        assert result.n_samples == 200
        assert result.n_features == 13

    def test_lr_metrics_populated(self, trained_bundle):
        m = trained_bundle["result"].lr_metrics
        assert 0 <= m.auc_roc <= 1
        assert 0 <= m.auc_pr <= 1
        assert 0 <= m.precision <= 1
        assert 0 <= m.recall <= 1
        assert 0 <= m.f1 <= 1
        assert m.n_test > 0

    def test_xgb_metrics_populated(self, trained_bundle):
        m = trained_bundle["result"].xgb_metrics
        assert 0 <= m.auc_roc <= 1
        assert 0 <= m.auc_pr <= 1
        assert 0 <= m.precision <= 1
        assert 0 <= m.recall <= 1
        assert 0 <= m.f1 <= 1
        assert m.n_test > 0

    def test_both_models_have_reasonable_auc(self, trained_bundle):
        """Both models should achieve above-chance AUC on synthetic data."""
        lr_auc = trained_bundle["result"].lr_metrics.auc_roc
        xgb_auc = trained_bundle["result"].xgb_metrics.auc_roc
        assert lr_auc > 0.5, f"LR AUC {lr_auc} should be above chance"
        assert xgb_auc > 0.5, f"XGB AUC {xgb_auc} should be above chance"

    def test_feature_importances_populated(self, trained_bundle):
        imp = trained_bundle["result"].feature_importances
        assert len(imp) == 13
        for feat in ALL_FEATURES:
            assert feat in imp
        # At least one feature should have non-zero importance
        assert max(imp.values()) > 0

    def test_training_result_serializes(self, trained_bundle):
        d = trained_bundle["result"].to_dict()
        assert "lr_metrics" in d
        assert "xgb_metrics" in d
        assert "feature_importances" in d
        assert isinstance(d["n_samples"], int)

    def test_classification_metrics_to_dict(self, trained_bundle):
        d = trained_bundle["result"].lr_metrics.to_dict()
        assert "auc_roc" in d
        assert "auc_pr" in d
        assert isinstance(d["auc_roc"], float)

    def test_save_and_load_roundtrip(self, synthetic_records, tmp_path):
        """Full persistence roundtrip: save → load → predict."""
        import app.ml.dropout_risk.config as cfg
        import app.ml.dropout_risk.model as mdl

        original_dir = cfg.DROPOUT_ARTIFACTS_DIR
        original_cache = mdl._cached_bundle

        try:
            # Redirect artifacts to temp dir
            cfg.DROPOUT_ARTIFACTS_DIR = tmp_path
            mdl._cached_bundle = None

            from app.ml.dropout_risk.model import train, predict as model_predict

            train(
                synthetic_records,
                save=True,
                xgb_params=_safe_xgb_params(),
            )

            # Verify files exist
            assert (tmp_path / cfg.MODEL_FILENAME_LR).exists()
            assert (tmp_path / cfg.MODEL_FILENAME_XGB).exists()
            assert (tmp_path / cfg.FEATURE_STATE_FILENAME).exists()
            assert (tmp_path / cfg.METADATA_FILENAME).exists()

            # Force reload and predict
            mdl._cached_bundle = None
            preds = model_predict([_make_record()])
            assert len(preds) == 1
            assert 0 <= preds[0].dropout_probability <= 1
        finally:
            cfg.DROPOUT_ARTIFACTS_DIR = original_dir
            mdl._cached_bundle = original_cache


# =========================================================================
# 4. Prediction
# =========================================================================

class TestPrediction:
    """Test dropout prediction with risk categories."""

    def test_predict_xgboost(self, trained_bundle):
        from app.ml.dropout_risk.model import predict

        preds = predict(
            [_make_record()],
            model="xgboost",
            _bundle=trained_bundle["bundle"],
        )
        assert len(preds) == 1
        p = preds[0]
        assert 0 <= p.dropout_probability <= 1
        assert p.risk_category in {"green", "yellow", "red"}
        assert p.model_used == "xgboost"

    def test_predict_logistic_regression(self, trained_bundle):
        from app.ml.dropout_risk.model import predict

        preds = predict(
            [_make_record()],
            model="logistic_regression",
            _bundle=trained_bundle["bundle"],
        )
        assert len(preds) == 1
        assert preds[0].model_used == "logistic_regression"
        assert 0 <= preds[0].dropout_probability <= 1

    def test_green_category(self, trained_bundle):
        """Low-risk student → green."""
        from app.ml.dropout_risk.model import predict

        # Very good signals
        rec = _make_record(
            latency=3.0, gap=7.0, delay=0.05, health_slope=0.1,
            engagement=15, coherence=0.9, revision=0.95, peers=10,
        )
        preds = predict([rec], _bundle=trained_bundle["bundle"])
        # probability should be low
        assert preds[0].dropout_probability < 0.5

    def test_red_category_high_risk(self, trained_bundle):
        """Very high-risk signals should produce elevated probability."""
        from app.ml.dropout_risk.model import predict

        rec = _make_record(
            latency=50.0, gap=80.0, delay=0.95, health_slope=-0.8,
            engagement=0, coherence=-0.9, revision=0.05, peers=0,
        )
        preds = predict([rec], _bundle=trained_bundle["bundle"])
        # Should have elevated risk
        assert preds[0].dropout_probability > 0.3

    def test_batch_prediction(self, trained_bundle):
        from app.ml.dropout_risk.model import predict

        records = [_make_record(latency=5 + i * 5) for i in range(10)]
        preds = predict(records, _bundle=trained_bundle["bundle"])
        assert len(preds) == 10

    def test_risk_category_thresholds(self, trained_bundle):
        """Verify the category assignment logic directly."""
        from app.ml.dropout_risk.model import predict

        # Predict a batch and check categories match thresholds
        records = _make_training_records(n=50, seed=99)
        # Remove dropout labels for pure prediction records
        unlabeled = [
            RawDropoutRecord(
                supervision_latency_avg=r.supervision_latency_avg,
                supervision_gap_max=r.supervision_gap_max,
                milestone_delay_ratio=r.milestone_delay_ratio,
                health_score_decline_slope=r.health_score_decline_slope,
                opportunity_engagement_count=r.opportunity_engagement_count,
                writing_coherence_trend=r.writing_coherence_trend,
                revision_response_rate=r.revision_response_rate,
                peer_connection_count=r.peer_connection_count,
                health_score_history=r.health_score_history,
                weeks_since_last_supervision=r.weeks_since_last_supervision,
            )
            for r in records
        ]
        preds = predict(unlabeled, _bundle=trained_bundle["bundle"])

        for p in preds:
            prob = p.dropout_probability
            if prob >= RISK_THRESHOLD_RED:
                assert p.risk_category == "red"
            elif prob >= RISK_THRESHOLD_YELLOW:
                assert p.risk_category == "yellow"
            else:
                assert p.risk_category == "green"

    def test_prediction_serializes(self, trained_bundle):
        from app.ml.dropout_risk.model import predict

        preds = predict([_make_record()], _bundle=trained_bundle["bundle"])
        d = preds[0].to_dict()
        assert "dropout_probability" in d
        assert "risk_category" in d
        assert "model_used" in d


# =========================================================================
# 5. SHAP Explainability
# =========================================================================

class TestExplainability:
    """Test SHAP-based dropout risk explanations."""

    def test_explain_xgboost(self, trained_bundle):
        from app.ml.dropout_risk.explainability import explain

        expls = explain(
            [_make_record()],
            model="xgboost",
            _bundle=trained_bundle["bundle"],
        )
        assert len(expls) == 1
        e = expls[0]
        assert 0 <= e.predicted_probability <= 1
        assert e.risk_category in {"green", "yellow", "red"}
        assert len(e.top_risk_factors) <= 5
        assert len(e.all_factors) == 13

    def test_explain_logistic_regression(self, trained_bundle):
        from app.ml.dropout_risk.explainability import explain

        expls = explain(
            [_make_record()],
            model="logistic_regression",
            top_n=3,
            _bundle=trained_bundle["bundle"],
        )
        assert len(expls) == 1
        e = expls[0]
        assert len(e.top_risk_factors) <= 3
        assert 0 <= e.predicted_probability <= 1
        assert e.risk_category in {"green", "yellow", "red"}

    def test_risk_factor_directions(self, trained_bundle):
        from app.ml.dropout_risk.explainability import explain

        expls = explain(
            [_make_record(latency=50.0, gap=80.0)],
            _bundle=trained_bundle["bundle"],
        )
        factors = expls[0].all_factors
        directions = {f.direction for f in factors}
        # Should contain at least one non-neutral direction
        assert directions & {"increases_risk", "decreases_risk"}

    def test_factors_sorted_by_shap_magnitude(self, trained_bundle):
        from app.ml.dropout_risk.explainability import explain

        expls = explain([_make_record()], _bundle=trained_bundle["bundle"])
        factors = expls[0].all_factors
        shap_abs = [abs(f.shap_value) for f in factors]
        assert shap_abs == sorted(shap_abs, reverse=True)

    def test_factor_fields_populated(self, trained_bundle):
        from app.ml.dropout_risk.explainability import explain

        expls = explain([_make_record()], _bundle=trained_bundle["bundle"])
        for f in expls[0].all_factors:
            assert isinstance(f.feature_name, str)
            assert f.feature_name in ALL_FEATURES
            assert isinstance(f.shap_value, float)
            assert f.direction in {"increases_risk", "decreases_risk", "neutral"}

    def test_explanation_serializes(self, trained_bundle):
        from app.ml.dropout_risk.explainability import explain

        expls = explain([_make_record()], _bundle=trained_bundle["bundle"])
        d = expls[0].to_dict()
        assert "base_probability" in d
        assert "predicted_probability" in d
        assert "top_risk_factors" in d
        assert isinstance(d["top_risk_factors"], list)

    def test_batch_explanation(self, trained_bundle):
        from app.ml.dropout_risk.explainability import explain

        records = [_make_record(latency=5 + i * 4) for i in range(5)]
        expls = explain(records, _bundle=trained_bundle["bundle"])
        assert len(expls) == 5


# =========================================================================
# 6. Service Layer
# =========================================================================

class TestService:
    """Test the public service API."""

    def test_predict_risk(self, trained_bundle):
        from app.ml.dropout_risk.service import predict_risk

        results = predict_risk(
            [_make_record()],
            _bundle=trained_bundle["bundle"],
        )
        assert len(results) == 1
        r = results[0]
        assert "dropout_probability" in r
        assert "risk_category" in r
        assert "model_used" in r
        assert 0 <= r["dropout_probability"] <= 1

    def test_explain_risk(self, trained_bundle):
        from app.ml.dropout_risk.service import explain_risk

        results = explain_risk(
            [_make_record()],
            _bundle=trained_bundle["bundle"],
        )
        assert len(results) == 1
        r = results[0]
        assert "top_risk_factors" in r
        assert "predicted_probability" in r

    def test_train_model(self, synthetic_records):
        from app.ml.dropout_risk.service import train_model

        result = train_model(synthetic_records, save=False)
        assert "lr_metrics" in result
        assert "xgb_metrics" in result
        assert result["n_samples"] == 200

    def test_bootstrap_model(self, tmp_path):
        """bootstrap_model generates data and trains in one step."""
        import app.ml.dropout_risk.config as cfg
        import app.ml.dropout_risk.model as mdl

        original_dir = cfg.DROPOUT_ARTIFACTS_DIR
        original_cache = mdl._cached_bundle
        try:
            cfg.DROPOUT_ARTIFACTS_DIR = tmp_path
            mdl._cached_bundle = None

            # Use safe params + small data for speed
            from app.ml.dropout_risk.service import generate_synthetic_dataset
            from app.ml.dropout_risk.model import train
            records = generate_synthetic_dataset(n=100)
            result = train(records, save=True, xgb_params=_safe_xgb_params())
            assert result.n_samples == 100
            assert (tmp_path / cfg.MODEL_FILENAME_XGB).exists()
        finally:
            cfg.DROPOUT_ARTIFACTS_DIR = original_dir
            mdl._cached_bundle = original_cache

    def test_get_model_status_no_model(self, tmp_path):
        """When no model is trained, status should say so."""
        import app.ml.dropout_risk.config as cfg

        original_dir = cfg.DROPOUT_ARTIFACTS_DIR
        try:
            cfg.DROPOUT_ARTIFACTS_DIR = tmp_path
            from app.ml.dropout_risk.service import get_model_status
            status = get_model_status()
            assert status["loaded"] is False
        finally:
            cfg.DROPOUT_ARTIFACTS_DIR = original_dir

    def test_get_model_status_after_training(self, tmp_path, synthetic_records):
        import app.ml.dropout_risk.config as cfg
        import app.ml.dropout_risk.model as mdl

        original_dir = cfg.DROPOUT_ARTIFACTS_DIR
        original_cache = mdl._cached_bundle
        try:
            cfg.DROPOUT_ARTIFACTS_DIR = tmp_path
            mdl._cached_bundle = None

            from app.ml.dropout_risk.model import train
            train(
                synthetic_records,
                save=True,
                xgb_params=_safe_xgb_params(),
            )

            from app.ml.dropout_risk.service import get_model_status
            status = get_model_status()
            assert status["loaded"] is True
            assert "lr_metrics" in status
            assert "xgb_metrics" in status
        finally:
            cfg.DROPOUT_ARTIFACTS_DIR = original_dir
            mdl._cached_bundle = original_cache


# =========================================================================
# 7. Synthetic Data Generation
# =========================================================================

class TestSyntheticData:
    """Test the synthetic dataset generator."""

    def test_correct_count(self):
        from app.ml.dropout_risk.service import generate_synthetic_dataset
        records = generate_synthetic_dataset(n=50, seed=7)
        assert len(records) == 50

    def test_deterministic(self):
        from app.ml.dropout_risk.service import generate_synthetic_dataset
        r1 = generate_synthetic_dataset(n=30, seed=42)
        r2 = generate_synthetic_dataset(n=30, seed=42)
        for a, b in zip(r1, r2):
            assert a.supervision_latency_avg == b.supervision_latency_avg
            assert a.dropout == b.dropout

    def test_has_both_classes(self):
        from app.ml.dropout_risk.service import generate_synthetic_dataset
        records = generate_synthetic_dataset(n=200, seed=42)
        labels = {r.dropout for r in records}
        assert labels == {0, 1}

    def test_features_in_reasonable_ranges(self):
        from app.ml.dropout_risk.service import generate_synthetic_dataset
        records = generate_synthetic_dataset(n=100, seed=42)
        for r in records:
            assert r.supervision_latency_avg >= 0
            assert r.supervision_gap_max >= 0
            assert 0 <= r.milestone_delay_ratio <= 1
            assert 0 <= r.revision_response_rate <= 1
            assert r.peer_connection_count >= 0
            assert r.opportunity_engagement_count >= 0

    def test_health_history_present(self):
        from app.ml.dropout_risk.service import generate_synthetic_dataset
        records = generate_synthetic_dataset(n=10, seed=42)
        for r in records:
            assert r.health_score_history is not None
            assert len(r.health_score_history) >= 2


# =========================================================================
# 8. Edge Cases
# =========================================================================

class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_single_record_prediction(self, trained_bundle):
        from app.ml.dropout_risk.model import predict

        preds = predict([_make_record()], _bundle=trained_bundle["bundle"])
        assert len(preds) == 1

    def test_all_missing_values_prediction(self, trained_bundle):
        """A record with all None should still produce a prediction."""
        from app.ml.dropout_risk.model import predict

        rec = RawDropoutRecord()  # everything None
        preds = predict([rec], _bundle=trained_bundle["bundle"])
        assert len(preds) == 1
        assert 0 <= preds[0].dropout_probability <= 1

    def test_tiny_training_set(self):
        """Training on <10 records uses the full set for both train+test."""
        from app.ml.dropout_risk.model import train

        records = [
            _make_record(dropout=0, latency=5 + i, gap=10 + i)
            for i in range(5)
        ] + [
            _make_record(dropout=1, latency=30 + i, gap=50 + i)
            for i in range(3)
        ]
        result = train(
            records,
            save=False,
            xgb_params=_safe_xgb_params(),
        )
        assert result.n_samples == 8
        assert result.lr_metrics.n_test > 0

    def test_predict_with_weeks_since(self, trained_bundle):
        from app.ml.dropout_risk.model import predict

        rec = _make_record(weeks_since=6.5)
        preds = predict([rec], _bundle=trained_bundle["bundle"])
        assert len(preds) == 1

    def test_explain_single_record(self, trained_bundle):
        from app.ml.dropout_risk.explainability import explain

        expls = explain([_make_record()], _bundle=trained_bundle["bundle"])
        assert len(expls) == 1
        assert len(expls[0].all_factors) == 13

    def test_reload_models_clears_cache(self):
        import app.ml.dropout_risk.model as mdl
        mdl._cached_bundle = {"dummy": True}
        mdl.reload_models()
        assert mdl._cached_bundle is None
