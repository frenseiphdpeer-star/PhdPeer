"""
Feature engineering for the Opportunity Matching Engine.

Transforms raw match requests into model-ready feature vectors by:
  1. Computing cosine similarity between researcher & opportunity embeddings.
  2. Deriving urgency from time-to-deadline.
  3. One-hot encoding stage_type and discipline.
  4. Computing discipline_match flag.
  5. Passing through numeric scalars (prior_success_rate, timeline_readiness).

The pipeline is **stateful** – it learns imputation medians on the training
set (``fit_transform``) and applies them to new data (``transform``).
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from app.ml.opportunity_matching.config import (
    ALL_FEATURES,
    DISCIPLINE_ONEHOT_FEATURES,
    DISCIPLINES,
    NUMERIC_FEATURES,
    SCORING,
    STAGE_ONEHOT_FEATURES,
    STAGE_TYPES,
    TARGET_COLUMN,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Input record
# ---------------------------------------------------------------------------

@dataclass
class MatchRecord:
    """
    Single researcher ↔ opportunity pair, before feature engineering.

    All scalar fields are optional; the pipeline imputes missing values.
    """

    # ── Pre-computed from embeddings layer (or passed directly) ───────
    cosine_similarity: Optional[float] = None

    # ── Categorical ───────────────────────────────────────────────────
    stage_type: Optional[str] = None          # e.g. "proposal", "writing"
    researcher_discipline: Optional[str] = None
    opportunity_discipline: Optional[str] = None

    # ── Numeric scalars ───────────────────────────────────────────────
    prior_success_rate: Optional[float] = None      # 0–1 fraction
    prior_application_count: Optional[int] = None
    timeline_readiness_score: Optional[float] = None  # 0–1 or 0–100
    days_to_deadline: Optional[float] = None          # ≥ 0

    # ── Label (training only) ─────────────────────────────────────────
    accepted: Optional[int] = None  # 1 = accepted / success, 0 = not


# ---------------------------------------------------------------------------
# Urgency helper
# ---------------------------------------------------------------------------

def compute_urgency(
    days_to_deadline: Optional[float],
    *,
    max_days: int = SCORING.urgency_max_days,
    zero_days: int = SCORING.urgency_zero_days,
) -> float:
    """
    Map days-to-deadline → urgency score in [0, 1].

    Uses a logistic curve so that deadlines within *max_days* yield ~1.0
    and deadlines beyond *zero_days* yield ~0.0, with a smooth transition.
    """
    if days_to_deadline is None or days_to_deadline < 0:
        return 0.0

    if days_to_deadline <= max_days:
        return 1.0
    if days_to_deadline >= zero_days:
        return 0.0

    # Normalise to (0, 1) between max_days and zero_days, then invert
    ratio = (days_to_deadline - max_days) / (zero_days - max_days)
    # Logistic decay
    return float(1.0 / (1.0 + math.exp(6 * (ratio - 0.5))))


# ---------------------------------------------------------------------------
# Feature engineer
# ---------------------------------------------------------------------------

class MatchFeatureEngineer:
    """
    Stateful feature-engineering pipeline for opportunity matching.

    ``fit_transform`` learns imputation medians; ``transform`` applies them.
    """

    def __init__(self) -> None:
        self._medians: Dict[str, float] = {}
        self._fitted = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fit_transform(
        self,
        records: Sequence[MatchRecord],
    ) -> pd.DataFrame:
        df = self._records_to_df(records)
        self._fit_medians(df)
        df = self._impute(df)
        self._fitted = True
        return df

    def transform(
        self,
        records: Sequence[MatchRecord],
    ) -> pd.DataFrame:
        if not self._fitted:
            raise RuntimeError("MatchFeatureEngineer not fitted yet.")
        df = self._records_to_df(records)
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
    def _records_to_df(records: Sequence[MatchRecord]) -> pd.DataFrame:
        rows: List[Dict[str, Any]] = []
        for r in records:
            row: Dict[str, Any] = {}

            # Cosine similarity (already computed or will be imputed)
            row["cosine_similarity"] = r.cosine_similarity

            # Numeric passthrough
            row["prior_success_rate"] = r.prior_success_rate
            row["prior_application_count"] = (
                float(r.prior_application_count)
                if r.prior_application_count is not None
                else None
            )
            row["timeline_readiness_score"] = r.timeline_readiness_score
            row["days_to_deadline"] = r.days_to_deadline

            # Urgency derived from deadline
            row["urgency_score"] = compute_urgency(r.days_to_deadline)

            # Discipline match flag
            if (
                r.researcher_discipline is not None
                and r.opportunity_discipline is not None
            ):
                row["discipline_match"] = (
                    1.0
                    if r.researcher_discipline == r.opportunity_discipline
                    else 0.0
                )
            else:
                row["discipline_match"] = None

            # Stage type one-hot
            for st in STAGE_TYPES:
                row[f"stage_{st}"] = (
                    1.0 if r.stage_type == st else 0.0
                )

            # Discipline one-hot (use researcher discipline)
            for d in DISCIPLINES:
                row[f"disc_{d}"] = (
                    1.0 if r.researcher_discipline == d else 0.0
                )

            # Target (training only)
            if r.accepted is not None:
                row[TARGET_COLUMN] = int(r.accepted)

            rows.append(row)

        return pd.DataFrame(rows)

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
