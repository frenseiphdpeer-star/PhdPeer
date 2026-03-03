"""
LightGBM training and prediction for milestone duration.

Trains three models:
  1. **Point estimator** – standard squared-error regression → ``predicted_duration_months``
  2. **Lower quantile** – quantile regression (α = 0.10) → CI lower bound
  3. **Upper quantile** – quantile regression (α = 0.90) → CI upper bound

Evaluation is via MAE and RMSE on a held-out test split (or full training set
when data is scarce).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Union

import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor
from sklearn.model_selection import train_test_split

from app.ml.config import ALL_FEATURES, HYPERPARAMS, LGBMHyperParams
from app.ml.features import FeatureEngineer, RawMilestoneRecord
from app.ml.persistence import save_model_bundle

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class EvaluationMetrics:
    """Hold-out evaluation metrics."""

    mae: float
    rmse: float
    r2: float
    n_train: int
    n_test: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mae": round(self.mae, 4),
            "rmse": round(self.rmse, 4),
            "r2": round(self.r2, 4),
            "n_train": self.n_train,
            "n_test": self.n_test,
        }


@dataclass
class TrainingResult:
    """Returned after a successful training run."""

    metrics: EvaluationMetrics
    model_path: str
    feature_importances: Dict[str, float]


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

def train(
    records: Sequence[Union[RawMilestoneRecord, Dict[str, Any]]],
    *,
    test_size: float = 0.2,
    hyperparams: Optional[LGBMHyperParams] = None,
    version_tag: Optional[str] = None,
) -> TrainingResult:
    """
    End-to-end training pipeline.

    1. Feature-engineer the raw records.
    2. Split into train / test.
    3. Fit point + quantile models.
    4. Evaluate on test set.
    5. Persist artefacts.

    Parameters
    ----------
    records
        Training observations – list of ``RawMilestoneRecord`` or flat dicts.
    test_size
        Fraction held out for evaluation (0 ≤ test_size < 1).
    hyperparams
        Override default LightGBM hyper-parameters.
    version_tag
        Optional human-readable version label.

    Returns
    -------
    TrainingResult
    """
    hp = hyperparams or HYPERPARAMS
    fe = FeatureEngineer()

    # --- Feature engineering -----------------------------------------------
    X, y = fe.fit_transform(records)
    logger.info("Feature matrix shape: %s | Target length: %d", X.shape, len(y))

    if len(X) < 5:
        raise ValueError(
            f"Need at least 5 records to train; got {len(X)}. "
            "Collect more milestone completion data first."
        )

    # --- Train / test split ------------------------------------------------
    if test_size > 0 and len(X) >= 10:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=hp.random_state,
        )
    else:
        # Too few rows for a meaningful split – train = test (overfit-aware)
        X_train = X_test = X
        y_train = y_test = y
        logger.warning(
            "Dataset too small (%d rows) for a proper split; evaluating on training set.",
            len(X),
        )

    # --- Fit point-estimate model ------------------------------------------
    model = LGBMRegressor(objective="regression", **hp.to_dict())
    model.fit(
        X_train,
        y_train,
        eval_set=[(X_test, y_test)],
        eval_metric="mae",
    )

    # --- Fit quantile models (confidence interval) -------------------------
    model_lower = LGBMRegressor(
        objective="quantile", alpha=hp.ci_lower_quantile, **hp.to_dict(),
    )
    model_lower.fit(X_train, y_train)

    model_upper = LGBMRegressor(
        objective="quantile", alpha=hp.ci_upper_quantile, **hp.to_dict(),
    )
    model_upper.fit(X_train, y_train)

    # --- Evaluate ----------------------------------------------------------
    metrics = _evaluate(model, X_test, y_test, n_train=len(X_train))

    # --- Feature importances -----------------------------------------------
    importances = dict(
        zip(ALL_FEATURES, model.feature_importances_.tolist())
    )

    # --- Persist -----------------------------------------------------------
    bundle = {
        "model": model,
        "model_lower": model_lower,
        "model_upper": model_upper,
        "feature_engineer_state": fe.get_state(),
        "feature_names": ALL_FEATURES,
    }
    saved_path = save_model_bundle(
        bundle,
        metrics=metrics.to_dict(),
        params=hp.to_dict(),
        version_tag=version_tag,
    )

    logger.info(
        "Training complete – MAE=%.3f  RMSE=%.3f  R²=%.3f",
        metrics.mae,
        metrics.rmse,
        metrics.r2,
    )

    return TrainingResult(
        metrics=metrics,
        model_path=str(saved_path),
        feature_importances=importances,
    )


# ---------------------------------------------------------------------------
# Prediction (stateless – loads from bundle dict)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DurationPrediction:
    """Single prediction result."""

    predicted_duration_months: float
    ci_lower: float
    ci_upper: float


def predict(
    records: Sequence[Union[RawMilestoneRecord, Dict[str, Any]]],
    bundle: Dict[str, Any],
) -> List[DurationPrediction]:
    """
    Predict milestone duration for one or more records.

    Parameters
    ----------
    records
        Input observations.
    bundle
        Model bundle loaded via ``persistence.load_model_bundle()``.

    Returns
    -------
    list[DurationPrediction]
    """
    fe = FeatureEngineer()
    fe.load_state(bundle["feature_engineer_state"])

    X = fe.transform(records)

    point = bundle["model"].predict(X)
    lower = bundle["model_lower"].predict(X)
    upper = bundle["model_upper"].predict(X)

    results: List[DurationPrediction] = []
    for p, lo, hi in zip(point, lower, upper):
        # Clamp to non-negative and ensure lo ≤ p ≤ hi
        p_val = max(float(p), 0.0)
        lo_val = max(float(lo), 0.0)
        hi_val = max(float(hi), p_val)
        lo_val = min(lo_val, p_val)
        results.append(
            DurationPrediction(
                predicted_duration_months=round(p_val, 2),
                ci_lower=round(lo_val, 2),
                ci_upper=round(hi_val, 2),
            )
        )
    return results


# ---------------------------------------------------------------------------
# Evaluation helpers
# ---------------------------------------------------------------------------

def _evaluate(
    model: LGBMRegressor,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    n_train: int,
) -> EvaluationMetrics:
    preds = model.predict(X_test)
    residuals = y_test.values - preds

    mae = float(np.mean(np.abs(residuals)))
    rmse = float(np.sqrt(np.mean(residuals ** 2)))

    ss_res = float(np.sum(residuals ** 2))
    ss_tot = float(np.sum((y_test.values - y_test.mean()) ** 2))
    r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

    return EvaluationMetrics(
        mae=mae,
        rmse=rmse,
        r2=r2,
        n_train=n_train,
        n_test=len(y_test),
    )
