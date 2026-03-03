"""
Training pipeline for dropout risk prediction.

Trains two classifiers:
  1. **Logistic Regression** – interpretable baseline.
  2. **XGBoost** – gradient-boosted ensemble for production.

Evaluates via AUC-ROC, precision, recall, F1, and precision-recall AUC.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    auc,
    classification_report,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

from app.ml.dropout_risk import config as _cfg
from app.ml.dropout_risk.config import (
    ALL_FEATURES,
    FEATURE_STATE_FILENAME,
    HYPERPARAMS_LR,
    HYPERPARAMS_XGB,
    LRHyperParams,
    METADATA_FILENAME,
    MODEL_FILENAME_LR,
    MODEL_FILENAME_XGB,
    TARGET_COLUMN,
    XGBHyperParams,
)
from app.ml.dropout_risk.features import (
    DropoutFeatureEngineer,
    RawDropoutRecord,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ClassificationMetrics:
    """Evaluation metrics for a binary classifier."""

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
        return {k: round(v, 4) if isinstance(v, float) else v for k, v in asdict(self).items()}


@dataclass
class TrainingResult:
    """Aggregated output from the training pipeline."""

    lr_metrics: ClassificationMetrics
    xgb_metrics: ClassificationMetrics
    feature_importances: Dict[str, float]
    n_samples: int
    n_features: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "lr_metrics": self.lr_metrics.to_dict(),
            "xgb_metrics": self.xgb_metrics.to_dict(),
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
    records: Sequence[RawDropoutRecord],
    *,
    test_size: float = 0.2,
    xgb_params: Optional[XGBHyperParams] = None,
    lr_params: Optional[LRHyperParams] = None,
    save: bool = True,
) -> TrainingResult:
    """
    Train both classifiers and evaluate on a held-out split.

    Parameters
    ----------
    records : sequence of RawDropoutRecord
        Training data with ``dropout`` label set.
    test_size : float
        Fraction held out for evaluation.
    save : bool
        Persist models to disk (default True).

    Returns
    -------
    TrainingResult
    """
    xgb_hp = xgb_params or HYPERPARAMS_XGB
    lr_hp = lr_params or HYPERPARAMS_LR

    # --- Feature engineering ---------------------------------------------
    fe = DropoutFeatureEngineer()
    df = fe.fit_transform(records)

    if TARGET_COLUMN not in df.columns:
        raise ValueError("Training data must include 'dropout' labels.")

    X = df[ALL_FEATURES].values.astype(np.float32)
    y = df[TARGET_COLUMN].values.astype(int)

    logger.info("Training dropout models on %d samples, %d features", len(y), X.shape[1])

    # --- Train / test split -----------------------------------------------
    if len(y) < 10:
        X_train, X_test, y_train, y_test = X, X, y, y
    else:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=42, stratify=y,
        )

    # --- Scaler for LR ----------------------------------------------------
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # --- Logistic Regression baseline -------------------------------------
    lr_model = LogisticRegression(**lr_hp.to_dict())
    lr_model.fit(X_train_scaled, y_train)
    lr_metrics = _evaluate(lr_model, X_test_scaled, y_test, len(y_train))

    # --- XGBoost classifier -----------------------------------------------
    xgb_model = XGBClassifier(**xgb_hp.to_dict())
    xgb_model.fit(X_train, y_train)
    xgb_metrics = _evaluate(xgb_model, X_test, y_test, len(y_train))

    # --- Feature importances (XGBoost) ------------------------------------
    importances = dict(zip(ALL_FEATURES, xgb_model.feature_importances_.tolist()))

    result = TrainingResult(
        lr_metrics=lr_metrics,
        xgb_metrics=xgb_metrics,
        feature_importances=importances,
        n_samples=len(y),
        n_features=X.shape[1],
    )

    # --- Persist -----------------------------------------------------------
    if save:
        _save_bundle(lr_model, xgb_model, scaler, fe, result)

    logger.info(
        "Training complete – LR AUC=%.3f  XGB AUC=%.3f",
        lr_metrics.auc_roc, xgb_metrics.auc_roc,
    )
    return result


# ---------------------------------------------------------------------------
# Prediction
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DropoutPrediction:
    """Single-sample dropout prediction."""

    dropout_probability: float
    risk_category: str          # "green" | "yellow" | "red"
    model_used: str             # "xgboost" | "logistic_regression"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def predict(
    records: Sequence[RawDropoutRecord],
    *,
    model: str = "xgboost",
    yellow_threshold: float = 0.3,
    red_threshold: float = 0.6,
    _bundle: Optional[Dict[str, Any]] = None,
) -> List[DropoutPrediction]:
    """
    Predict dropout probability for one or more records.

    Parameters
    ----------
    records : sequence of RawDropoutRecord
    model : str
        ``"xgboost"`` (default) or ``"logistic_regression"``.
    yellow_threshold, red_threshold : float
        Risk-category cut-offs.

    Returns
    -------
    list of DropoutPrediction
    """
    bundle = _bundle or _load_bundle()
    fe: DropoutFeatureEngineer = bundle["feature_engineer"]
    df = fe.transform(records)
    X = df[ALL_FEATURES].values.astype(np.float32)

    if model == "logistic_regression":
        scaler: StandardScaler = bundle["scaler"]
        X_in = scaler.transform(X)
        clf = bundle["lr_model"]
    else:
        X_in = X
        clf = bundle["xgb_model"]

    probas = clf.predict_proba(X_in)[:, 1]

    results: List[DropoutPrediction] = []
    for p in probas:
        cat = (
            "red" if p >= red_threshold
            else "yellow" if p >= yellow_threshold
            else "green"
        )
        results.append(DropoutPrediction(
            dropout_probability=round(float(p), 4),
            risk_category=cat,
            model_used=model,
        ))
    return results


# ---------------------------------------------------------------------------
# Evaluation helper
# ---------------------------------------------------------------------------

def _evaluate(
    clf,
    X_test: np.ndarray,
    y_test: np.ndarray,
    n_train: int,
) -> ClassificationMetrics:
    """Compute classification metrics."""
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
        pos_rate_train=0.0,  # filled in caller if needed
        pos_rate_test=float(y_test.mean()) if len(y_test) > 0 else 0.0,
    )


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def _save_bundle(
    lr_model,
    xgb_model,
    scaler,
    fe: DropoutFeatureEngineer,
    result: TrainingResult,
) -> Path:
    out_dir = _cfg.DROPOUT_ARTIFACTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    joblib.dump(lr_model, out_dir / MODEL_FILENAME_LR)
    joblib.dump(xgb_model, out_dir / MODEL_FILENAME_XGB)
    joblib.dump(scaler, out_dir / "scaler.joblib")
    joblib.dump(fe.get_state(), out_dir / FEATURE_STATE_FILENAME)

    meta = result.to_dict()
    (out_dir / METADATA_FILENAME).write_text(json.dumps(meta, indent=2))

    logger.info("Saved dropout risk models to %s", out_dir)
    return out_dir


_cached_bundle: Optional[Dict[str, Any]] = None


def _load_bundle() -> Dict[str, Any]:
    global _cached_bundle
    if _cached_bundle is not None:
        return _cached_bundle

    d = _cfg.DROPOUT_ARTIFACTS_DIR
    if not (d / MODEL_FILENAME_XGB).exists():
        raise RuntimeError(
            "No trained dropout model found.  Call train() first."
        )

    fe = DropoutFeatureEngineer()
    fe.load_state(joblib.load(d / FEATURE_STATE_FILENAME))

    _cached_bundle = {
        "lr_model": joblib.load(d / MODEL_FILENAME_LR),
        "xgb_model": joblib.load(d / MODEL_FILENAME_XGB),
        "scaler": joblib.load(d / "scaler.joblib"),
        "feature_engineer": fe,
    }
    return _cached_bundle


def reload_models() -> None:
    """Clear cached models (forces reload on next predict)."""
    global _cached_bundle
    _cached_bundle = None
