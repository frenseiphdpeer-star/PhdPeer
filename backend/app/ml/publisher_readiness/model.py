"""
LightGBM regression model for the Publisher Readiness Index.

Trains three models:
  1. **Mean regression** – predicts the expected readiness score (0–100).
  2. **Quantile-low**  – lower confidence bound (e.g. 10th percentile).
  3. **Quantile-high** – upper confidence bound (e.g. 90th percentile).

The gap between the quantile predictions serves as the **confidence
estimate**: a narrow band means high confidence, a wide band means
low confidence.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import joblib
import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)
from sklearn.model_selection import train_test_split

from app.ml.publisher_readiness import config as _cfg
from app.ml.publisher_readiness.config import (
    ALL_FEATURES,
    CATEGORY_THRESHOLDS,
    FEATURE_STATE_FILENAME,
    HYPERPARAMS,
    LGBMReadinessParams,
    METADATA_FILENAME,
    MODEL_FILENAME,
    QUANTILE_CFG,
    QUANTILE_HIGH_FILENAME,
    QUANTILE_LOW_FILENAME,
    SCALER_FILENAME,
    QuantileConfig,
    TARGET_COLUMN,
    categorise,
)
from app.ml.publisher_readiness.features import (
    RawReadinessRecord,
    ReadinessFeatureEngineer,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RegressionMetrics:
    """Evaluation metrics for the readiness regression model."""

    r2: float
    mae: float
    rmse: float
    n_train: int
    n_test: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            k: round(v, 4) if isinstance(v, float) else v
            for k, v in asdict(self).items()
        }


@dataclass
class TrainingResult:
    """Aggregated output from the training pipeline."""

    metrics: RegressionMetrics
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
    records: Sequence[RawReadinessRecord],
    *,
    test_size: float = 0.2,
    params: Optional[LGBMReadinessParams] = None,
    quantile_cfg: Optional[QuantileConfig] = None,
    save: bool = True,
) -> TrainingResult:
    """
    Train mean + quantile LightGBM regressors on readiness data.

    Parameters
    ----------
    records : sequence of RawReadinessRecord
        Training data with ``acceptance_outcome`` target set.
    test_size : float
        Fraction held out for evaluation.
    save : bool
        Persist models to disk (default True).

    Returns
    -------
    TrainingResult
    """
    hp = params or HYPERPARAMS
    qc = quantile_cfg or QUANTILE_CFG

    # --- Feature engineering -----------------------------------------------
    fe = ReadinessFeatureEngineer()
    df = fe.fit_transform(records)

    if TARGET_COLUMN not in df.columns or df[TARGET_COLUMN].isna().all():
        raise ValueError("Training data must include 'acceptance_outcome' targets.")

    X = df[ALL_FEATURES].values.astype(np.float64)
    y = df[TARGET_COLUMN].values.astype(np.float64)

    logger.info(
        "Training readiness model on %d samples, %d features",
        len(y), X.shape[1],
    )

    # --- Train / test split ------------------------------------------------
    if len(y) < 10:
        X_train, X_test, y_train, y_test = X, X, y, y
    else:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=42,
        )

    # --- Mean regression ---------------------------------------------------
    mean_model = LGBMRegressor(**hp.to_dict())
    mean_model.fit(X_train, y_train)

    # --- Quantile regressions (for confidence) -----------------------------
    q_low_params = {**hp.to_dict(), "objective": "quantile", "alpha": qc.alpha_low}
    q_high_params = {**hp.to_dict(), "objective": "quantile", "alpha": qc.alpha_high}

    q_low_model = LGBMRegressor(**q_low_params)
    q_low_model.fit(X_train, y_train)

    q_high_model = LGBMRegressor(**q_high_params)
    q_high_model.fit(X_train, y_train)

    # --- Evaluate mean model -----------------------------------------------
    y_pred = mean_model.predict(X_test)
    metrics = RegressionMetrics(
        r2=float(r2_score(y_test, y_pred)),
        mae=float(mean_absolute_error(y_test, y_pred)),
        rmse=float(np.sqrt(mean_squared_error(y_test, y_pred))),
        n_train=len(y_train),
        n_test=len(y_test),
    )

    # --- Feature importances -----------------------------------------------
    importances = dict(
        zip(ALL_FEATURES, mean_model.feature_importances_.tolist())
    )

    result = TrainingResult(
        metrics=metrics,
        feature_importances=importances,
        n_samples=len(y),
        n_features=X.shape[1],
    )

    # --- Persist -----------------------------------------------------------
    if save:
        _save_bundle(mean_model, q_low_model, q_high_model, fe, result)

    # Always update in-memory cache so predict() works without save
    global _cached_bundle
    _cached_bundle = {
        "mean_model": mean_model,
        "q_low_model": q_low_model,
        "q_high_model": q_high_model,
        "feature_engineer": fe,
    }

    logger.info(
        "Training complete – R²=%.3f  MAE=%.2f  RMSE=%.2f",
        metrics.r2, metrics.mae, metrics.rmse,
    )
    return result


# ---------------------------------------------------------------------------
# Prediction
# ---------------------------------------------------------------------------

@dataclass
class ReadinessPrediction:
    """Single-sample readiness prediction with confidence."""

    readiness_score: float          # 0–100
    category: str                   # revise | moderate readiness | submission-ready
    confidence: float               # 0–1 (1 = high confidence)
    confidence_low: float           # lower bound estimate
    confidence_high: float          # upper bound estimate
    researcher_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "readiness_score": round(self.readiness_score, 2),
            "category": self.category,
            "confidence": round(self.confidence, 4),
            "confidence_low": round(self.confidence_low, 2),
            "confidence_high": round(self.confidence_high, 2),
        }
        if self.researcher_id:
            d["researcher_id"] = self.researcher_id
        return d


def predict(
    records: Sequence[RawReadinessRecord],
    *,
    _bundle: Optional[Dict[str, Any]] = None,
) -> List[ReadinessPrediction]:
    """
    Predict readiness score and confidence for one or more records.

    Confidence is computed as:
        confidence = 1 − clamp(band_width / 100, 0, 1)
    where ``band_width = q_high − q_low``.
    """
    bundle = _bundle or _load_bundle()
    fe: ReadinessFeatureEngineer = bundle["feature_engineer"]
    df = fe.transform(records)
    X = df[ALL_FEATURES].values.astype(np.float64)

    mean_preds = bundle["mean_model"].predict(X)
    low_preds = bundle["q_low_model"].predict(X)
    high_preds = bundle["q_high_model"].predict(X)

    results: List[ReadinessPrediction] = []
    for i, (mp, lp, hp) in enumerate(zip(mean_preds, low_preds, high_preds)):
        score = float(np.clip(mp, 0, 100))
        lo = float(np.clip(lp, 0, 100))
        hi = float(np.clip(hp, 0, 100))

        # Ensure lo ≤ score ≤ hi
        lo = min(lo, score)
        hi = max(hi, score)

        band = hi - lo
        confidence = float(np.clip(1.0 - band / 100.0, 0.0, 1.0))

        rid = records[i].researcher_id if i < len(records) else None

        results.append(ReadinessPrediction(
            readiness_score=score,
            category=categorise(score),
            confidence=confidence,
            confidence_low=lo,
            confidence_high=hi,
            researcher_id=rid,
        ))

    return results


def rank_feature_importance(
    _bundle: Optional[Dict[str, Any]] = None,
) -> Dict[str, float]:
    """Return feature importances from the mean model, sorted descending."""
    bundle = _bundle or _load_bundle()
    model = bundle["mean_model"]
    raw = dict(zip(ALL_FEATURES, model.feature_importances_.tolist()))
    return dict(sorted(raw.items(), key=lambda kv: kv[1], reverse=True))


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def _save_bundle(
    mean_model: LGBMRegressor,
    q_low_model: LGBMRegressor,
    q_high_model: LGBMRegressor,
    fe: ReadinessFeatureEngineer,
    result: TrainingResult,
) -> Path:
    out_dir = _cfg.READINESS_ARTIFACTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    joblib.dump(mean_model, out_dir / MODEL_FILENAME)
    joblib.dump(q_low_model, out_dir / QUANTILE_LOW_FILENAME)
    joblib.dump(q_high_model, out_dir / QUANTILE_HIGH_FILENAME)
    joblib.dump(fe.get_state(), out_dir / FEATURE_STATE_FILENAME)

    meta = result.to_dict()
    (out_dir / METADATA_FILENAME).write_text(json.dumps(meta, indent=2))

    logger.info("Saved readiness models to %s", out_dir)
    return out_dir


_cached_bundle: Optional[Dict[str, Any]] = None


def _load_bundle() -> Dict[str, Any]:
    global _cached_bundle
    if _cached_bundle is not None:
        return _cached_bundle

    d = _cfg.READINESS_ARTIFACTS_DIR
    if not (d / MODEL_FILENAME).exists():
        raise RuntimeError(
            "No trained readiness model found.  Call train() first."
        )

    fe = ReadinessFeatureEngineer()
    fe.load_state(joblib.load(d / FEATURE_STATE_FILENAME))

    _cached_bundle = {
        "mean_model": joblib.load(d / MODEL_FILENAME),
        "q_low_model": joblib.load(d / QUANTILE_LOW_FILENAME),
        "q_high_model": joblib.load(d / QUANTILE_HIGH_FILENAME),
        "feature_engineer": fe,
    }
    return _cached_bundle


def reload_models() -> None:
    """Clear cached models (forces reload on next predict)."""
    global _cached_bundle
    _cached_bundle = None
