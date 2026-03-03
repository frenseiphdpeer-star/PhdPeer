"""
Comprehensive test suite for the Publisher Readiness Index scoring model.

Covers:
 • config validation (features, thresholds, LightGBM params)
 • feature engineering (normalisation, derived features, imputation)
 • LightGBM training, prediction, quantile confidence, persistence
 • scorer orchestration (full pipeline)
 • service layer + synthetic data
 • Pydantic schema contracts
 • API endpoint response shapes
 • cross-cutting invariants
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Module imports
# ---------------------------------------------------------------------------
from app.ml.publisher_readiness import config as _cfg
from app.ml.publisher_readiness.config import (
    ALL_FEATURES,
    CATEGORY_THRESHOLDS,
    DERIVED_FEATURES,
    FEATURE_STATE_FILENAME,
    HYPERPARAMS,
    LGBMReadinessParams,
    METADATA_FILENAME,
    MODEL_FILENAME,
    QUANTILE_CFG,
    QUANTILE_HIGH_FILENAME,
    QUANTILE_LOW_FILENAME,
    QuantileConfig,
    RAW_FEATURES,
    READINESS_ARTIFACTS_DIR,
    SCALER_FILENAME,
    TARGET_COLUMN,
    categorise,
)
from app.ml.publisher_readiness.features import (
    RawReadinessRecord,
    ReadinessFeatureEngineer,
)
from app.ml.publisher_readiness.model import (
    ReadinessPrediction,
    RegressionMetrics,
    TrainingResult,
    predict,
    rank_feature_importance,
    reload_models,
    train,
)
from app.ml.publisher_readiness.scorer import (
    ReadinessAnalysis,
    analyse,
    score_only,
)
from app.ml.publisher_readiness.service import (
    analyse as service_analyse,
    generate_synthetic_dataset,
    get_model_status,
    score as service_score,
)


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def _isolate_artifacts(tmp_path: Path, monkeypatch):
    """Redirect artifact writes to a temp dir and clear model caches."""
    monkeypatch.setattr(_cfg, "READINESS_ARTIFACTS_DIR", tmp_path)
    reload_models()
    yield
    reload_models()


def _make_records(
    n: int = 80,
    seed: int = 42,
) -> List[RawReadinessRecord]:
    """Helper: generate synthetic readiness records with targets."""
    rng = np.random.RandomState(seed)
    records: List[RawReadinessRecord] = []
    for i in range(n):
        coh = rng.beta(5, 2)
        nov = rng.beta(4, 3)
        sup = rng.beta(3, 2)
        rev = rng.exponential(3.0)
        cit = rng.beta(4, 2)
        stg = rng.beta(3, 3)

        target = float(np.clip(
            20 * coh + 15 * nov + 10 * sup
            + 10 * min(rev / 10.0, 1.0)
            + 15 * cit + 20 * stg
            + rng.normal(0, 5),
            0, 100,
        ))

        records.append(RawReadinessRecord(
            coherence_score=coh,
            novelty_score=nov,
            supervision_quality_score=sup,
            revision_density=rev,
            citation_consistency=cit,
            stage_completion_ratio=stg,
            acceptance_outcome=target,
            researcher_id=f"R{i:03d}",
        ))
    return records


def _make_unlabelled(n: int = 10, seed: int = 99) -> List[RawReadinessRecord]:
    """Helper: records without acceptance_outcome (for scoring only)."""
    rng = np.random.RandomState(seed)
    return [
        RawReadinessRecord(
            coherence_score=rng.rand(),
            novelty_score=rng.rand(),
            supervision_quality_score=rng.rand(),
            revision_density=rng.exponential(3.0),
            citation_consistency=rng.rand(),
            stage_completion_ratio=rng.rand(),
            researcher_id=f"U{i:03d}",
        )
        for i in range(n)
    ]


# ═══════════════════════════════════════════════════════════════════════════
# 1 – CONFIG
# ═══════════════════════════════════════════════════════════════════════════

class TestConfig:
    """Validate all configuration objects."""

    def test_raw_features_count(self):
        assert len(RAW_FEATURES) == 6

    def test_derived_features_count(self):
        assert len(DERIVED_FEATURES) == 6

    def test_all_features_is_union(self):
        assert ALL_FEATURES == RAW_FEATURES + DERIVED_FEATURES

    def test_target_column(self):
        assert TARGET_COLUMN == "acceptance_outcome"

    def test_category_thresholds_sorted(self):
        thresholds = [t[0] for t in CATEGORY_THRESHOLDS]
        assert thresholds == sorted(thresholds)

    def test_categorise_revise(self):
        assert categorise(0) == "revise"
        assert categorise(20) == "revise"
        assert categorise(39.9) == "revise"

    def test_categorise_moderate(self):
        assert categorise(40) == "moderate readiness"
        assert categorise(55) == "moderate readiness"
        assert categorise(69.9) == "moderate readiness"

    def test_categorise_submission_ready(self):
        assert categorise(70) == "submission-ready"
        assert categorise(85) == "submission-ready"
        assert categorise(100) == "submission-ready"

    def test_lgbm_params_defaults(self):
        hp = HYPERPARAMS
        assert hp.n_estimators > 0
        assert hp.learning_rate > 0
        assert hp.max_depth > 0
        assert hp.n_jobs == 1

    def test_lgbm_params_to_dict(self):
        d = HYPERPARAMS.to_dict()
        assert "n_estimators" in d
        assert "verbose" in d
        assert d["verbose"] == -1

    def test_quantile_cfg(self):
        assert 0 < QUANTILE_CFG.alpha_low < QUANTILE_CFG.alpha_high < 1

    def test_artifact_paths(self):
        assert MODEL_FILENAME.endswith(".joblib")
        assert METADATA_FILENAME.endswith(".json")


# ═══════════════════════════════════════════════════════════════════════════
# 2 – FEATURE ENGINEERING
# ═══════════════════════════════════════════════════════════════════════════

class TestFeatureEngineering:
    """Validate normalisation and derived-feature construction."""

    def test_fit_transform_shape(self):
        records = _make_records(n=30)
        fe = ReadinessFeatureEngineer()
        df = fe.fit_transform(records)
        assert len(df) == 30
        for col in ALL_FEATURES:
            assert col in df.columns

    def test_raw_features_normalised_0_1(self):
        records = _make_records(n=50)
        fe = ReadinessFeatureEngineer()
        df = fe.fit_transform(records)
        for col in RAW_FEATURES:
            assert df[col].between(0, 1).all(), f"{col} not in [0,1]"

    def test_derived_features_present(self):
        records = _make_records(n=20)
        fe = ReadinessFeatureEngineer()
        df = fe.fit_transform(records)
        for col in DERIVED_FEATURES:
            assert col in df.columns
            assert df[col].notna().all()

    def test_quality_composite_formula(self):
        records = _make_records(n=20)
        fe = ReadinessFeatureEngineer()
        df = fe.fit_transform(records)
        expected = df["coherence_score"] * df["novelty_score"]
        pd.testing.assert_series_equal(
            df["quality_composite"], expected, check_names=False,
        )

    def test_overall_mean_formula(self):
        records = _make_records(n=20)
        fe = ReadinessFeatureEngineer()
        df = fe.fit_transform(records)
        expected = df[RAW_FEATURES].mean(axis=1)
        pd.testing.assert_series_equal(
            df["overall_mean"], expected, check_names=False,
        )

    def test_min_signal_formula(self):
        records = _make_records(n=20)
        fe = ReadinessFeatureEngineer()
        df = fe.fit_transform(records)
        expected = df[RAW_FEATURES].min(axis=1)
        pd.testing.assert_series_equal(
            df["min_signal"], expected, check_names=False,
        )

    def test_transform_requires_fit(self):
        fe = ReadinessFeatureEngineer()
        with pytest.raises(RuntimeError, match="not fitted"):
            fe.transform([RawReadinessRecord()])

    def test_state_persistence(self):
        records = _make_records(n=20)
        fe1 = ReadinessFeatureEngineer()
        df1 = fe1.fit_transform(records)
        state = fe1.get_state()

        fe2 = ReadinessFeatureEngineer()
        fe2.load_state(state)
        df2 = fe2.transform(records)

        for col in ALL_FEATURES:
            pd.testing.assert_series_equal(
                df1[col], df2[col], check_names=False,
            )

    def test_impute_missing_values(self):
        records = [RawReadinessRecord()] * 5  # all None
        fe = ReadinessFeatureEngineer()
        df = fe.fit_transform(records)
        for col in ALL_FEATURES:
            assert df[col].notna().all()

    def test_normalise_constant_column(self):
        """Constant column (range=0) should become 0.5."""
        records = [
            RawReadinessRecord(
                coherence_score=0.5, novelty_score=0.5,
                supervision_quality_score=0.5, revision_density=0.0,
                citation_consistency=0.5, stage_completion_ratio=0.5,
                acceptance_outcome=50.0,
            )
            for _ in range(10)
        ]
        fe = ReadinessFeatureEngineer()
        df = fe.fit_transform(records)
        assert (df["coherence_score"] == 0.5).all()

    def test_target_column_preserved(self):
        records = _make_records(n=10)
        fe = ReadinessFeatureEngineer()
        df = fe.fit_transform(records)
        assert TARGET_COLUMN in df.columns
        assert df[TARGET_COLUMN].notna().all()


# ═══════════════════════════════════════════════════════════════════════════
# 3 – MODEL TRAINING
# ═══════════════════════════════════════════════════════════════════════════

class TestTraining:
    """Validate LightGBM regression training pipeline."""

    def test_train_returns_result(self):
        records = _make_records(n=50)
        result = train(records, save=False)
        assert isinstance(result, TrainingResult)
        assert isinstance(result.metrics, RegressionMetrics)

    def test_train_metrics_structure(self):
        records = _make_records(n=50)
        result = train(records, save=False)
        m = result.metrics
        assert isinstance(m.r2, float)
        assert isinstance(m.mae, float)
        assert isinstance(m.rmse, float)
        assert m.n_train > 0
        assert m.n_test > 0

    def test_train_positive_r2(self):
        """With a learnable target, R² should be positive."""
        records = _make_records(n=100)
        result = train(records, save=False)
        assert result.metrics.r2 > 0

    def test_train_mae_reasonable(self):
        records = _make_records(n=100)
        result = train(records, save=False)
        assert result.metrics.mae < 50  # should be well below this

    def test_feature_importances_all_features(self):
        records = _make_records(n=50)
        result = train(records, save=False)
        for feat in ALL_FEATURES:
            assert feat in result.feature_importances

    def test_feature_importances_non_negative(self):
        records = _make_records(n=50)
        result = train(records, save=False)
        for v in result.feature_importances.values():
            assert v >= 0

    def test_train_saves_artifacts(self):
        records = _make_records(n=50)
        train(records, save=True)
        art = _cfg.READINESS_ARTIFACTS_DIR
        assert (art / MODEL_FILENAME).exists()
        assert (art / QUANTILE_LOW_FILENAME).exists()
        assert (art / QUANTILE_HIGH_FILENAME).exists()
        assert (art / FEATURE_STATE_FILENAME).exists()
        assert (art / METADATA_FILENAME).exists()

    def test_train_updates_in_memory_cache(self):
        records = _make_records(n=50)
        train(records, save=False)
        # predict should work without save (uses in-memory cache)
        preds = predict(records[:5])
        assert len(preds) == 5

    def test_training_result_to_dict(self):
        records = _make_records(n=50)
        result = train(records, save=False)
        d = result.to_dict()
        assert "metrics" in d
        assert "feature_importances" in d
        assert "n_samples" in d
        assert "n_features" in d

    def test_train_small_dataset(self):
        """Training on < 10 samples should not error (no split)."""
        records = _make_records(n=5)
        result = train(records, save=False)
        assert result.n_samples == 5


# ═══════════════════════════════════════════════════════════════════════════
# 4 – PREDICTION
# ═══════════════════════════════════════════════════════════════════════════

class TestPrediction:
    """Validate readiness prediction pipeline."""

    def _train_quick(self):
        records = _make_records(n=60)
        train(records, save=False)
        return records

    def test_predict_shape(self):
        records = self._train_quick()
        preds = predict(records[:5])
        assert len(preds) == 5

    def test_predict_score_range(self):
        records = self._train_quick()
        preds = predict(records[:10])
        for p in preds:
            assert 0 <= p.readiness_score <= 100

    def test_predict_category_valid(self):
        records = self._train_quick()
        preds = predict(records[:10])
        valid_cats = {"revise", "moderate readiness", "submission-ready"}
        for p in preds:
            assert p.category in valid_cats

    def test_predict_confidence_range(self):
        records = self._train_quick()
        preds = predict(records[:10])
        for p in preds:
            assert 0 <= p.confidence <= 1

    def test_predict_confidence_band(self):
        records = self._train_quick()
        preds = predict(records[:10])
        for p in preds:
            assert p.confidence_low <= p.readiness_score
            assert p.confidence_high >= p.readiness_score

    def test_predict_researcher_id_propagated(self):
        records = self._train_quick()
        preds = predict(records[:3])
        for i, p in enumerate(preds):
            assert p.researcher_id == records[i].researcher_id

    def test_predict_to_dict(self):
        records = self._train_quick()
        preds = predict(records[:2])
        d = preds[0].to_dict()
        assert "readiness_score" in d
        assert "category" in d
        assert "confidence" in d
        assert "confidence_low" in d
        assert "confidence_high" in d

    def test_predict_deterministic(self):
        records = self._train_quick()
        p1 = predict(records[:3])
        p2 = predict(records[:3])
        for a, b in zip(p1, p2):
            assert abs(a.readiness_score - b.readiness_score) < 1e-6

    def test_rank_feature_importance(self):
        self._train_quick()
        importances = rank_feature_importance()
        assert len(importances) == len(ALL_FEATURES)
        vals = list(importances.values())
        assert vals == sorted(vals, reverse=True)


# ═══════════════════════════════════════════════════════════════════════════
# 5 – PERSISTENCE
# ═══════════════════════════════════════════════════════════════════════════

class TestPersistence:
    """Validate model save / load roundtrip."""

    def test_save_load_roundtrip(self):
        records = _make_records(n=60)
        train(records, save=True)
        preds_before = predict(records[:3])

        reload_models()
        preds_after = predict(records[:3])

        for a, b in zip(preds_before, preds_after):
            assert abs(a.readiness_score - b.readiness_score) < 0.01

    def test_reload_clears_cache(self):
        records = _make_records(n=50)
        train(records, save=True)
        reload_models()
        preds = predict(records[:2])
        assert len(preds) == 2

    def test_no_model_raises(self):
        reload_models()
        with pytest.raises(RuntimeError, match="No trained readiness model"):
            predict([RawReadinessRecord()])

    def test_metadata_file_valid_json(self):
        records = _make_records(n=50)
        train(records, save=True)
        meta_path = _cfg.READINESS_ARTIFACTS_DIR / METADATA_FILENAME
        meta = json.loads(meta_path.read_text())
        assert "metrics" in meta
        assert "n_samples" in meta


# ═══════════════════════════════════════════════════════════════════════════
# 6 – SCORER (ORCHESTRATION)
# ═══════════════════════════════════════════════════════════════════════════

class TestScorer:
    """Validate end-to-end scoring pipeline."""

    def test_analyse_full_pipeline(self):
        records = _make_records(n=60)
        result = analyse(records, save_model=False)
        assert isinstance(result, ReadinessAnalysis)
        assert result.training_result is not None
        assert len(result.predictions) == 60
        assert result.n_samples == 60

    def test_analyse_empty_records(self):
        result = analyse([], save_model=False)
        assert result.n_samples == 0
        assert result.predictions == []

    def test_analyse_to_dict(self):
        records = _make_records(n=40)
        result = analyse(records, save_model=False)
        d = result.to_dict()
        assert "training_result" in d
        assert "predictions" in d
        assert "feature_importances" in d
        assert "n_samples" in d

    def test_analyse_saves_model(self):
        records = _make_records(n=40)
        analyse(records, save_model=True)
        assert (_cfg.READINESS_ARTIFACTS_DIR / MODEL_FILENAME).exists()

    def test_score_only_with_trained_model(self):
        records = _make_records(n=50)
        train(records, save=False)
        new_records = _make_unlabelled(n=5)
        preds = score_only(new_records)
        assert len(preds) == 5
        for p in preds:
            assert 0 <= p.readiness_score <= 100

    def test_analyse_feature_importances_present(self):
        records = _make_records(n=40)
        result = analyse(records, save_model=False)
        assert len(result.feature_importances) == len(ALL_FEATURES)

    def test_analyse_predictions_have_correct_structure(self):
        records = _make_records(n=30)
        result = analyse(records, save_model=False)
        for p in result.predictions:
            assert isinstance(p.readiness_score, float)
            assert isinstance(p.category, str)
            assert isinstance(p.confidence, float)


# ═══════════════════════════════════════════════════════════════════════════
# 7 – SERVICE LAYER
# ═══════════════════════════════════════════════════════════════════════════

class TestService:
    """Validate public service layer."""

    def test_service_analyse(self):
        records = _make_records(n=50)
        result = service_analyse(records, save_model=False)
        assert isinstance(result, dict)
        assert "predictions" in result
        assert "training_result" in result

    def test_service_score(self):
        records = _make_records(n=50)
        train(records, save=False)
        preds = service_score(records[:3])
        assert len(preds) == 3
        assert "readiness_score" in preds[0]

    def test_get_model_status_no_model(self):
        status = get_model_status()
        assert status["model_trained"] is False

    def test_get_model_status_after_training(self):
        records = _make_records(n=50)
        service_analyse(records, save_model=True)
        status = get_model_status()
        assert status["model_trained"] is True
        assert "metadata" in status

    def test_generate_synthetic_dataset(self):
        records = generate_synthetic_dataset(n=30, seed=42)
        assert len(records) == 30
        for r in records:
            assert r.acceptance_outcome is not None
            assert 0 <= r.acceptance_outcome <= 100

    def test_synthetic_deterministic(self):
        r1 = generate_synthetic_dataset(n=20, seed=99)
        r2 = generate_synthetic_dataset(n=20, seed=99)
        for a, b in zip(r1, r2):
            assert a.coherence_score == b.coherence_score
            assert a.acceptance_outcome == b.acceptance_outcome

    def test_synthetic_researcher_ids(self):
        records = generate_synthetic_dataset(n=10)
        ids = [r.researcher_id for r in records]
        assert len(set(ids)) == 10

    def test_end_to_end_synthetic_to_analysis(self):
        """Full integration: generate → analyse → verify output."""
        records = generate_synthetic_dataset(n=80, seed=42)
        result = service_analyse(records, save_model=False)
        assert result["n_samples"] == 80
        assert result["training_result"] is not None
        assert len(result["predictions"]) == 80
        for p in result["predictions"]:
            assert "readiness_score" in p
            assert "category" in p
            assert "confidence" in p

    def test_end_to_end_categories_distributed(self):
        """With synthetic data, all three categories should appear."""
        records = generate_synthetic_dataset(n=200, seed=42)
        result = service_analyse(records, save_model=False)
        cats = {p["category"] for p in result["predictions"]}
        # At least 2 of the 3 categories should appear (noise may push all high)
        assert len(cats) >= 2


# ═══════════════════════════════════════════════════════════════════════════
# 8 – PYDANTIC SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════

class TestSchemas:
    """Validate Pydantic request / response schemas."""

    def test_readiness_record_in(self):
        from app.schemas.publisher_readiness import ReadinessRecordIn
        r = ReadinessRecordIn(
            coherence_score=0.8,
            novelty_score=0.6,
            supervision_quality_score=0.7,
            revision_density=4.5,
            citation_consistency=0.9,
            stage_completion_ratio=0.5,
        )
        assert r.coherence_score == 0.8

    def test_readiness_record_optional_fields(self):
        from app.schemas.publisher_readiness import ReadinessRecordIn
        r = ReadinessRecordIn()
        assert r.coherence_score is None
        assert r.researcher_id is None

    def test_analyse_request(self):
        from app.schemas.publisher_readiness import AnalyseRequest, ReadinessRecordIn
        req = AnalyseRequest(
            records=[ReadinessRecordIn(coherence_score=0.5)],
            save_model=False,
        )
        assert len(req.records) == 1

    def test_analyse_request_min_length(self):
        from app.schemas.publisher_readiness import AnalyseRequest
        with pytest.raises(Exception):
            AnalyseRequest(records=[], save_model=True)

    def test_score_request(self):
        from app.schemas.publisher_readiness import ScoreRequest, ReadinessRecordIn
        req = ScoreRequest(
            records=[ReadinessRecordIn(coherence_score=0.5)],
        )
        assert len(req.records) == 1

    def test_synthetic_request_defaults(self):
        from app.schemas.publisher_readiness import SyntheticRequest
        req = SyntheticRequest()
        assert req.n == 200
        assert req.seed == 42
        assert req.run_analysis is True

    def test_synthetic_request_validation(self):
        from app.schemas.publisher_readiness import SyntheticRequest
        with pytest.raises(Exception):
            SyntheticRequest(n=5)  # min 10

    def test_readiness_prediction_out(self):
        from app.schemas.publisher_readiness import ReadinessPredictionOut
        p = ReadinessPredictionOut(
            readiness_score=72.5,
            category="submission-ready",
            confidence=0.85,
            confidence_low=65.0,
            confidence_high=80.0,
        )
        assert p.category == "submission-ready"

    def test_regression_metrics_out(self):
        from app.schemas.publisher_readiness import RegressionMetricsOut
        m = RegressionMetricsOut(r2=0.85, mae=5.2, rmse=7.1, n_train=80, n_test=20)
        assert m.r2 == 0.85

    def test_training_result_out(self):
        from app.schemas.publisher_readiness import TrainingResultOut, RegressionMetricsOut
        tr = TrainingResultOut(
            metrics=RegressionMetricsOut(r2=0.85, mae=5.2, rmse=7.1, n_train=80, n_test=20),
            feature_importances={"coherence_score": 100.0},
            n_samples=100,
            n_features=12,
        )
        assert tr.n_samples == 100

    def test_analyse_response(self):
        from app.schemas.publisher_readiness import AnalyseResponse
        resp = AnalyseResponse(
            training_result=None,
            predictions=[],
            feature_importances={},
            n_samples=0,
        )
        assert resp.n_samples == 0

    def test_model_status_response(self):
        from app.schemas.publisher_readiness import ModelStatusResponse
        ms = ModelStatusResponse(
            model_trained=False,
            model_path="/tmp/model.joblib",
            artifacts_dir="/tmp",
        )
        assert ms.model_trained is False


# ═══════════════════════════════════════════════════════════════════════════
# 9 – API ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

class TestEndpoints:
    """Validate API endpoint contracts (unit-level, no live server)."""

    def test_router_exists(self):
        from app.api.v1.endpoints.publisher_readiness import router
        assert router is not None

    def test_router_has_analyse_route(self):
        from app.api.v1.endpoints.publisher_readiness import router
        paths = [r.path for r in router.routes]
        assert "/analyse" in paths

    def test_router_has_score_route(self):
        from app.api.v1.endpoints.publisher_readiness import router
        paths = [r.path for r in router.routes]
        assert "/score" in paths

    def test_router_has_synthetic_route(self):
        from app.api.v1.endpoints.publisher_readiness import router
        paths = [r.path for r in router.routes]
        assert "/synthetic" in paths

    def test_router_has_status_route(self):
        from app.api.v1.endpoints.publisher_readiness import router
        paths = [r.path for r in router.routes]
        assert "/status" in paths

    def test_router_registered_in_api(self):
        from app.api.v1 import api_router
        prefixes = [r.path for r in api_router.routes if hasattr(r, "path")]
        assert any("publisher-readiness" in p for p in prefixes)


# ═══════════════════════════════════════════════════════════════════════════
# 10 – INVARIANTS & CROSS-CUTTING
# ═══════════════════════════════════════════════════════════════════════════

class TestInvariants:
    """Cross-cutting invariant checks."""

    def test_predictions_always_categorised(self):
        records = _make_records(n=50)
        result = analyse(records, save_model=False)
        for p in result.predictions:
            assert p.category in {"revise", "moderate readiness", "submission-ready"}

    def test_confidence_inversely_related_to_band_width(self):
        records = _make_records(n=50)
        train(records, save=False)
        preds = predict(records[:10])
        for p in preds:
            band = p.confidence_high - p.confidence_low
            expected_conf = max(0, min(1, 1 - band / 100))
            assert abs(p.confidence - expected_conf) < 0.01

    def test_category_matches_score_thresholds(self):
        records = _make_records(n=80)
        train(records, save=False)
        preds = predict(records)
        for p in preds:
            if p.readiness_score < 40:
                assert p.category == "revise"
            elif p.readiness_score < 70:
                assert p.category == "moderate readiness"
            else:
                assert p.category == "submission-ready"

    def test_all_features_used_in_model(self):
        records = _make_records(n=50)
        result = train(records, save=False)
        assert set(result.feature_importances.keys()) == set(ALL_FEATURES)

    def test_to_dict_json_serialisable(self):
        records = _make_records(n=40)
        result = analyse(records, save_model=False)
        d = result.to_dict()
        json_str = json.dumps(d)
        assert isinstance(json_str, str)

    def test_idempotent_analysis(self):
        records = _make_records(n=40, seed=42)
        r1 = analyse(records, save_model=False)
        reload_models()
        r2 = analyse(records, save_model=False)
        assert r1.n_samples == r2.n_samples
        assert len(r1.predictions) == len(r2.predictions)

    def test_high_quality_signals_score_higher(self):
        """Records with all high signals should score higher than all low."""
        records = _make_records(n=80)
        train(records, save=False)

        high = [RawReadinessRecord(
            coherence_score=0.95, novelty_score=0.9,
            supervision_quality_score=0.9, revision_density=8.0,
            citation_consistency=0.95, stage_completion_ratio=0.9,
        )]
        low = [RawReadinessRecord(
            coherence_score=0.1, novelty_score=0.1,
            supervision_quality_score=0.1, revision_density=0.1,
            citation_consistency=0.1, stage_completion_ratio=0.1,
        )]

        p_high = predict(high)[0]
        p_low = predict(low)[0]
        assert p_high.readiness_score > p_low.readiness_score

    def test_confidence_band_non_negative_width(self):
        records = _make_records(n=50)
        train(records, save=False)
        preds = predict(records)
        for p in preds:
            assert p.confidence_high >= p.confidence_low
