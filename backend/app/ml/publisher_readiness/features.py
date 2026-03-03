"""
Feature engineering for the Publisher Readiness Index.

Normalises the six raw input signals to [0, 1] via MinMax scaling,
then derives interaction / composite features that help the model
detect readiness patterns.

The pipeline is stateful:
  • ``fit_transform()`` learns scale parameters & imputation medians.
  • ``transform()`` applies them to new data.
  • ``get_state()`` / ``load_state()`` for persistence via joblib.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from app.ml.publisher_readiness.config import (
    ALL_FEATURES,
    DERIVED_FEATURES,
    RAW_FEATURES,
    TARGET_COLUMN,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Raw input record
# ---------------------------------------------------------------------------

@dataclass
class RawReadinessRecord:
    """
    One observation (manuscript snapshot) before feature engineering.

    All raw feature values are optional – the pipeline imputes missing
    values with per-feature medians learned during fitting.
    """

    coherence_score: Optional[float] = None
    novelty_score: Optional[float] = None
    supervision_quality_score: Optional[float] = None
    revision_density: Optional[float] = None
    citation_consistency: Optional[float] = None
    stage_completion_ratio: Optional[float] = None

    # Target (only required for training)
    acceptance_outcome: Optional[float] = None

    # Optional identifier
    researcher_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Feature engineer
# ---------------------------------------------------------------------------

class ReadinessFeatureEngineer:
    """
    Stateful feature-engineering pipeline for readiness scoring.

    Normalisation strategy:
      • Raw features already on 0–1 (scores / ratios) are kept as-is
        after clipping and null imputation.
      • ``revision_density`` (unbounded) is scaled using min/max
        learned during ``fit_transform()``.
    """

    def __init__(self) -> None:
        self._medians: Dict[str, float] = {}
        self._min: Dict[str, float] = {}
        self._max: Dict[str, float] = {}
        self._fitted = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fit_transform(
        self,
        records: Sequence[RawReadinessRecord],
    ) -> pd.DataFrame:
        """Fit imputation / scale stats and return engineered DataFrame."""
        df = self._records_to_df(records)
        self._fit_stats(df)
        df = self._normalise(df)
        df = self._engineer_derived(df)
        df = self._impute(df)
        self._fitted = True
        return df

    def transform(
        self,
        records: Sequence[RawReadinessRecord],
    ) -> pd.DataFrame:
        """Transform new records using previously fitted stats."""
        if not self._fitted:
            raise RuntimeError("ReadinessFeatureEngineer not fitted yet.")
        df = self._records_to_df(records)
        df = self._normalise(df)
        df = self._engineer_derived(df)
        df = self._impute(df)
        return df

    def get_state(self) -> Dict[str, Any]:
        return {
            "medians": self._medians,
            "min": self._min,
            "max": self._max,
            "fitted": self._fitted,
        }

    def load_state(self, state: Dict[str, Any]) -> None:
        self._medians = state["medians"]
        self._min = state["min"]
        self._max = state["max"]
        self._fitted = state["fitted"]

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _records_to_df(records: Sequence[RawReadinessRecord]) -> pd.DataFrame:
        rows: List[Dict[str, Any]] = []
        for r in records:
            rows.append({
                "coherence_score": r.coherence_score,
                "novelty_score": r.novelty_score,
                "supervision_quality_score": r.supervision_quality_score,
                "revision_density": r.revision_density,
                "citation_consistency": r.citation_consistency,
                "stage_completion_ratio": r.stage_completion_ratio,
                TARGET_COLUMN: r.acceptance_outcome,
                "researcher_id": r.researcher_id,
            })
        return pd.DataFrame(rows)

    def _fit_stats(self, df: pd.DataFrame) -> None:
        """Learn median, min, max for each raw feature from training data."""
        for col in RAW_FEATURES:
            series = pd.to_numeric(df[col], errors="coerce")
            self._medians[col] = float(series.median()) if not series.isna().all() else 0.5
            self._min[col] = float(series.min()) if not series.isna().all() else 0.0
            self._max[col] = float(series.max()) if not series.isna().all() else 1.0

    def _normalise(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Normalise raw features to [0, 1].

        Most inputs are already 0–1 scores; ``revision_density``
        (unbounded count) is min-max scaled to [0, 1].
        """
        out = df.copy()

        for col in RAW_FEATURES:
            series = pd.to_numeric(out[col], errors="coerce")
            # Impute with median before scaling
            median = self._medians.get(col, 0.5)
            series = series.fillna(median)

            lo = self._min.get(col, 0.0)
            hi = self._max.get(col, 1.0)
            rng = hi - lo
            if rng > 0:
                series = (series - lo) / rng
            else:
                series = series * 0.0 + 0.5  # constant → 0.5

            # Clip to [0, 1] for safety
            out[col] = series.clip(0.0, 1.0)

        return out

    @staticmethod
    def _engineer_derived(df: pd.DataFrame) -> pd.DataFrame:
        """Append derived / interaction features."""
        out = df.copy()

        out["quality_composite"] = out["coherence_score"] * out["novelty_score"]
        out["engagement_composite"] = (
            out["supervision_quality_score"] * out["revision_density"]
        )
        out["progress_quality"] = (
            out["stage_completion_ratio"] * out["coherence_score"]
        )
        out["revision_citation_interact"] = (
            out["revision_density"] * out["citation_consistency"]
        )

        raw_cols = [c for c in RAW_FEATURES if c in out.columns]
        out["overall_mean"] = out[raw_cols].mean(axis=1)
        out["min_signal"] = out[raw_cols].min(axis=1)

        return out

    def _impute(self, df: pd.DataFrame) -> pd.DataFrame:
        """Fill remaining NaNs in ALL_FEATURES with 0."""
        out = df.copy()
        for col in ALL_FEATURES:
            if col in out.columns:
                out[col] = out[col].fillna(0.0)
        return out
