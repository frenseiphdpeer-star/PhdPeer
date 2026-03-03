"""
Feature engineering for dropout risk prediction.

Transforms raw longitudinal PhD signals into model-ready features,
including **slope / trend** computations and interaction terms that
capture the dynamics of student engagement and progress.

The pipeline is stateful (learns medians for imputation on the training
set) and can be persisted / loaded via ``get_state`` / ``load_state``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from app.ml.dropout_risk.config import (
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
class RawDropoutRecord:
    """
    One observation (student-snapshot) before feature engineering.

    All values are optional – the pipeline imputes missing values.
    """

    supervision_latency_avg: Optional[float] = None
    supervision_gap_max: Optional[float] = None
    milestone_delay_ratio: Optional[float] = None
    health_score_decline_slope: Optional[float] = None
    opportunity_engagement_count: Optional[int] = None
    writing_coherence_trend: Optional[float] = None
    revision_response_rate: Optional[float] = None
    peer_connection_count: Optional[int] = None

    # Target (only needed for training)
    dropout: Optional[int] = None

    # Optional longitudinal history for slope/trend features
    health_score_history: Optional[List[float]] = None
    engagement_history: Optional[List[float]] = None
    weeks_since_last_supervision: Optional[float] = None


# ---------------------------------------------------------------------------
# Feature engineer
# ---------------------------------------------------------------------------

class DropoutFeatureEngineer:
    """
    Stateful feature-engineering pipeline for dropout risk prediction.

    Call ``fit_transform()`` on the training set, then ``transform()``
    on new data.  Use ``get_state()`` / ``load_state()`` for persistence.
    """

    def __init__(self) -> None:
        self._medians: Dict[str, float] = {}
        self._fitted = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fit_transform(
        self,
        records: Sequence[RawDropoutRecord],
    ) -> pd.DataFrame:
        """Fit imputation stats and return the engineered DataFrame."""
        df = self._records_to_df(records)
        df = self._engineer_features(df)
        self._fit_medians(df)
        df = self._impute(df)
        self._fitted = True
        return df

    def transform(
        self,
        records: Sequence[RawDropoutRecord],
    ) -> pd.DataFrame:
        """Transform new records using previously-fitted stats."""
        if not self._fitted:
            raise RuntimeError("DropoutFeatureEngineer not fitted yet.")
        df = self._records_to_df(records)
        df = self._engineer_features(df)
        df = self._impute(df)
        return df

    def get_state(self) -> Dict[str, Any]:
        return {"medians": self._medians, "fitted": self._fitted}

    def load_state(self, state: Dict[str, Any]) -> None:
        self._medians = state["medians"]
        self._fitted = state["fitted"]

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _records_to_df(records: Sequence[RawDropoutRecord]) -> pd.DataFrame:
        rows: List[Dict[str, Any]] = []
        for r in records:
            row: Dict[str, Any] = {
                "supervision_latency_avg": r.supervision_latency_avg,
                "supervision_gap_max": r.supervision_gap_max,
                "milestone_delay_ratio": r.milestone_delay_ratio,
                "health_score_decline_slope": r.health_score_decline_slope,
                "opportunity_engagement_count": r.opportunity_engagement_count,
                "writing_coherence_trend": r.writing_coherence_trend,
                "revision_response_rate": r.revision_response_rate,
                "peer_connection_count": r.peer_connection_count,
                "weeks_since_last_supervision": r.weeks_since_last_supervision,
            }
            # Compute slopes from history if available
            if r.health_score_history and len(r.health_score_history) >= 2:
                row["health_score_decline_slope"] = _compute_slope(
                    r.health_score_history
                )
            if r.engagement_history and len(r.engagement_history) >= 2:
                row["risk_velocity"] = _compute_slope(r.engagement_history)
            else:
                row["risk_velocity"] = None

            if r.dropout is not None:
                row[TARGET_COLUMN] = int(r.dropout)
            rows.append(row)
        return pd.DataFrame(rows)

    @staticmethod
    def _engineer_features(df: pd.DataFrame) -> pd.DataFrame:
        """Create derived / interaction features."""
        df = df.copy()

        # supervision_intensity = avg_latency × gap_max
        lat = pd.to_numeric(df.get("supervision_latency_avg"), errors="coerce")
        gap = pd.to_numeric(df.get("supervision_gap_max"), errors="coerce")
        df["supervision_intensity"] = lat * gap

        # delay × health interaction
        delay = pd.to_numeric(df.get("milestone_delay_ratio"), errors="coerce")
        slope = pd.to_numeric(df.get("health_score_decline_slope"), errors="coerce")
        df["delay_health_interaction"] = delay * slope

        # engagement per peer connection
        eng = pd.to_numeric(df.get("opportunity_engagement_count"), errors="coerce")
        peers = pd.to_numeric(df.get("peer_connection_count"), errors="coerce")
        df["engagement_per_peer"] = eng / peers.replace(0, np.nan)

        # risk_velocity – already computed from history or left as NaN
        if "risk_velocity" not in df.columns:
            df["risk_velocity"] = np.nan

        # weeks_since_last_supervision – already populated or NaN
        if "weeks_since_last_supervision" not in df.columns:
            df["weeks_since_last_supervision"] = np.nan

        return df

    def _fit_medians(self, df: pd.DataFrame) -> None:
        for col in ALL_FEATURES:
            if col in df.columns:
                med = pd.to_numeric(df[col], errors="coerce").median()
                self._medians[col] = float(med) if pd.notna(med) else 0.0
            else:
                self._medians[col] = 0.0

    def _impute(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        for col in ALL_FEATURES:
            if col not in df.columns:
                df[col] = self._medians.get(col, 0.0)
            else:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(
                    self._medians.get(col, 0.0)
                )
        return df


# ---------------------------------------------------------------------------
# Utility: slope computation
# ---------------------------------------------------------------------------

def _compute_slope(values: List[float]) -> float:
    """Least-squares slope of *values* over integer time indices."""
    n = len(values)
    if n < 2:
        return 0.0
    x = np.arange(n, dtype=np.float64)
    y = np.array(values, dtype=np.float64)
    # polyfit degree 1 → [slope, intercept]
    coeffs = np.polyfit(x, y, 1)
    return float(coeffs[0])
