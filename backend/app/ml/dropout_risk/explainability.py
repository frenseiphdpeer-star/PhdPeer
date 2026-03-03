"""
SHAP-based explainability for dropout risk predictions.

Provides per-prediction feature attributions using TreeExplainer (for
XGBoost) or a model-agnostic KernelExplainer fallback (for Logistic
Regression).  Every prediction carries evidence of *why* the student
was classified at a given risk level.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd
import shap

from app.ml.dropout_risk.config import ALL_FEATURES
from app.ml.dropout_risk.features import DropoutFeatureEngineer, RawDropoutRecord

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RiskFactor:
    """SHAP attribution for a single feature in a single prediction."""

    feature_name: str
    feature_value: Any
    shap_value: float
    direction: str  # "increases_risk" | "decreases_risk" | "neutral"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "feature_name": self.feature_name,
            "feature_value": self.feature_value,
            "shap_value": round(self.shap_value, 4),
            "direction": self.direction,
        }


@dataclass(frozen=True)
class DropoutExplanation:
    """Full SHAP explanation for one dropout prediction."""

    base_probability: float
    predicted_probability: float
    risk_category: str
    top_risk_factors: List[RiskFactor]
    all_factors: List[RiskFactor]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "base_probability": round(self.base_probability, 4),
            "predicted_probability": round(self.predicted_probability, 4),
            "risk_category": self.risk_category,
            "top_risk_factors": [f.to_dict() for f in self.top_risk_factors],
            "all_factors": [f.to_dict() for f in self.all_factors],
        }


# ---------------------------------------------------------------------------
# Explain
# ---------------------------------------------------------------------------

def explain(
    records: Sequence[RawDropoutRecord],
    *,
    model: str = "xgboost",
    top_n: int = 5,
    yellow_threshold: float = 0.3,
    red_threshold: float = 0.6,
    _bundle: Optional[Dict[str, Any]] = None,
) -> List[DropoutExplanation]:
    """
    Generate SHAP-based explanations for dropout predictions.

    Parameters
    ----------
    records : sequence of RawDropoutRecord
    model : str
        ``"xgboost"`` or ``"logistic_regression"``.
    top_n : int
        Number of top risk factors to highlight.

    Returns
    -------
    list of DropoutExplanation
    """
    if _bundle is None:
        from app.ml.dropout_risk.model import _load_bundle
        _bundle = _load_bundle()

    fe: DropoutFeatureEngineer = _bundle["feature_engineer"]
    df = fe.transform(records)
    X = df[ALL_FEATURES].values.astype(np.float32)

    if model == "logistic_regression":
        from sklearn.preprocessing import StandardScaler
        scaler: StandardScaler = _bundle["scaler"]
        X_in = scaler.transform(X)
        clf = _bundle["lr_model"]
        # Use KernelExplainer for LR (lighter: use a small background set)
        background = shap.kmeans(X_in, min(10, len(X_in)))
        explainer = shap.KernelExplainer(clf.predict_proba, background)
        shap_values = explainer.shap_values(X_in)
        # shap_values is a list [class0, class1]; we want class 1
        if isinstance(shap_values, list):
            shap_matrix = np.array(shap_values[1])
        else:
            sv = np.array(shap_values)
            # Handle 3D: (n, f, 2) → take class-1 slice
            if sv.ndim == 3:
                shap_matrix = sv[:, :, 1]
            else:
                shap_matrix = sv
        base_val = float(clf.predict_proba(background.data).mean(axis=0)[1])
    else:
        X_in = X
        clf = _bundle["xgb_model"]
        explainer = shap.TreeExplainer(clf)
        shap_result = explainer(pd.DataFrame(X_in, columns=ALL_FEATURES))
        # For binary classification TreeExplainer may return shape (n, f) or (n, f, 2)
        if shap_result.values.ndim == 3:
            shap_matrix = shap_result.values[:, :, 1]
            base_val = float(shap_result.base_values[0, 1])
        else:
            shap_matrix = shap_result.values
            base_val = float(shap_result.base_values[0])

    # Build explanations
    probas = clf.predict_proba(X_in)[:, 1]
    results: List[DropoutExplanation] = []

    for i in range(len(X_in)):
        prob = float(probas[i])
        cat = (
            "red" if prob >= red_threshold
            else "yellow" if prob >= yellow_threshold
            else "green"
        )

        factors: List[RiskFactor] = []
        for j, fname in enumerate(ALL_FEATURES):
            sv = float(shap_matrix[i, j])
            direction = (
                "increases_risk" if sv > 0.001
                else "decreases_risk" if sv < -0.001
                else "neutral"
            )
            factors.append(RiskFactor(
                feature_name=fname,
                feature_value=_safe_value(X[i, j]),
                shap_value=sv,
                direction=direction,
            ))

        # Sort by absolute SHAP value (most impactful first)
        factors.sort(key=lambda f: abs(f.shap_value), reverse=True)

        results.append(DropoutExplanation(
            base_probability=base_val,
            predicted_probability=prob,
            risk_category=cat,
            top_risk_factors=factors[:top_n],
            all_factors=factors,
        ))

    return results


def _safe_value(v: Any) -> Any:
    """Convert numpy scalars to native Python types for JSON."""
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return round(float(v), 4)
    return v
