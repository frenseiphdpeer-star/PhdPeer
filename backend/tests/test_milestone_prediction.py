"""
Tests for the milestone duration prediction ML module.

Covers:
  * Feature engineering (fit, transform, missing-value handling, state roundtrip)
  * Model training + evaluation metrics
  * Prediction + confidence intervals
  * SHAP explainability
  * Model persistence (save → load roundtrip)
  * Service layer (bootstrap, predict_duration, reload)
  * Synthetic data generator determinism
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List
from unittest import mock

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def sample_records() -> List[Dict[str, Any]]:
    """Minimal set of flat-dict records for training / prediction."""
    return [
        {
            "stage_type": "writing",
            "discipline": "computer_science",
            "milestone_type": "thesis_chapter",
            "number_of_prior_milestones": 5,
            "supervision_latency_avg": 14.0,
            "writing_velocity_score": 0.65,
            "prior_delay_patterns": [False, False, True, False, True],
            "opportunity_engagement_score": 0.8,
            "health_score_trajectory": 0.72,
            "revision_density": 2.1,
            "historical_completion_time": 4.5,
            "actual_duration_months": 6.5,
        },
        {
            "stage_type": "data_collection",
            "discipline": "biology",
            "milestone_type": "dataset",
            "number_of_prior_milestones": 2,
            "supervision_latency_avg": 7.0,
            "writing_velocity_score": 0.9,
            "prior_delay_patterns": [False, False],
            "opportunity_engagement_score": 0.5,
            "health_score_trajectory": 0.85,
            "revision_density": 0.5,
            "historical_completion_time": 3.0,
            "actual_duration_months": 8.2,
        },
        {
            "stage_type": "analysis",
            "discipline": "physics",
            "milestone_type": "paper",
            "number_of_prior_milestones": 8,
            "supervision_latency_avg": 21.0,
            "writing_velocity_score": 0.3,
            "prior_delay_patterns": [True, True, False, True],
            "opportunity_engagement_score": 0.3,
            "health_score_trajectory": 0.55,
            "revision_density": 4.0,
            "historical_completion_time": 7.0,
            "actual_duration_months": 10.1,
        },
    ]


@pytest.fixture()
def tmp_model_dir(tmp_path: Path):
    """Redirect model artefacts to a temp dir during tests."""
    with mock.patch("app.ml.config.MODEL_DIR", tmp_path):
        with mock.patch("app.ml.persistence.MODEL_DIR", tmp_path):
            yield tmp_path


# ---------------------------------------------------------------------------
# Feature engineering tests
# ---------------------------------------------------------------------------

class TestFeatureEngineer:

    def test_fit_transform_returns_dataframe_and_series(self, sample_records):
        from app.ml.features import FeatureEngineer, RawMilestoneRecord

        fe = FeatureEngineer()
        X, y = fe.fit_transform(sample_records)

        assert X.shape[0] == 3
        assert X.shape[1] == 11  # 3 categorical + 8 numeric
        assert len(y) == 3
        assert y.isna().sum() == 0

    def test_transform_before_fit_raises(self, sample_records):
        from app.ml.features import FeatureEngineer

        fe = FeatureEngineer()
        with pytest.raises(RuntimeError, match="not been fitted"):
            fe.transform(sample_records)

    def test_missing_values_handled(self):
        from app.ml.features import FeatureEngineer

        sparse_records = [
            {"actual_duration_months": 5.0},  # everything else None
            {"stage_type": "writing", "actual_duration_months": 3.0},
        ]
        fe = FeatureEngineer()
        X, y = fe.fit_transform(sparse_records)

        assert X.isna().sum().sum() == 0
        assert len(y) == 2

    def test_state_roundtrip(self, sample_records):
        from app.ml.features import FeatureEngineer

        fe = FeatureEngineer()
        X_orig, _ = fe.fit_transform(sample_records)
        state = fe.get_state()

        fe2 = FeatureEngineer()
        fe2.load_state(state)
        X_loaded = fe2.transform(sample_records)

        # Feature values should match exactly
        np.testing.assert_array_equal(X_orig.values, X_loaded.values)

    def test_unseen_category_handled(self, sample_records):
        from app.ml.features import FeatureEngineer

        fe = FeatureEngineer()
        fe.fit_transform(sample_records)

        new_rec = [{"stage_type": "never_seen_before_stage"}]
        X = fe.transform(new_rec)
        assert X.shape[0] == 1  # should not crash

    def test_accepts_raw_milestone_record(self):
        from app.ml.features import FeatureEngineer, RawMilestoneRecord

        rec = RawMilestoneRecord(
            stage_type="writing",
            discipline="cs",
            actual_duration_months=4.0,
        )
        fe = FeatureEngineer()
        X, y = fe.fit_transform([rec])
        assert X.shape[0] == 1
        assert float(y.iloc[0]) == 4.0


# ---------------------------------------------------------------------------
# Synthetic data tests
# ---------------------------------------------------------------------------

class TestSyntheticData:

    def test_deterministic(self):
        from app.ml.service import generate_synthetic_dataset

        d1 = generate_synthetic_dataset(n=50, seed=123)
        d2 = generate_synthetic_dataset(n=50, seed=123)
        assert d1 == d2

    def test_has_required_keys(self):
        from app.ml.service import generate_synthetic_dataset

        data = generate_synthetic_dataset(n=5, seed=0)
        required = {
            "stage_type", "discipline", "milestone_type",
            "number_of_prior_milestones", "supervision_latency_avg",
            "writing_velocity_score", "prior_delay_patterns",
            "opportunity_engagement_score", "health_score_trajectory",
            "revision_density", "actual_duration_months",
        }
        for rec in data:
            assert required.issubset(rec.keys())

    def test_positive_duration(self):
        from app.ml.service import generate_synthetic_dataset

        data = generate_synthetic_dataset(n=200, seed=7)
        for rec in data:
            assert rec["actual_duration_months"] > 0


# ---------------------------------------------------------------------------
# Model training tests
# ---------------------------------------------------------------------------

class TestTraining:

    def test_train_returns_metrics(self, tmp_model_dir):
        from app.ml.service import generate_synthetic_dataset, train_model

        data = generate_synthetic_dataset(n=100, seed=42)
        result = train_model(data, test_size=0.2, version_tag="test-v1")

        assert "metrics" in result
        assert result["metrics"]["mae"] >= 0
        assert result["metrics"]["rmse"] >= 0
        assert result["metrics"]["n_train"] > 0
        assert result["metrics"]["n_test"] > 0
        assert "model_path" in result
        assert "feature_importances" in result

    def test_train_too_few_records_raises(self, tmp_model_dir):
        from app.ml.model import train

        with pytest.raises(ValueError, match="at least 5"):
            train([{"actual_duration_months": 1.0}])

    def test_model_file_persisted(self, tmp_model_dir):
        from app.ml.service import generate_synthetic_dataset, train_model

        data = generate_synthetic_dataset(n=50, seed=0)
        train_model(data, test_size=0.0)

        assert (tmp_model_dir / "milestone_duration_model.joblib").exists()
        assert (tmp_model_dir / "milestone_duration_metadata.json").exists()


# ---------------------------------------------------------------------------
# Prediction tests
# ---------------------------------------------------------------------------

class TestPrediction:

    @pytest.fixture(autouse=True)
    def _trained_model(self, tmp_model_dir):
        """Ensure a model is trained before each prediction test."""
        from app.ml.service import bootstrap_model, reload_model
        bootstrap_model(n=100, seed=42)
        reload_model()

    def test_predict_returns_results(self):
        from app.ml.service import predict_duration

        records = [
            {
                "stage_type": "writing",
                "discipline": "computer_science",
                "milestone_type": "thesis_chapter",
                "number_of_prior_milestones": 5,
            }
        ]
        results = predict_duration(records, include_explanations=False)

        assert len(results) == 1
        r = results[0]
        assert r["predicted_duration_months"] >= 0
        assert r["ci_lower"] <= r["predicted_duration_months"]
        assert r["ci_upper"] >= r["predicted_duration_months"]

    def test_predict_with_explanations(self):
        from app.ml.service import predict_duration

        records = [{"stage_type": "analysis"}]
        results = predict_duration(records, include_explanations=True, top_k=3)

        assert len(results) == 1
        assert "explanation" in results[0]
        expl = results[0]["explanation"]
        assert "base_value" in expl
        assert len(expl["top_contributors"]) <= 3

    def test_batch_prediction(self):
        from app.ml.service import predict_duration

        records = [
            {"stage_type": "writing"},
            {"stage_type": "data_collection"},
            {"stage_type": "coursework"},
        ]
        results = predict_duration(records, include_explanations=False)
        assert len(results) == 3

    def test_empty_record_handled(self):
        from app.ml.service import predict_duration

        results = predict_duration([{}], include_explanations=False)
        assert len(results) == 1
        assert results[0]["predicted_duration_months"] >= 0


# ---------------------------------------------------------------------------
# SHAP explainability tests
# ---------------------------------------------------------------------------

class TestExplainability:

    @pytest.fixture(autouse=True)
    def _trained_model(self, tmp_model_dir):
        from app.ml.service import bootstrap_model, reload_model
        bootstrap_model(n=100, seed=42)
        reload_model()

    def test_explain_returns_attributions(self):
        from app.ml.explainability import explain
        from app.ml.persistence import load_model_bundle

        bundle = load_model_bundle()
        records = [{"stage_type": "writing", "discipline": "physics"}]
        explanations = explain(records, bundle, top_k=5)

        assert len(explanations) == 1
        expl = explanations[0]
        assert expl.base_value > 0
        assert len(expl.attributions) == 11  # all features
        assert len(expl.top_contributors) <= 5

    def test_attribution_directions_valid(self):
        from app.ml.explainability import explain
        from app.ml.persistence import load_model_bundle

        bundle = load_model_bundle()
        explanations = explain([{"stage_type": "writing"}], bundle)

        for attr in explanations[0].attributions:
            assert attr.direction in {"increases", "decreases", "neutral"}

    def test_shap_values_sum_to_prediction(self):
        from app.ml.explainability import explain
        from app.ml.persistence import load_model_bundle
        from app.ml.service import predict_duration

        bundle = load_model_bundle()
        records = [{"stage_type": "analysis", "discipline": "biology"}]

        preds = predict_duration(records, include_explanations=False)
        pred_value = preds[0]["predicted_duration_months"]

        explanations = explain(records, bundle)
        expl = explanations[0]
        shap_sum = expl.base_value + sum(a.shap_value for a in expl.attributions)

        # SHAP values should approximately reconstruct the prediction
        assert abs(shap_sum - pred_value) < 0.5


# ---------------------------------------------------------------------------
# Persistence tests
# ---------------------------------------------------------------------------

class TestPersistence:

    def test_model_exists_false_initially(self, tmp_model_dir):
        from app.ml.persistence import model_exists
        assert model_exists() is False

    def test_save_load_roundtrip(self, tmp_model_dir):
        from app.ml.persistence import load_model_bundle, model_exists, save_model_bundle

        bundle = {"model": "fake", "feature_names": ["a", "b"]}
        save_model_bundle(bundle, metrics={"mae": 1.0}, params={"lr": 0.1})

        assert model_exists() is True
        loaded = load_model_bundle()
        assert loaded["model"] == "fake"
        assert loaded["feature_names"] == ["a", "b"]

    def test_metadata_persisted(self, tmp_model_dir):
        from app.ml.persistence import load_model_metadata, save_model_bundle

        save_model_bundle(
            {"model": "x"}, metrics={"mae": 2.0}, params={}, version_tag="v1"
        )
        meta = load_model_metadata()
        assert meta["version"] == "v1"
        assert meta["metrics"]["mae"] == 2.0

    def test_load_missing_raises(self, tmp_model_dir):
        from app.ml.persistence import load_model_bundle

        with pytest.raises(FileNotFoundError, match="No trained model"):
            load_model_bundle()


# ---------------------------------------------------------------------------
# Service layer integration
# ---------------------------------------------------------------------------

class TestService:

    def test_bootstrap_model(self, tmp_model_dir):
        from app.ml.service import bootstrap_model

        result = bootstrap_model(n=100, seed=42)
        assert result["metrics"]["mae"] >= 0
        assert "feature_importances" in result

    def test_reload_model(self, tmp_model_dir):
        from app.ml.service import bootstrap_model, reload_model

        bootstrap_model(n=100, seed=42)
        # Should not raise
        reload_model()

    def test_predict_without_model_raises(self, tmp_model_dir):
        from app.ml.service import predict_duration, _cached_bundle
        import app.ml.service as svc
        svc._cached_bundle = None

        with pytest.raises(FileNotFoundError):
            predict_duration([{"stage_type": "writing"}])
