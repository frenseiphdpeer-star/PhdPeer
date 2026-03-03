"""
LightGBM ranking model for opportunity matching.

Trains a binary classifier (``LGBMClassifier``) on historical acceptance
outcomes.  The predicted probability serves as the *success_probability*,
while the final *match_score* is a weighted blend of:

  * cosine similarity (semantic fit)
  * model probability (learned ranking)
  * urgency score (time pressure)

Persistence is via joblib.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import joblib
import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.metrics import (
    auc,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split

from app.ml.opportunity_matching import config as _cfg
from app.ml.opportunity_matching.config import (
    ALL_FEATURES,
    FEATURE_STATE_FILENAME,
    HYPERPARAMS,
    LGBMRankParams,
    METADATA_FILENAME,
    MODEL_FILENAME,
    SCORING,
    TARGET_COLUMN,
)
from app.ml.opportunity_matching.features import (
    MatchFeatureEngineer,
    MatchRecord,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ClassificationMetrics:
    """Evaluation metrics for the ranking classifier."""

    auc_roc: float
    auc_pr: float
    precision: float
    recall: float
    f1: float
    n_train: int
    n_test: int
    pos_rate_train: float
    pos_rate_test: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            k: round(v, 4) if isinstance(v, float) else v
            for k, v in asdict(self).items()
        }


@dataclass
class TrainingResult:
    """Output from a training run."""

    metrics: ClassificationMetrics
    feature_importances: Dict[str, float]
    n_samples: int
    n_features: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metrics": self.metrics.to_dict(),
            "feature_importances": {
                k: round(v, 4) for k, v in self.feature_importances.items()
            },
            "n_samples": self.n_samples,
            "n_features": self.n_features,
        }


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

def train(
    records: Sequence[MatchRecord],
    *,
    test_size: float = 0.2,
    params: Optional[LGBMRankParams] = None,
    save: bool = True,
) -> TrainingResult:
    """Train the LightGBM ranking classifier on historical outcomes."""
    hp = params or HYPERPARAMS

    fe = MatchFeatureEngineer()
    df = fe.fit_transform(records)

    if TARGET_COLUMN not in df.columns:
        raise ValueError("Training data must include 'accepted' labels.")

    X = df[ALL_FEATURES].values.astype(np.float32)
    y = df[TARGET_COLUMN].values.astype(int)

    logger.info(
        "Training opportunity matching on %d samples, %d features",
        len(y),
        X.shape[1],
    )

    # Train / test split
    if len(y) < 10:
        X_train, X_test, y_train, y_test = X, X, y, y
    else:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=42, stratify=y,
        )

    clf = LGBMClassifier(**hp.to_dict())
    clf.fit(X_train, y_train)

    metrics = _evaluate(clf, X_test, y_test, len(y_train), y_train, y_test)
    importances = dict(zip(ALL_FEATURES, clf.feature_importances_.tolist()))

    result = TrainingResult(
        metrics=metrics,
        feature_importances=importances,
        n_samples=len(y),
        n_features=X.shape[1],
    )

    if save:
        _save_bundle(clf, fe, result)

    logger.info("Training complete – AUC=%.3f", metrics.auc_roc)
    return result


# ---------------------------------------------------------------------------
# Prediction
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MatchPrediction:
    """Single opportunity-match prediction."""

    match_score: float               # 0–100
    success_probability: float       # 0–1
    cosine_similarity: float         # 0–1
    urgency_score: float             # 0–1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "match_score": round(self.match_score, 2),
            "success_probability": round(self.success_probability, 4),
            "cosine_similarity": round(self.cosine_similarity, 4),
            "urgency_score": round(self.urgency_score, 4),
        }


def predict(
    records: Sequence[MatchRecord],
    *,
    _bundle: Optional[Dict[str, Any]] = None,
) -> List[MatchPrediction]:
    """
    Predict match score and success probability for researcher ↔ opportunity
    pairs.
    """
    bundle = _bundle or _load_bundle()
    fe: MatchFeatureEngineer = bundle["feature_engineer"]
    clf = bundle["model"]

    df = fe.transform(records)
    X = df[ALL_FEATURES].values.astype(np.float32)

    probas = clf.predict_proba(X)[:, 1]

    results: List[MatchPrediction] = []
    for i, prob in enumerate(probas):
        cos_sim = float(df["cosine_similarity"].iloc[i])
        urg = float(df["urgency_score"].iloc[i])

        # Weighted blend → match_score (0–100)
        raw = (
            SCORING.weight_similarity * cos_sim
            + SCORING.weight_model * float(prob)
            + SCORING.weight_urgency * urg
        )
        match_score = float(np.clip(raw * SCORING.score_scale, 0, 100))

        results.append(
            MatchPrediction(
                match_score=match_score,
                success_probability=float(prob),
                cosine_similarity=cos_sim,
                urgency_score=urg,
            )
        )

    return results


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def _evaluate(
    clf,
    X_test: np.ndarray,
    y_test: np.ndarray,
    n_train: int,
    y_train: np.ndarray,
    y_test_labels: np.ndarray,
) -> ClassificationMetrics:
    y_proba = clf.predict_proba(X_test)[:, 1]
    y_pred = (y_proba >= 0.5).astype(int)

    try:
        auc_roc = roc_auc_score(y_test, y_proba)
    except ValueError:
        auc_roc = 0.0

    prec_arr, rec_arr, _ = precision_recall_curve(y_test, y_proba)
    auc_pr = float(auc(rec_arr, prec_arr))

    return ClassificationMetrics(
        auc_roc=auc_roc,
        auc_pr=auc_pr,
        precision=precision_score(y_test, y_pred, zero_division=0),
        recall=recall_score(y_test, y_pred, zero_division=0),
        f1=f1_score(y_test, y_pred, zero_division=0),
        n_train=n_train,
        n_test=len(y_test),
        pos_rate_train=float(y_train.mean()) if len(y_train) > 0 else 0.0,
        pos_rate_test=float(y_test_labels.mean()) if len(y_test_labels) > 0 else 0.0,
    )


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def _save_bundle(
    clf,
    fe: MatchFeatureEngineer,
    result: TrainingResult,
) -> Path:
    out_dir = _cfg.MATCHING_ARTIFACTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    joblib.dump(clf, out_dir / MODEL_FILENAME)
    joblib.dump(fe.get_state(), out_dir / FEATURE_STATE_FILENAME)

    meta = result.to_dict()
    (out_dir / METADATA_FILENAME).write_text(json.dumps(meta, indent=2))

    logger.info("Saved opportunity matching model to %s", out_dir)
    return out_dir


_cached_bundle: Optional[Dict[str, Any]] = None


def _load_bundle() -> Dict[str, Any]:
    global _cached_bundle
    if _cached_bundle is not None:
        return _cached_bundle

    d = _cfg.MATCHING_ARTIFACTS_DIR
    if not (d / MODEL_FILENAME).exists():
        raise RuntimeError(
            "No trained opportunity matching model found. Call train() first."
        )

    fe = MatchFeatureEngineer()
    fe.load_state(joblib.load(d / FEATURE_STATE_FILENAME))

    _cached_bundle = {
        "model": joblib.load(d / MODEL_FILENAME),
        "feature_engineer": fe,
    }
    return _cached_bundle


def reload_models() -> None:
    """Clear the cached model (forces reload on next predict)."""
    global _cached_bundle
    _cached_bundle = None
