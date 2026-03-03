"""
Multi-target regression model for the Cross-Feature Fusion Engine.

Trains one LightGBM regressor **per target** (publication_success,
milestone_acceleration, dropout_risk) using the lagged cross-signal
feature matrix.  Wraps them in a ``MultiTargetModel`` that exposes
a unified train / predict / feature-importance interface.

Persistence is via joblib (one bundle for all target models).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import joblib
import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split

from app.ml.fusion_engine import config as _cfg
from app.ml.fusion_engine.config import (
    HYPERPARAMS,
    LGBMFusionParams,
    METADATA_FILENAME,
    MODEL_FILENAME,
    TARGET_NAMES,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TargetMetrics:
    """Regression metrics for one target variable."""

    target: str
    r2: float
    mae: float
    rmse: float
    n_train: int
    n_test: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target": self.target,
            "r2": round(self.r2, 4),
            "mae": round(self.mae, 4),
            "rmse": round(self.rmse, 4),
            "n_train": self.n_train,
            "n_test": self.n_test,
        }


@dataclass
class FusionTrainingResult:
    """Output from a multi-target training run."""

    target_metrics: List[TargetMetrics]
    feature_importances: Dict[str, Dict[str, float]]  # target → {feat: imp}
    feature_names: List[str]
    n_samples: int
    n_features: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_metrics": [m.to_dict() for m in self.target_metrics],
            "feature_importances": {
                tgt: {k: round(v, 4) for k, v in imp.items()}
                for tgt, imp in self.feature_importances.items()
            },
            "feature_names": self.feature_names,
            "n_samples": self.n_samples,
            "n_features": self.n_features,
        }


@dataclass(frozen=True)
class FusionPrediction:
    """Predicted values for all targets at one time-point."""

    predictions: Dict[str, float]    # target → predicted value

    def to_dict(self) -> Dict[str, Any]:
        return {
            k: round(v, 4) for k, v in self.predictions.items()
        }


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

def train(
    df: pd.DataFrame,
    feature_names: List[str],
    *,
    targets: List[str] | None = None,
    test_size: float = 0.2,
    params: LGBMFusionParams | None = None,
    save: bool = True,
) -> FusionTrainingResult:
    """
    Train one LGBMRegressor per target using the fused feature matrix.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain both ``feature_names`` and ``targets`` columns.
    feature_names : list[str]
        Input feature column names.
    targets : list[str], optional
        Target column names (default: TARGET_NAMES present in df).
    test_size : float
        Held-out fraction.
    params : LGBMFusionParams
        Hyper-parameters for each LGBMRegressor.
    save : bool
        Whether to persist the trained models.

    Returns
    -------
    FusionTrainingResult
    """
    hp = params or HYPERPARAMS
    tgt_cols = targets or [c for c in TARGET_NAMES if c in df.columns]

    if not tgt_cols:
        raise ValueError("No target columns found in DataFrame.")

    X = df[feature_names].values.astype(np.float32)

    models: Dict[str, LGBMRegressor] = {}
    all_metrics: List[TargetMetrics] = []
    all_importances: Dict[str, Dict[str, float]] = {}

    for tgt in tgt_cols:
        y = df[tgt].values.astype(np.float32)
        mask = ~np.isnan(y)
        X_valid, y_valid = X[mask], y[mask]

        if len(y_valid) < 5:
            logger.warning("Target '%s' has <5 valid samples, skipping.", tgt)
            continue

        if len(y_valid) < 10:
            X_tr, X_te, y_tr, y_te = X_valid, X_valid, y_valid, y_valid
        else:
            X_tr, X_te, y_tr, y_te = train_test_split(
                X_valid, y_valid,
                test_size=test_size,
                random_state=42,
            )

        clf = LGBMRegressor(**hp.to_dict())
        clf.fit(X_tr, y_tr)

        y_pred = clf.predict(X_te)
        metrics = TargetMetrics(
            target=tgt,
            r2=float(r2_score(y_te, y_pred)),
            mae=float(mean_absolute_error(y_te, y_pred)),
            rmse=float(np.sqrt(mean_squared_error(y_te, y_pred))),
            n_train=len(y_tr),
            n_test=len(y_te),
        )
        all_metrics.append(metrics)
        models[tgt] = clf
        all_importances[tgt] = dict(
            zip(feature_names, clf.feature_importances_.tolist())
        )
        logger.info("Target '%s' – R²=%.3f MAE=%.3f", tgt, metrics.r2, metrics.mae)

    result = FusionTrainingResult(
        target_metrics=all_metrics,
        feature_importances=all_importances,
        feature_names=feature_names,
        n_samples=len(df),
        n_features=len(feature_names),
    )

    if save and models:
        _save_bundle(models, feature_names, result)

    # Always keep in-memory cache so predict() works without disk I/O
    if models:
        global _cached_bundle
        _cached_bundle = {"models": models, "feature_names": feature_names}

    return result


# ---------------------------------------------------------------------------
# Prediction
# ---------------------------------------------------------------------------

def predict(
    df: pd.DataFrame,
    feature_names: List[str],
    *,
    _bundle: Optional[Dict[str, Any]] = None,
) -> List[FusionPrediction]:
    """
    Predict all targets for each row of the feature DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain ``feature_names`` columns.
    feature_names : list[str]
    _bundle : dict, optional
        Injected model bundle (for testing).

    Returns
    -------
    list[FusionPrediction]
        One prediction per row.
    """
    bundle = _bundle or _load_bundle()
    models: Dict[str, LGBMRegressor] = bundle["models"]

    X = df[feature_names].values.astype(np.float32)
    preds: List[FusionPrediction] = []

    # Predict each target
    target_predictions: Dict[str, np.ndarray] = {}
    for tgt, mdl in models.items():
        target_predictions[tgt] = mdl.predict(X)

    for i in range(len(X)):
        row_preds = {
            tgt: float(arr[i]) for tgt, arr in target_predictions.items()
        }
        preds.append(FusionPrediction(predictions=row_preds))

    return preds


# ---------------------------------------------------------------------------
# Feature importance ranking
# ---------------------------------------------------------------------------

def rank_feature_importance(
    result: FusionTrainingResult,
    *,
    target: str | None = None,
) -> List[Dict[str, Any]]:
    """
    Return feature importances sorted descending.

    If ``target`` is specified, rank for that target only.
    Otherwise aggregate (mean) across all targets.
    """
    if target and target in result.feature_importances:
        imp = result.feature_importances[target]
    else:
        # Aggregate across targets
        agg: Dict[str, float] = {}
        for tgt_imp in result.feature_importances.values():
            for feat, val in tgt_imp.items():
                agg[feat] = agg.get(feat, 0.0) + val
        n_targets = max(len(result.feature_importances), 1)
        imp = {k: v / n_targets for k, v in agg.items()}

    ranked = sorted(imp.items(), key=lambda x: x[1], reverse=True)
    total = sum(v for _, v in ranked) or 1.0

    return [
        {
            "feature": feat,
            "importance": round(val, 4),
            "relative_importance": round(val / total, 4),
            "rank": i + 1,
        }
        for i, (feat, val) in enumerate(ranked)
    ]


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def _save_bundle(
    models: Dict[str, LGBMRegressor],
    feature_names: List[str],
    result: FusionTrainingResult,
) -> Path:
    out_dir = _cfg.FUSION_ARTIFACTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    joblib.dump(
        {"models": models, "feature_names": feature_names},
        out_dir / MODEL_FILENAME,
    )

    meta = result.to_dict()
    (out_dir / METADATA_FILENAME).write_text(json.dumps(meta, indent=2))

    logger.info("Saved fusion models to %s", out_dir)
    return out_dir


_cached_bundle: Optional[Dict[str, Any]] = None


def _load_bundle() -> Dict[str, Any]:
    global _cached_bundle
    if _cached_bundle is not None:
        return _cached_bundle

    d = _cfg.FUSION_ARTIFACTS_DIR
    if not (d / MODEL_FILENAME).exists():
        raise RuntimeError(
            "No trained fusion models found. Call train() first."
        )

    _cached_bundle = joblib.load(d / MODEL_FILENAME)
    return _cached_bundle


def reload_models() -> None:
    """Clear the cached model (forces reload on next predict)."""
    global _cached_bundle
    _cached_bundle = None
