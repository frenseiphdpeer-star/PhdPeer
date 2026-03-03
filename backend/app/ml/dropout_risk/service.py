"""
Dropout Risk Service – public entry-point for the API layer.

Manages model lifecycle, synthetic data generation, and exposes
high-level functions for prediction and explanation.

Provides:
  * ``predict_risk()``       – predict dropout probability
  * ``explain_risk()``       – SHAP-explained predictions
  * ``train_model()``        – train both classifiers
  * ``bootstrap_model()``    – train on synthetic data for quick start
  * ``get_model_status()``   – report model metadata
  * ``generate_synthetic_dataset()`` – deterministic dataset for demos
"""

from __future__ import annotations

import logging
import random as _random
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from app.ml.dropout_risk.config import (
    ALL_FEATURES,
    EARLY_WARNING_MAX_WEEKS,
    EARLY_WARNING_MIN_WEEKS,
    RISK_THRESHOLD_RED,
    RISK_THRESHOLD_YELLOW,
)
from app.ml.dropout_risk.features import RawDropoutRecord

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Predict
# ---------------------------------------------------------------------------

def predict_risk(
    records: Sequence[RawDropoutRecord],
    *,
    model: str = "xgboost",
    _bundle: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Predict dropout probability for one or more student snapshots.

    Returns a list of dicts with ``dropout_probability``,
    ``risk_category``, and ``model_used``.
    """
    from app.ml.dropout_risk.model import predict

    preds = predict(
        records,
        model=model,
        yellow_threshold=RISK_THRESHOLD_YELLOW,
        red_threshold=RISK_THRESHOLD_RED,
        _bundle=_bundle,
    )
    return [p.to_dict() for p in preds]


# ---------------------------------------------------------------------------
# Explain
# ---------------------------------------------------------------------------

def explain_risk(
    records: Sequence[RawDropoutRecord],
    *,
    model: str = "xgboost",
    top_n: int = 5,
    _bundle: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Predict dropout risk **with SHAP explanations**.

    Returns a list of dicts including ``top_risk_factors``.
    """
    from app.ml.dropout_risk.explainability import explain

    explanations = explain(
        records,
        model=model,
        top_n=top_n,
        yellow_threshold=RISK_THRESHOLD_YELLOW,
        red_threshold=RISK_THRESHOLD_RED,
        _bundle=_bundle,
    )
    return [e.to_dict() for e in explanations]


# ---------------------------------------------------------------------------
# Train
# ---------------------------------------------------------------------------

def train_model(
    records: Sequence[RawDropoutRecord],
    *,
    save: bool = True,
) -> Dict[str, Any]:
    """Train both classifiers and return evaluation metrics."""
    from app.ml.dropout_risk.model import train

    result = train(records, save=save)
    return result.to_dict()


def bootstrap_model(
    n: int = 500,
    *,
    save: bool = True,
) -> Dict[str, Any]:
    """Train on a synthetic dataset for quick-start / demo."""
    records = generate_synthetic_dataset(n=n)
    return train_model(records, save=save)


# ---------------------------------------------------------------------------
# Model status
# ---------------------------------------------------------------------------

def get_model_status() -> Dict[str, Any]:
    """Return metadata about the current trained model."""
    from app.ml.dropout_risk import config as _cfg
    import json

    meta_path = _cfg.DROPOUT_ARTIFACTS_DIR / _cfg.METADATA_FILENAME
    if meta_path.exists():
        with open(meta_path) as f:
            meta = json.load(f)
        return {"loaded": True, **meta}
    return {"loaded": False}


# ---------------------------------------------------------------------------
# Synthetic data generation
# ---------------------------------------------------------------------------

def generate_synthetic_dataset(
    n: int = 500,
    seed: int = 42,
) -> List[RawDropoutRecord]:
    """
    Generate *n* synthetic student-snapshot records with realistic
    correlations between features and the dropout label.

    Designed so that high supervision latency, declining health scores,
    low engagement, and poor writing coherence correlate with dropout.
    """
    rng = np.random.RandomState(seed)
    py_rng = _random.Random(seed)

    records: List[RawDropoutRecord] = []

    for _ in range(n):
        # Base risk factor (latent)
        risk = rng.beta(2, 5)  # Skewed toward low risk

        # Features correlated with risk
        supervision_latency = float(
            np.clip(rng.normal(7 + risk * 20, 3), 1, 60)
        )
        supervision_gap = float(
            np.clip(rng.normal(14 + risk * 30, 5), 2, 90)
        )
        delay_ratio = float(
            np.clip(rng.beta(2 + risk * 5, 5 - risk * 3), 0, 1)
        )
        health_slope = float(
            np.clip(rng.normal(-risk * 0.5, 0.15), -1, 0.3)
        )
        engagement = int(
            np.clip(rng.poisson(max(1, 8 - risk * 10)), 0, 30)
        )
        coherence_trend = float(
            np.clip(rng.normal(0.5 - risk * 0.8, 0.2), -1, 1)
        )
        revision_rate = float(
            np.clip(rng.beta(5 - risk * 3, 2 + risk * 3), 0, 1)
        )
        peer_count = int(
            np.clip(rng.poisson(max(1, 5 - risk * 6)), 0, 20)
        )

        # Health score history (declining for high risk)
        base_health = 80 - risk * 30
        history = [
            float(np.clip(base_health + rng.normal(0, 5) - i * health_slope * 10, 0, 100))
            for i in range(6)
        ]

        weeks_since = float(np.clip(supervision_gap / 7.0 + rng.normal(0, 1), 0, 20))

        # Dropout label (noisy function of risk)
        dropout_prob = 1 / (1 + np.exp(-(risk * 6 - 2.5 + rng.normal(0, 0.5))))
        dropout = int(rng.random() < dropout_prob)

        records.append(RawDropoutRecord(
            supervision_latency_avg=round(supervision_latency, 2),
            supervision_gap_max=round(supervision_gap, 2),
            milestone_delay_ratio=round(delay_ratio, 4),
            health_score_decline_slope=round(health_slope, 4),
            opportunity_engagement_count=engagement,
            writing_coherence_trend=round(coherence_trend, 4),
            revision_response_rate=round(revision_rate, 4),
            peer_connection_count=peer_count,
            dropout=dropout,
            health_score_history=history,
            weeks_since_last_supervision=round(weeks_since, 2),
        ))

    pos = sum(1 for r in records if r.dropout == 1)
    logger.info("Generated %d synthetic records (%.1f%% dropout)", n, 100 * pos / n)
    return records
