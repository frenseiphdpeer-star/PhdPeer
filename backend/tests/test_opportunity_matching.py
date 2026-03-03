"""
Tests for the Opportunity Matching Engine.

Covers:
  * Configuration defaults, feature catalogue, scoring weights
  * Embeddings (sentence-transformer encode, cosine similarity)
  * Feature engineering (urgency, one-hot encoding, imputation, state roundtrip)
  * LightGBM training (metrics validation, feature importances, persistence)
  * Prediction (match_score bounds, success_probability bounds, ranking)
  * Recommender (preparation recommendations, readiness labels)
  * Scorer orchestration (end-to-end with pre-computed cosine_similarity)
  * Service layer (match, train, bootstrap, model status)
  * Synthetic data generation (statistics, determinism, label distribution)
  * Edge cases (single record, all-missing values, tiny dataset)

Expensive objects (trained model bundle, embedder) are module-scoped to
avoid redundant computation.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd
import pytest

from app.ml.opportunity_matching.config import (
    ALL_FEATURES,
    DISCIPLINES,
    DISCIPLINE_ONEHOT_FEATURES,
    HYPERPARAMS,
    LGBMRankParams,
    NUMERIC_FEATURES,
    SCORING,
    STAGE_ONEHOT_FEATURES,
    STAGE_TYPES,
    TARGET_COLUMN,
)
from app.ml.opportunity_matching.features import (
    MatchFeatureEngineer,
    MatchRecord,
    compute_urgency,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_record(
    *,
    cos_sim: float = 0.65,
    stage: str = "writing",
    res_disc: str = "computer_science",
    opp_disc: str = "computer_science",
    psr: float = 0.5,
    pac: int = 3,
    trs: float = 0.7,
    days: float = 30.0,
    accepted: int | None = None,
) -> MatchRecord:
    return MatchRecord(
        cosine_similarity=cos_sim,
        stage_type=stage,
        researcher_discipline=res_disc,
        opportunity_discipline=opp_disc,
        prior_success_rate=psr,
        prior_application_count=pac,
        timeline_readiness_score=trs,
        days_to_deadline=days,
        accepted=accepted,
    )


def _make_training_records(n: int = 200, seed: int = 42) -> List[MatchRecord]:
    from app.ml.opportunity_matching.service import generate_synthetic_dataset
    return generate_synthetic_dataset(n=n, seed=seed)


def _safe_lgbm_params() -> LGBMRankParams:
    """Small, fast LightGBM params for tests."""
    return LGBMRankParams(
        n_estimators=20,
        learning_rate=0.1,
        max_depth=3,
        num_leaves=15,
        min_child_samples=2,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_alpha=0.0,
        reg_lambda=1.0,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def synthetic_records() -> List[MatchRecord]:
    return _make_training_records(n=200)


@pytest.fixture(scope="module")
def trained_bundle(synthetic_records):
    """Train once and return the in-memory bundle."""
    from lightgbm import LGBMClassifier

    from app.ml.opportunity_matching.model import train

    result = train(synthetic_records, save=False, params=_safe_lgbm_params())

    # Rebuild bundle for injection
    fe = MatchFeatureEngineer()
    df = fe.fit_transform(synthetic_records)
    X = df[ALL_FEATURES].values.astype(np.float32)
    y = df[TARGET_COLUMN].values.astype(int)

    clf = LGBMClassifier(**_safe_lgbm_params().to_dict())
    clf.fit(X, y)

    bundle = {"model": clf, "feature_engineer": fe}
    return {"result": result, "bundle": bundle}


@pytest.fixture(scope="module")
def embedder():
    """Module-scoped sentence-transformer embedder."""
    from app.ml.opportunity_matching.embeddings import OpportunityEmbedder
    return OpportunityEmbedder()


# =========================================================================
# 1. Configuration
# =========================================================================

class TestConfig:

    def test_numeric_feature_count(self):
        assert len(NUMERIC_FEATURES) == 7

    def test_stage_onehot_count(self):
        assert len(STAGE_ONEHOT_FEATURES) == len(STAGE_TYPES)

    def test_discipline_onehot_count(self):
        assert len(DISCIPLINE_ONEHOT_FEATURES) == len(DISCIPLINES)

    def test_all_features_union(self):
        expected_len = len(NUMERIC_FEATURES) + len(STAGE_ONEHOT_FEATURES) + len(DISCIPLINE_ONEHOT_FEATURES)
        assert len(ALL_FEATURES) == expected_len

    def test_scoring_weights_sum_to_one(self):
        SCORING.validate()

    def test_target_column(self):
        assert TARGET_COLUMN == "accepted"

    def test_lgbm_hyperparams_dict(self):
        d = HYPERPARAMS.to_dict()
        assert d["n_estimators"] == 300
        assert d["learning_rate"] == 0.05
        assert isinstance(d, dict)


# =========================================================================
# 2. Embeddings
# =========================================================================

class TestEmbeddings:

    def test_encode_single_text(self, embedder):
        vecs = embedder.encode("A brief research proposal about NLP.")
        assert vecs.shape == (1, embedder.dimension)

    def test_encode_batch(self, embedder):
        texts = ["proposal A", "proposal B", "proposal C"]
        vecs = embedder.encode(texts)
        assert vecs.shape == (3, embedder.dimension)

    def test_vectors_are_normalised(self, embedder):
        vecs = embedder.encode("test normalisation")
        norm = np.linalg.norm(vecs[0])
        assert abs(norm - 1.0) < 1e-5

    def test_cosine_similarity_same_text(self, embedder):
        vec = embedder.encode("identical text")
        sim = embedder.cosine_similarity(vec[0], vec[0])
        assert sim == pytest.approx(1.0, abs=1e-4)

    def test_cosine_similarity_different_texts(self, embedder):
        va = embedder.encode("deep learning for computer vision")[0]
        vb = embedder.encode("medieval history of Eastern Europe")[0]
        sim = embedder.cosine_similarity(va, vb)
        assert 0.0 <= sim < 0.8  # clearly different

    def test_cosine_similarity_related_texts(self, embedder):
        va = embedder.encode("machine learning for protein folding")[0]
        vb = embedder.encode("deep learning applied to protein structure prediction")[0]
        sim = embedder.cosine_similarity(va, vb)
        assert sim > 0.5  # semantically related

    def test_dimension_positive(self, embedder):
        assert embedder.dimension > 0


# =========================================================================
# 3. Feature Engineering
# =========================================================================

class TestFeatureEngineering:

    def test_urgency_near_deadline(self):
        assert compute_urgency(3.0) == pytest.approx(1.0)

    def test_urgency_far_deadline(self):
        assert compute_urgency(200.0) == pytest.approx(0.0)

    def test_urgency_moderate_deadline(self):
        urg = compute_urgency(60.0)
        assert 0.0 < urg < 1.0

    def test_urgency_none(self):
        assert compute_urgency(None) == 0.0

    def test_urgency_negative(self):
        assert compute_urgency(-5.0) == 0.0

    def test_fit_transform_all_features(self):
        records = [_make_record(accepted=0), _make_record(accepted=1)]
        fe = MatchFeatureEngineer()
        df = fe.fit_transform(records)
        for col in ALL_FEATURES:
            assert col in df.columns, f"Missing: {col}"

    def test_transform_requires_fit(self):
        fe = MatchFeatureEngineer()
        with pytest.raises(RuntimeError, match="not fitted"):
            fe.transform([_make_record()])

    def test_onehot_encoding_stage(self):
        rec = _make_record(stage="proposal", accepted=0)
        fe = MatchFeatureEngineer()
        df = fe.fit_transform([rec])
        assert df["stage_proposal"].iloc[0] == 1.0
        assert df["stage_writing"].iloc[0] == 0.0

    def test_onehot_encoding_discipline(self):
        rec = _make_record(res_disc="physics", accepted=0)
        fe = MatchFeatureEngineer()
        df = fe.fit_transform([rec])
        assert df["disc_physics"].iloc[0] == 1.0
        assert df["disc_computer_science"].iloc[0] == 0.0

    def test_discipline_match_flag(self):
        rec_match = _make_record(res_disc="biology", opp_disc="biology", accepted=0)
        rec_mismatch = _make_record(res_disc="biology", opp_disc="physics", accepted=0)
        fe = MatchFeatureEngineer()
        df = fe.fit_transform([rec_match, rec_mismatch])
        assert df["discipline_match"].iloc[0] == 1.0
        assert df["discipline_match"].iloc[1] == 0.0

    def test_imputation_fills_nans(self):
        rec = MatchRecord(accepted=0)  # all None
        good = _make_record(accepted=1)
        fe = MatchFeatureEngineer()
        df = fe.fit_transform([good, rec])
        # All features should be non-null
        for col in ALL_FEATURES:
            assert not pd.isna(df[col].iloc[1])

    def test_state_roundtrip(self):
        records = [_make_record(accepted=i % 2) for i in range(10)]
        fe1 = MatchFeatureEngineer()
        fe1.fit_transform(records)
        state = fe1.get_state()

        fe2 = MatchFeatureEngineer()
        fe2.load_state(state)
        df2 = fe2.transform([_make_record()])
        for col in ALL_FEATURES:
            assert col in df2.columns

    def test_target_column_present(self):
        records = [_make_record(accepted=0), _make_record(accepted=1)]
        fe = MatchFeatureEngineer()
        df = fe.fit_transform(records)
        assert TARGET_COLUMN in df.columns

    def test_urgency_score_populated(self):
        rec = _make_record(days=10.0, accepted=0)
        fe = MatchFeatureEngineer()
        df = fe.fit_transform([rec])
        assert df["urgency_score"].iloc[0] > 0


# =========================================================================
# 4. Model Training
# =========================================================================

class TestModelTraining:

    def test_training_returns_result(self, trained_bundle):
        result = trained_bundle["result"]
        assert result.n_samples == 200
        assert result.n_features == len(ALL_FEATURES)

    def test_metrics_populated(self, trained_bundle):
        m = trained_bundle["result"].metrics
        assert 0 <= m.auc_roc <= 1
        assert 0 <= m.auc_pr <= 1
        assert 0 <= m.precision <= 1
        assert 0 <= m.recall <= 1
        assert 0 <= m.f1 <= 1
        assert m.n_test > 0

    def test_auc_above_chance(self, trained_bundle):
        m = trained_bundle["result"].metrics
        assert m.auc_roc > 0.5

    def test_feature_importances(self, trained_bundle):
        imp = trained_bundle["result"].feature_importances
        assert len(imp) == len(ALL_FEATURES)
        assert max(imp.values()) > 0

    def test_training_result_serializes(self, trained_bundle):
        d = trained_bundle["result"].to_dict()
        assert "metrics" in d
        assert "feature_importances" in d
        assert isinstance(d["n_samples"], int)

    def test_save_and_load_roundtrip(self, synthetic_records, tmp_path):
        import app.ml.opportunity_matching.config as cfg
        import app.ml.opportunity_matching.model as mdl

        original_dir = cfg.MATCHING_ARTIFACTS_DIR
        original_cache = mdl._cached_bundle
        try:
            cfg.MATCHING_ARTIFACTS_DIR = tmp_path
            mdl._cached_bundle = None

            from app.ml.opportunity_matching.model import train, predict as model_predict
            train(synthetic_records, save=True, params=_safe_lgbm_params())

            assert (tmp_path / cfg.MODEL_FILENAME).exists()
            assert (tmp_path / cfg.FEATURE_STATE_FILENAME).exists()
            assert (tmp_path / cfg.METADATA_FILENAME).exists()

            mdl._cached_bundle = None
            preds = model_predict([_make_record()])
            assert len(preds) == 1
            assert 0 <= preds[0].match_score <= 100
        finally:
            cfg.MATCHING_ARTIFACTS_DIR = original_dir
            mdl._cached_bundle = original_cache


# =========================================================================
# 5. Prediction
# =========================================================================

class TestPrediction:

    def test_predict_single(self, trained_bundle):
        from app.ml.opportunity_matching.model import predict
        preds = predict([_make_record()], _bundle=trained_bundle["bundle"])
        assert len(preds) == 1
        p = preds[0]
        assert 0 <= p.match_score <= 100
        assert 0 <= p.success_probability <= 1
        assert 0 <= p.cosine_similarity <= 1
        assert 0 <= p.urgency_score <= 1

    def test_predict_batch(self, trained_bundle):
        from app.ml.opportunity_matching.model import predict
        records = [_make_record(cos_sim=0.3 + i * 0.1) for i in range(5)]
        preds = predict(records, _bundle=trained_bundle["bundle"])
        assert len(preds) == 5

    def test_high_quality_scores_higher(self, trained_bundle):
        from app.ml.opportunity_matching.model import predict
        good = _make_record(cos_sim=0.95, psr=0.9, trs=0.95, days=5.0)
        weak = _make_record(cos_sim=0.1, psr=0.0, trs=0.1, days=300.0)
        preds = predict([good, weak], _bundle=trained_bundle["bundle"])
        assert preds[0].match_score > preds[1].match_score

    def test_prediction_serializes(self, trained_bundle):
        from app.ml.opportunity_matching.model import predict
        preds = predict([_make_record()], _bundle=trained_bundle["bundle"])
        d = preds[0].to_dict()
        assert "match_score" in d
        assert "success_probability" in d
        assert "cosine_similarity" in d
        assert "urgency_score" in d


# =========================================================================
# 6. Recommender
# =========================================================================

class TestRecommender:

    def test_tight_deadline_high_priority(self):
        from app.ml.opportunity_matching.recommender import generate_recommendations
        rec = _make_record(days=5.0)
        plan = generate_recommendations(
            rec, success_probability=0.5, cosine_similarity=0.7, match_score=60,
        )
        priorities = [r.priority for r in plan.recommendations]
        assert "high" in priorities

    def test_low_similarity_triggers_writing_rec(self):
        from app.ml.opportunity_matching.recommender import generate_recommendations
        rec = _make_record(cos_sim=0.2)
        plan = generate_recommendations(
            rec, success_probability=0.5, cosine_similarity=0.2, match_score=50,
        )
        categories = [r.category for r in plan.recommendations]
        assert "writing" in categories

    def test_discipline_mismatch_triggers_networking(self):
        from app.ml.opportunity_matching.recommender import generate_recommendations
        rec = _make_record(res_disc="biology", opp_disc="physics")
        plan = generate_recommendations(
            rec, success_probability=0.5, cosine_similarity=0.7, match_score=50,
        )
        categories = [r.category for r in plan.recommendations]
        assert "networking" in categories

    def test_low_prior_success_triggers_track_record(self):
        from app.ml.opportunity_matching.recommender import generate_recommendations
        rec = _make_record(psr=0.1)
        plan = generate_recommendations(
            rec, success_probability=0.5, cosine_similarity=0.7, match_score=50,
        )
        categories = [r.category for r in plan.recommendations]
        assert "track_record" in categories

    def test_zero_applications_triggers_experience(self):
        from app.ml.opportunity_matching.recommender import generate_recommendations
        rec = _make_record(pac=0)
        plan = generate_recommendations(
            rec, success_probability=0.5, cosine_similarity=0.7, match_score=50,
        )
        categories = [r.category for r in plan.recommendations]
        assert "experience" in categories

    def test_low_timeline_readiness(self):
        from app.ml.opportunity_matching.recommender import generate_recommendations
        rec = _make_record(trs=0.1)
        plan = generate_recommendations(
            rec, success_probability=0.5, cosine_similarity=0.7, match_score=50,
        )
        categories = [r.category for r in plan.recommendations]
        assert "timeline" in categories

    def test_low_success_probability_strategy(self):
        from app.ml.opportunity_matching.recommender import generate_recommendations
        rec = _make_record()
        plan = generate_recommendations(
            rec, success_probability=0.1, cosine_similarity=0.7, match_score=30,
        )
        categories = [r.category for r in plan.recommendations]
        assert "strategy" in categories

    def test_readiness_label_ready(self):
        from app.ml.opportunity_matching.recommender import generate_recommendations
        rec = _make_record()
        plan = generate_recommendations(
            rec, success_probability=0.7, cosine_similarity=0.9, match_score=80,
        )
        assert plan.readiness_label == "ready"

    def test_readiness_label_stretch(self):
        from app.ml.opportunity_matching.recommender import generate_recommendations
        rec = _make_record()
        plan = generate_recommendations(
            rec, success_probability=0.1, cosine_similarity=0.2, match_score=15,
        )
        assert plan.readiness_label == "stretch_goal"

    def test_all_positive_gives_general_rec(self):
        from app.ml.opportunity_matching.recommender import generate_recommendations
        rec = _make_record(
            cos_sim=0.9, psr=0.8, pac=5, trs=0.9, days=90.0,
        )
        plan = generate_recommendations(
            rec, success_probability=0.8, cosine_similarity=0.9, match_score=80,
        )
        categories = [r.category for r in plan.recommendations]
        assert "general" in categories

    def test_preparation_plan_serializes(self):
        from app.ml.opportunity_matching.recommender import generate_recommendations
        rec = _make_record(days=5.0)
        plan = generate_recommendations(
            rec, success_probability=0.5, cosine_similarity=0.5, match_score=50,
        )
        d = plan.to_dict()
        assert "recommendations" in d
        assert "readiness_label" in d
        assert isinstance(d["recommendations"], list)


# =========================================================================
# 7. Scorer (Orchestration)
# =========================================================================

class TestScorer:

    def test_score_matches_single(self, trained_bundle):
        from app.ml.opportunity_matching.scorer import score_matches
        results = score_matches(
            [_make_record()],
            _bundle=trained_bundle["bundle"],
        )
        assert len(results) == 1
        r = results[0]
        assert 0 <= r.match_score <= 100
        assert r.preparation is not None

    def test_score_matches_batch(self, trained_bundle):
        from app.ml.opportunity_matching.scorer import score_matches
        records = [_make_record(cos_sim=0.3 + i * 0.1) for i in range(4)]
        results = score_matches(records, _bundle=trained_bundle["bundle"])
        assert len(results) == 4

    def test_result_serializes(self, trained_bundle):
        from app.ml.opportunity_matching.scorer import score_matches
        results = score_matches(
            [_make_record()],
            _bundle=trained_bundle["bundle"],
        )
        d = results[0].to_dict()
        assert "match_score" in d
        assert "preparation_recommendation" in d

    def test_score_from_texts(self, trained_bundle, embedder):
        from app.ml.opportunity_matching.scorer import score_from_texts

        researcher_text = "Deep learning for protein structure prediction"
        opp_texts = [
            "Grant for computational biology research",
            "Medieval history fellowship",
        ]
        records = [
            _make_record(cos_sim=None),  # will be computed from texts
            _make_record(cos_sim=None),
        ]
        results = score_from_texts(
            researcher_text,
            opp_texts,
            records=records,
            _bundle=trained_bundle["bundle"],
            _embedder=embedder,
        )
        assert len(results) == 2
        # The biology-related opportunity should score higher
        assert results[0].cosine_similarity > results[1].cosine_similarity


# =========================================================================
# 8. Service Layer
# =========================================================================

class TestService:

    def test_match_opportunities(self, trained_bundle):
        from app.ml.opportunity_matching.service import match_opportunities
        results = match_opportunities(
            [_make_record()],
            _bundle=trained_bundle["bundle"],
        )
        assert len(results) == 1
        r = results[0]
        assert "match_score" in r
        assert "success_probability" in r
        assert "preparation_recommendation" in r

    def test_train_model(self, synthetic_records):
        from app.ml.opportunity_matching.service import train_model
        result = train_model(synthetic_records, save=False)
        assert "metrics" in result
        assert result["n_samples"] == 200

    def test_bootstrap_model(self, tmp_path):
        import app.ml.opportunity_matching.config as cfg
        import app.ml.opportunity_matching.model as mdl

        original_dir = cfg.MATCHING_ARTIFACTS_DIR
        original_cache = mdl._cached_bundle
        try:
            cfg.MATCHING_ARTIFACTS_DIR = tmp_path
            mdl._cached_bundle = None

            from app.ml.opportunity_matching.service import generate_synthetic_dataset
            from app.ml.opportunity_matching.model import train
            records = generate_synthetic_dataset(n=100)
            result = train(records, save=True, params=_safe_lgbm_params())
            assert result.n_samples == 100
            assert (tmp_path / cfg.MODEL_FILENAME).exists()
        finally:
            cfg.MATCHING_ARTIFACTS_DIR = original_dir
            mdl._cached_bundle = original_cache

    def test_get_model_status_no_model(self, tmp_path):
        import app.ml.opportunity_matching.config as cfg
        original = cfg.MATCHING_ARTIFACTS_DIR
        try:
            cfg.MATCHING_ARTIFACTS_DIR = tmp_path
            from app.ml.opportunity_matching.service import get_model_status
            status = get_model_status()
            assert status["loaded"] is False
        finally:
            cfg.MATCHING_ARTIFACTS_DIR = original

    def test_get_model_status_after_training(self, tmp_path, synthetic_records):
        import app.ml.opportunity_matching.config as cfg
        import app.ml.opportunity_matching.model as mdl

        original_dir = cfg.MATCHING_ARTIFACTS_DIR
        original_cache = mdl._cached_bundle
        try:
            cfg.MATCHING_ARTIFACTS_DIR = tmp_path
            mdl._cached_bundle = None

            from app.ml.opportunity_matching.model import train
            train(synthetic_records, save=True, params=_safe_lgbm_params())

            from app.ml.opportunity_matching.service import get_model_status
            status = get_model_status()
            assert status["loaded"] is True
            assert "metrics" in status
        finally:
            cfg.MATCHING_ARTIFACTS_DIR = original_dir
            mdl._cached_bundle = original_cache


# =========================================================================
# 9. Synthetic Data
# =========================================================================

class TestSyntheticData:

    def test_correct_count(self):
        from app.ml.opportunity_matching.service import generate_synthetic_dataset
        records = generate_synthetic_dataset(n=50, seed=7)
        assert len(records) == 50

    def test_deterministic(self):
        from app.ml.opportunity_matching.service import generate_synthetic_dataset
        r1 = generate_synthetic_dataset(n=30, seed=42)
        r2 = generate_synthetic_dataset(n=30, seed=42)
        for a, b in zip(r1, r2):
            assert a.cosine_similarity == b.cosine_similarity
            assert a.accepted == b.accepted

    def test_has_both_classes(self):
        from app.ml.opportunity_matching.service import generate_synthetic_dataset
        records = generate_synthetic_dataset(n=200, seed=42)
        labels = {r.accepted for r in records}
        assert labels == {0, 1}

    def test_features_in_reasonable_ranges(self):
        from app.ml.opportunity_matching.service import generate_synthetic_dataset
        records = generate_synthetic_dataset(n=100, seed=42)
        for r in records:
            assert 0 <= r.cosine_similarity <= 1
            assert 0 <= r.prior_success_rate <= 1
            assert r.prior_application_count >= 0
            assert 0 <= r.timeline_readiness_score <= 1
            assert r.days_to_deadline >= 0
            assert r.stage_type in STAGE_TYPES
            assert r.researcher_discipline in DISCIPLINES


# =========================================================================
# 10. Edge Cases
# =========================================================================

class TestEdgeCases:

    def test_single_record_prediction(self, trained_bundle):
        from app.ml.opportunity_matching.model import predict
        preds = predict([_make_record()], _bundle=trained_bundle["bundle"])
        assert len(preds) == 1

    def test_all_missing_values(self, trained_bundle):
        from app.ml.opportunity_matching.model import predict
        rec = MatchRecord()
        preds = predict([rec], _bundle=trained_bundle["bundle"])
        assert len(preds) == 1
        assert 0 <= preds[0].match_score <= 100

    def test_tiny_training_set(self):
        from app.ml.opportunity_matching.model import train
        records = [
            _make_record(accepted=0, cos_sim=0.2 + i * 0.05)
            for i in range(5)
        ] + [
            _make_record(accepted=1, cos_sim=0.7 + i * 0.05)
            for i in range(3)
        ]
        result = train(records, save=False, params=_safe_lgbm_params())
        assert result.n_samples == 8

    def test_reload_models_clears_cache(self):
        import app.ml.opportunity_matching.model as mdl
        mdl._cached_bundle = {"dummy": True}
        mdl.reload_models()
        assert mdl._cached_bundle is None

    def test_zero_cosine_similarity(self, trained_bundle):
        from app.ml.opportunity_matching.model import predict
        rec = _make_record(cos_sim=0.0)
        preds = predict([rec], _bundle=trained_bundle["bundle"])
        assert preds[0].match_score >= 0

    def test_max_cosine_similarity(self, trained_bundle):
        from app.ml.opportunity_matching.model import predict
        rec = _make_record(cos_sim=1.0, psr=1.0, trs=1.0, days=5.0)
        preds = predict([rec], _bundle=trained_bundle["bundle"])
        assert preds[0].match_score <= 100
