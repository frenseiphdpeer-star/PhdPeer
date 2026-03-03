"""
Scorer (orchestration) for the Publisher Readiness Index.

Composes the full pipeline:

    raw readiness records
        → feature engineering (normalise + derive)
            → LightGBM regression
                → 0–100 readiness score
                    → category + confidence
                        → feature importance ranking
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from app.ml.publisher_readiness.config import (
    ALL_FEATURES,
    HYPERPARAMS,
    LGBMReadinessParams,
    QUANTILE_CFG,
    QuantileConfig,
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
    train,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pipeline result
# ---------------------------------------------------------------------------

@dataclass
class ReadinessAnalysis:
    """Complete output of the Publisher Readiness pipeline."""

    training_result: Optional[TrainingResult]
    predictions: List[ReadinessPrediction]
    feature_importances: Dict[str, float]
    n_samples: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "training_result": (
                self.training_result.to_dict()
                if self.training_result else None
            ),
            "predictions": [p.to_dict() for p in self.predictions],
            "feature_importances": {
                k: round(v, 4)
                for k, v in self.feature_importances.items()
            },
            "n_samples": self.n_samples,
        }


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def analyse(
    records: Sequence[RawReadinessRecord],
    *,
    do_train: bool = True,
    save_model: bool = True,
    params: Optional[LGBMReadinessParams] = None,
    quantile_cfg: Optional[QuantileConfig] = None,
) -> ReadinessAnalysis:
    """
    Run the full Publisher Readiness pipeline from raw records to
    scored predictions with confidence bands.

    If ``do_train=True`` (default), the model is trained first on the
    provided records (which must include ``acceptance_outcome``).  Then
    predictions are generated for all records.
    """
    hp = params or HYPERPARAMS
    qc = quantile_cfg or QUANTILE_CFG

    if not records:
        return ReadinessAnalysis(
            training_result=None,
            predictions=[],
            feature_importances={},
            n_samples=0,
        )

    # 1) Train
    training_result: Optional[TrainingResult] = None
    if do_train:
        training_result = train(
            records, params=hp, quantile_cfg=qc, save=save_model,
        )

    # 2) Predict (all records)
    preds = predict(records)

    # 3) Feature importances
    importances = rank_feature_importance()

    logger.info(
        "Publisher readiness analysis complete: %d samples scored",
        len(preds),
    )

    return ReadinessAnalysis(
        training_result=training_result,
        predictions=preds,
        feature_importances=importances,
        n_samples=len(records),
    )


def score_only(
    records: Sequence[RawReadinessRecord],
) -> List[ReadinessPrediction]:
    """
    Score records using an already-trained model (no training step).
    """
    return predict(records)
