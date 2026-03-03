"""
Feature engineering pipeline for milestone duration prediction.

Responsibilities
----------------
* Accept raw heterogeneous inputs (dicts, ORM objects, DataFrames).
* Encode categoricals via LabelEncoder (fitted at training time, persisted).
* Impute missing numerics with column medians (fitted at training time).
* Derive ``prior_delay_ratio`` from ``prior_delay_patterns`` list.
* Return a clean ``pandas.DataFrame`` ready for LightGBM.

Design constraints
------------------
* Deterministic – same input always produces same output.
* Stateful – encoders / imputers are fitted once, then persisted alongside the
  model so that inference uses identical transforms.
* Null-safe – every feature has a defined missing-value strategy.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Union

import numpy as np
import pandas as pd
from sklearn.preprocessing import LabelEncoder

from app.ml.config import (
    ALL_FEATURES,
    CATEGORICAL_FEATURES,
    NUMERIC_FEATURES,
    TARGET_COLUMN,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public data-class: a single raw sample before engineering
# ---------------------------------------------------------------------------
@dataclass
class RawMilestoneRecord:
    """
    One observation row – the union of all available features.

    Callers may leave any field as ``None``; the pipeline handles missingness.
    ``prior_delay_patterns`` is a list of booleans (True = delayed) from which
    ``prior_delay_ratio`` is derived.
    """

    stage_type: Optional[str] = None
    discipline: Optional[str] = None
    milestone_type: Optional[str] = None
    number_of_prior_milestones: Optional[int] = None
    supervision_latency_avg: Optional[float] = None
    writing_velocity_score: Optional[float] = None
    prior_delay_patterns: Optional[List[bool]] = None   # raw; will be aggregated
    opportunity_engagement_score: Optional[float] = None
    health_score_trajectory: Optional[float] = None
    revision_density: Optional[float] = None
    historical_completion_time: Optional[float] = None
    # Label – only present in training data
    actual_duration_months: Optional[float] = None

    def to_flat_dict(self) -> Dict[str, Any]:
        """Flatten to dict, deriving ``prior_delay_ratio``."""
        pdp = self.prior_delay_patterns or []
        prior_delay_ratio = (
            sum(pdp) / len(pdp) if pdp else None
        )
        return {
            "stage_type": self.stage_type,
            "discipline": self.discipline,
            "milestone_type": self.milestone_type,
            "number_of_prior_milestones": self.number_of_prior_milestones,
            "supervision_latency_avg": self.supervision_latency_avg,
            "writing_velocity_score": self.writing_velocity_score,
            "prior_delay_ratio": prior_delay_ratio,
            "opportunity_engagement_score": self.opportunity_engagement_score,
            "health_score_trajectory": self.health_score_trajectory,
            "revision_density": self.revision_density,
            "historical_completion_time": self.historical_completion_time,
            TARGET_COLUMN: self.actual_duration_months,
        }


# ---------------------------------------------------------------------------
# Feature-engineering transformer (stateful – fit / transform)
# ---------------------------------------------------------------------------
class FeatureEngineer:
    """
    Stateful feature transformer.

    Usage::

        fe = FeatureEngineer()
        X_train, y_train = fe.fit_transform(training_records)
        X_test = fe.transform(test_records)

    After ``fit()``, internal state (label-encoder mappings + median fills) is
    accessible via ``get_state()`` / ``load_state()`` for persistence.
    """

    def __init__(self) -> None:
        self._label_encoders: Dict[str, LabelEncoder] = {}
        self._medians: Dict[str, float] = {}
        self._is_fitted: bool = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fit_transform(
        self,
        records: Sequence[Union[RawMilestoneRecord, Dict[str, Any]]],
    ) -> tuple[pd.DataFrame, pd.Series]:
        """Fit encoders/imputers on *records* and return (X, y)."""
        df = self._to_dataframe(records)
        self._fit_label_encoders(df)
        self._fit_medians(df)
        self._is_fitted = True
        return self._apply(df, has_target=True)

    def transform(
        self,
        records: Sequence[Union[RawMilestoneRecord, Dict[str, Any]]],
    ) -> pd.DataFrame:
        """Transform *records* using previously-fitted state. Returns X only."""
        if not self._is_fitted:
            raise RuntimeError("FeatureEngineer has not been fitted yet.")
        df = self._to_dataframe(records)
        X, _ = self._apply(df, has_target=False)
        return X

    # ------------------------------------------------------------------
    # State persistence helpers
    # ------------------------------------------------------------------

    def get_state(self) -> Dict[str, Any]:
        """Serialise internal state for ``joblib`` persistence."""
        return {
            "label_encoders": {
                col: {"classes": le.classes_.tolist()}
                for col, le in self._label_encoders.items()
            },
            "medians": self._medians,
            "is_fitted": self._is_fitted,
        }

    def load_state(self, state: Dict[str, Any]) -> None:
        """Restore internal state from a persisted dict."""
        self._medians = state["medians"]
        self._is_fitted = state["is_fitted"]
        self._label_encoders = {}
        for col, le_data in state["label_encoders"].items():
            le = LabelEncoder()
            le.classes_ = np.array(le_data["classes"])
            self._label_encoders[col] = le

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _to_dataframe(
        records: Sequence[Union[RawMilestoneRecord, Dict[str, Any]]],
    ) -> pd.DataFrame:
        rows: List[Dict[str, Any]] = []
        for rec in records:
            if isinstance(rec, RawMilestoneRecord):
                rows.append(rec.to_flat_dict())
            elif isinstance(rec, dict):
                # Accept pre-flattened dicts (must already contain prior_delay_ratio)
                rows.append(rec)
            else:
                raise TypeError(f"Unsupported record type: {type(rec)}")
        return pd.DataFrame(rows)

    def _fit_label_encoders(self, df: pd.DataFrame) -> None:
        for col in CATEGORICAL_FEATURES:
            le = LabelEncoder()
            if col not in df.columns:
                df[col] = np.nan
            valid = df[col].dropna().astype(str)
            if valid.empty:
                le.classes_ = np.array(["__unknown__"])
            else:
                le.fit(valid)
                # Reserve space for unseen categories at inference time
                le.classes_ = np.append(le.classes_, "__unknown__")
            self._label_encoders[col] = le

    def _fit_medians(self, df: pd.DataFrame) -> None:
        for col in NUMERIC_FEATURES:
            if col in df.columns and df[col].notna().any():
                self._medians[col] = float(
                    pd.to_numeric(df[col], errors="coerce").median()
                )
            else:
                self._medians[col] = 0.0

    def _apply(
        self,
        df: pd.DataFrame,
        has_target: bool,
    ) -> tuple[pd.DataFrame, Optional[pd.Series]]:
        df = df.copy()

        # --- Categorical encoding -------------------------------------------
        for col in CATEGORICAL_FEATURES:
            if col not in df.columns:
                df[col] = np.nan
            le = self._label_encoders[col]
            unknown_code = int(np.where(le.classes_ == "__unknown__")[0][0])
            df[col] = df[col].fillna("__unknown__").astype(str)
            df[col] = df[col].apply(
                lambda v, _le=le, _uc=unknown_code: (
                    int(_le.transform([v])[0])
                    if v in _le.classes_
                    else _uc
                )
            )

        # --- Numeric imputation ---------------------------------------------
        for col in NUMERIC_FEATURES:
            if col not in df.columns:
                df[col] = np.nan
            df[col] = pd.to_numeric(df[col], errors="coerce")
            df[col] = df[col].fillna(self._medians.get(col, 0.0))

        # --- Assemble X (and y if training) ---------------------------------
        X = df[ALL_FEATURES].copy()

        y: Optional[pd.Series] = None
        if has_target:
            if TARGET_COLUMN not in df.columns:
                raise ValueError(
                    f"Training data must include the target column '{TARGET_COLUMN}'."
                )
            y = df[TARGET_COLUMN].copy()
            if y.isna().any():
                logger.warning(
                    "Target column has %d missing values – rows will be dropped.",
                    int(y.isna().sum()),
                )
                mask = y.notna()
                X = X.loc[mask].reset_index(drop=True)
                y = y.loc[mask].reset_index(drop=True)

        return X, y
