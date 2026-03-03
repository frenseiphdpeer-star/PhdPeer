"""
SHAP-based explainability for milestone duration predictions.

Provides per-prediction feature attributions using TreeExplainer (exact,
fast for tree ensembles).  Output follows the project's ``InterpretableSignal``
pattern – every prediction carries evidence of *why*.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Sequence, Union

import numpy as np
import pandas as pd
import shap

from app.ml.config import ALL_FEATURES
from app.ml.features import FeatureEngineer, RawMilestoneRecord

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class FeatureAttribution:
    """SHAP attribution for a single feature in a single prediction."""

    feature_name: str
    feature_value: Any
    shap_value: float
    direction: str          # "increases" | "decreases" | "neutral"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "feature_name": self.feature_name,
            "feature_value": self.feature_value,
            "shap_value": round(self.shap_value, 4),
            "direction": self.direction,
        }


@dataclass(frozen=True)
class PredictionExplanation:
    """Full SHAP explanation for one prediction row."""

    base_value: float                         # expected model output (training mean)
    attributions: List[FeatureAttribution]     # sorted by |shap_value| descending
    top_contributors: List[FeatureAttribution] # top-K drivers

    def to_dict(self) -> Dict[str, Any]:
        return {
            "base_value": round(self.base_value, 4),
            "attributions": [a.to_dict() for a in self.attributions],
            "top_contributors": [a.to_dict() for a in self.top_contributors],
        }


# ---------------------------------------------------------------------------
# Explainer
# ---------------------------------------------------------------------------

def explain(
    records: Sequence[Union[RawMilestoneRecord, Dict[str, Any]]],
    bundle: Dict[str, Any],
    *,
    top_k: int = 5,
) -> List[PredictionExplanation]:
    """
    Generate SHAP explanations for one or more prediction inputs.

    Parameters
    ----------
    records
        Same input format accepted by ``model.predict()``.
    bundle
        Loaded model bundle dict.
    top_k
        Number of top contributing features to highlight.

    Returns
    -------
    list[PredictionExplanation]  – one per input record.
    """
    fe = FeatureEngineer()
    fe.load_state(bundle["feature_engineer_state"])
    X = fe.transform(records)

    point_model = bundle["model"]

    # TreeExplainer is exact & fast for LightGBM
    explainer = shap.TreeExplainer(point_model)
    shap_values = explainer.shap_values(X)       # shape (n, n_features)
    base_value = float(explainer.expected_value)

    feature_names = bundle.get("feature_names", ALL_FEATURES)

    explanations: List[PredictionExplanation] = []
    for row_idx in range(len(X)):
        row_shap = shap_values[row_idx]
        row_data = X.iloc[row_idx]

        attrs: List[FeatureAttribution] = []
        for feat_idx, feat_name in enumerate(feature_names):
            sv = float(row_shap[feat_idx])
            fv = _safe_value(row_data.iloc[feat_idx])
            direction = (
                "increases" if sv > 0.01
                else "decreases" if sv < -0.01
                else "neutral"
            )
            attrs.append(
                FeatureAttribution(
                    feature_name=feat_name,
                    feature_value=fv,
                    shap_value=sv,
                    direction=direction,
                )
            )

        # Sort by absolute SHAP value descending
        attrs.sort(key=lambda a: abs(a.shap_value), reverse=True)

        explanations.append(
            PredictionExplanation(
                base_value=base_value,
                attributions=attrs,
                top_contributors=attrs[:top_k],
            )
        )

    return explanations


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_value(v: Any) -> Any:
    """Convert numpy types to native Python for JSON serialisation."""
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return float(v)
    if isinstance(v, np.ndarray):
        return v.tolist()
    return v
