"""
Automated insight generation for the Cross-Feature Fusion Engine.

Analyses correlation pairs, feature importances, and prediction results
to produce human-readable findings about cross-signal relationships.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from app.ml.fusion_engine.config import (
    INSIGHT_CFG,
    InsightConfig,
    SIGNAL_NAMES,
    TARGET_NAMES,
)
from app.ml.fusion_engine.features import CorrelationMatrix
from app.ml.fusion_engine.model import FusionTrainingResult, rank_feature_importance

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Insight container
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Insight:
    """A single generated finding."""

    category: str          # e.g. "predictor", "correlation", "leading-indicator"
    priority: str          # "high", "medium", "low"
    message: str           # Human-readable statement
    evidence: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "priority": self.priority,
            "message": self.message,
            "evidence": self.evidence,
        }


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------

def _correlation_insights(
    corr: CorrelationMatrix,
    cfg: InsightConfig,
) -> List[Insight]:
    """Detect strong / moderate cross-signal correlations."""
    insights: List[Insight] = []
    pairs = corr.strongest_pairs(threshold=cfg.moderate_correlation, top_k=20)

    for pair in pairs:
        strength = abs(pair["correlation"])
        direction = "positive" if pair["correlation"] > 0 else "negative"

        if strength >= cfg.strong_correlation:
            prio = "high"
            adj = "strong"
        elif strength >= cfg.moderate_correlation:
            prio = "medium"
            adj = "moderate"
        else:
            continue

        msg = (
            f"{adj.capitalize()} {direction} correlation ({pair['correlation']:.2f}) "
            f"between {pair['signal_a']} and {pair['signal_b']}."
        )

        insights.append(Insight(
            category="correlation",
            priority=prio,
            message=msg,
            evidence={
                "signal_a": pair["signal_a"],
                "signal_b": pair["signal_b"],
                "correlation": round(pair["correlation"], 4),
            },
        ))

    return insights


def _predictor_insights(
    result: FusionTrainingResult,
    cfg: InsightConfig,
) -> List[Insight]:
    """Identify top predictive features for each target."""
    insights: List[Insight] = []

    for tgt in result.feature_importances:
        ranked = rank_feature_importance(result, target=tgt)

        for entry in ranked:
            if entry["relative_importance"] < cfg.top_importance_threshold:
                continue

            # Determine which base signal this feature derives from
            base_signal = _extract_base_signal(entry["feature"])
            lag_type = _extract_lag_type(entry["feature"])

            prio = "high" if entry["relative_importance"] >= 0.12 else "medium"

            if lag_type:
                msg = (
                    f"{base_signal} ({lag_type}) is a top predictor of {tgt} "
                    f"(relative importance {entry['relative_importance']:.1%})."
                )
            else:
                msg = (
                    f"{base_signal} is a top predictor of {tgt} "
                    f"(relative importance {entry['relative_importance']:.1%})."
                )

            insights.append(Insight(
                category="predictor",
                priority=prio,
                message=msg,
                evidence={
                    "feature": entry["feature"],
                    "target": tgt,
                    "importance": entry["importance"],
                    "relative_importance": entry["relative_importance"],
                    "rank": entry["rank"],
                },
            ))

    return insights


def _leading_indicator_insights(
    result: FusionTrainingResult,
    cfg: InsightConfig,
) -> List[Insight]:
    """
    Detect when a *lagged* version of one signal is a top predictor of
    another — i.e. a leading indicator relationship.
    """
    insights: List[Insight] = []

    for tgt in result.feature_importances:
        ranked = rank_feature_importance(result, target=tgt)

        for entry in ranked[:10]:
            feat = entry["feature"]
            base = _extract_base_signal(feat)
            lag = _extract_lag_period(feat)

            if lag is None or lag < 1:
                continue

            # Only interesting when base signal != target
            if base == tgt:
                continue

            prio = "high" if entry["relative_importance"] >= 0.10 else "medium"
            msg = (
                f"{base} ({lag}-period lag) is a leading indicator of {tgt} "
                f"(rank #{entry['rank']}, importance {entry['relative_importance']:.1%})."
            )

            insights.append(Insight(
                category="leading-indicator",
                priority=prio,
                message=msg,
                evidence={
                    "feature": feat,
                    "base_signal": base,
                    "lag_periods": lag,
                    "target": tgt,
                    "relative_importance": entry["relative_importance"],
                },
            ))

    return insights


def _model_quality_insights(
    result: FusionTrainingResult,
) -> List[Insight]:
    """Flag targets with notably strong or weak model performance."""
    insights: List[Insight] = []

    for m in result.target_metrics:
        if m.r2 >= 0.7:
            insights.append(Insight(
                category="model-quality",
                priority="high",
                message=(
                    f"The fusion model achieves strong predictive power for "
                    f"{m.target} (R² = {m.r2:.3f})."
                ),
                evidence=m.to_dict(),
            ))
        elif m.r2 < 0.1:
            insights.append(Insight(
                category="model-quality",
                priority="medium",
                message=(
                    f"The fusion model has low predictive power for "
                    f"{m.target} (R² = {m.r2:.3f}). More signal data may help."
                ),
                evidence=m.to_dict(),
            ))

    return insights


# ---------------------------------------------------------------------------
# Top-level generator
# ---------------------------------------------------------------------------

def generate_insights(
    *,
    correlation: CorrelationMatrix | None = None,
    training_result: FusionTrainingResult | None = None,
    cfg: InsightConfig | None = None,
) -> List[Insight]:
    """
    Produce up to ``cfg.max_insights`` insights from available evidence.

    Parameters
    ----------
    correlation : CorrelationMatrix, optional
    training_result : FusionTrainingResult, optional
    cfg : InsightConfig, optional

    Returns
    -------
    list[Insight]
    """
    c = cfg or INSIGHT_CFG
    insights: List[Insight] = []

    if correlation is not None:
        insights.extend(_correlation_insights(correlation, c))

    if training_result is not None:
        insights.extend(_predictor_insights(training_result, c))
        insights.extend(_leading_indicator_insights(training_result, c))
        insights.extend(_model_quality_insights(training_result))

    # Sort: high → medium → low, then alphabetical
    prio_order = {"high": 0, "medium": 1, "low": 2}
    insights.sort(key=lambda i: (prio_order.get(i.priority, 9), i.message))

    return insights[: c.max_insights]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_base_signal(feature_name: str) -> str:
    """
    Given a feature like ``writing_coherence_lag_2`` return the
    base signal name (``writing_coherence``).
    """
    for sig in sorted(SIGNAL_NAMES, key=len, reverse=True):
        if feature_name.startswith(sig):
            return sig
    return feature_name


def _extract_lag_type(feature_name: str) -> Optional[str]:
    """Return human label for the lag type: 'lag-2', 'roll-3', 'roc-1', …"""
    for sig in sorted(SIGNAL_NAMES, key=len, reverse=True):
        if feature_name.startswith(sig):
            suffix = feature_name[len(sig):]
            if suffix.startswith("_lag_"):
                return f"lag-{suffix[5:]}"
            if suffix.startswith("_roll_"):
                return f"rolling-{suffix[6:]}"
            if suffix.startswith("_roc_"):
                return f"rate-of-change-{suffix[5:]}"
            return None
    return None


def _extract_lag_period(feature_name: str) -> Optional[int]:
    """Return the integer lag period if this is a _lag_ feature, else None."""
    for sig in sorted(SIGNAL_NAMES, key=len, reverse=True):
        if feature_name.startswith(sig):
            suffix = feature_name[len(sig):]
            if suffix.startswith("_lag_"):
                try:
                    return int(suffix[5:])
                except ValueError:
                    return None
    return None
