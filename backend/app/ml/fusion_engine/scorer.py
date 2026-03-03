"""
Scorer (orchestration) for the Cross-Feature Intelligence Fusion Engine.

Composes the pipeline:

    raw observations
        → temporal alignment
            → lag / rolling / roc features
                → correlation matrix
                    → multi-target LightGBM training OR prediction
                        → automated insight generation
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd

from app.ml.fusion_engine.config import (
    INSIGHT_CFG,
    InsightConfig,
    LAGS,
    LagConfig,
    LGBMFusionParams,
    HYPERPARAMS,
    TEMPORAL,
    TemporalConfig,
)
from app.ml.fusion_engine.features import (
    CorrelationMatrix,
    build_lag_features,
    compute_correlation_matrix,
)
from app.ml.fusion_engine.insights import Insight, generate_insights
from app.ml.fusion_engine.model import (
    FusionPrediction,
    FusionTrainingResult,
    predict,
    rank_feature_importance,
    train,
)
from app.ml.fusion_engine.signals import (
    SignalObservation,
    align_multi_researcher,
    align_signals,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Full-pipeline result
# ---------------------------------------------------------------------------

@dataclass
class FusionAnalysis:
    """Complete output of the fusion analysis pipeline."""

    correlation: CorrelationMatrix
    training_result: Optional[FusionTrainingResult]
    predictions: Optional[List[FusionPrediction]]
    insights: List[Insight]
    n_observations: int
    n_aligned_periods: int
    n_features: int
    feature_names: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "correlation": self.correlation.to_dict(),
            "training_result": (
                self.training_result.to_dict()
                if self.training_result else None
            ),
            "predictions": (
                [p.to_dict() for p in self.predictions]
                if self.predictions else None
            ),
            "insights": [i.to_dict() for i in self.insights],
            "n_observations": self.n_observations,
            "n_aligned_periods": self.n_aligned_periods,
            "n_features": self.n_features,
            "feature_names": self.feature_names,
        }


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def analyse(
    observations: Sequence[SignalObservation],
    *,
    temporal_config: TemporalConfig | None = None,
    lag_config: LagConfig | None = None,
    params: LGBMFusionParams | None = None,
    insight_config: InsightConfig | None = None,
    do_train: bool = True,
    do_predict: bool = True,
    save_model: bool = True,
    min_coverage: float = 0.3,
) -> FusionAnalysis:
    """
    Run the complete fusion pipeline from raw observations to insights.

    Parameters
    ----------
    observations : sequence of SignalObservation
    temporal_config : TemporalConfig, optional
    lag_config : LagConfig, optional
    params : LGBMFusionParams, optional
    insight_config : InsightConfig, optional
    do_train : bool
        Whether to train the multi-target model.
    do_predict : bool
        Whether to generate predictions on the feature set.
    save_model : bool
        Whether to persist trained models to disk.
    min_coverage : float
        Minimum signal coverage per period.

    Returns
    -------
    FusionAnalysis
    """
    t_cfg = temporal_config or TEMPORAL
    l_cfg = lag_config or LAGS
    hp = params or HYPERPARAMS
    i_cfg = insight_config or INSIGHT_CFG

    # 1) Align signals
    aligned = align_signals(
        observations,
        config=t_cfg,
        min_coverage=min_coverage,
    )

    if aligned.empty:
        return FusionAnalysis(
            correlation=CorrelationMatrix(
                matrix=pd.DataFrame(), signal_names=[]
            ),
            training_result=None,
            predictions=None,
            insights=[],
            n_observations=len(observations),
            n_aligned_periods=0,
            n_features=0,
            feature_names=[],
        )

    # 2) Correlation matrix (on base signals)
    corr = compute_correlation_matrix(aligned)

    # 3) Build features
    featured, feature_names = build_lag_features(aligned, lag_config=l_cfg)

    # 4) Train model
    training_result: Optional[FusionTrainingResult] = None
    if do_train and len(featured) >= 5:
        training_result = train(
            featured,
            feature_names,
            params=hp,
            save=save_model,
        )

    # 5) Predict
    preds: Optional[List[FusionPrediction]] = None
    if do_predict and training_result is not None:
        preds = predict(featured, feature_names)

    # 6) Generate insights
    insights = generate_insights(
        correlation=corr,
        training_result=training_result,
        cfg=i_cfg,
    )

    logger.info(
        "Fusion analysis complete: %d periods, %d features, %d insights",
        len(featured),
        len(feature_names),
        len(insights),
    )

    return FusionAnalysis(
        correlation=corr,
        training_result=training_result,
        predictions=preds,
        insights=insights,
        n_observations=len(observations),
        n_aligned_periods=len(featured),
        n_features=len(feature_names),
        feature_names=feature_names,
    )


def analyse_from_dataframe(
    df: pd.DataFrame,
    *,
    lag_config: LagConfig | None = None,
    params: LGBMFusionParams | None = None,
    insight_config: InsightConfig | None = None,
    do_train: bool = True,
    do_predict: bool = True,
    save_model: bool = True,
) -> FusionAnalysis:
    """
    Shortcut when the caller already has an aligned DataFrame
    (skips observation parsing and temporal alignment).
    """
    l_cfg = lag_config or LAGS
    hp = params or HYPERPARAMS
    i_cfg = insight_config or INSIGHT_CFG

    corr = compute_correlation_matrix(df)
    featured, feature_names = build_lag_features(df, lag_config=l_cfg)

    training_result: Optional[FusionTrainingResult] = None
    if do_train and len(featured) >= 5:
        training_result = train(
            featured,
            feature_names,
            params=hp,
            save=save_model,
        )

    preds: Optional[List[FusionPrediction]] = None
    if do_predict and training_result is not None:
        preds = predict(featured, feature_names)

    insights = generate_insights(
        correlation=corr,
        training_result=training_result,
        cfg=i_cfg,
    )

    return FusionAnalysis(
        correlation=corr,
        training_result=training_result,
        predictions=preds,
        insights=insights,
        n_observations=0,
        n_aligned_periods=len(featured),
        n_features=len(feature_names),
        feature_names=feature_names,
    )
