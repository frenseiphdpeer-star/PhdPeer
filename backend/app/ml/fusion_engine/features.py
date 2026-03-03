"""
Feature engineering for the Cross-Feature Fusion Engine.

Transforms an aligned signal DataFrame into model-ready features by:

1. Creating **lag features** (e.g. writing_coherence_lag_1).
2. Creating **rolling-mean features** (e.g. health_score_roll_3).
3. Creating **rate-of-change features** (Δ per period).
4. Computing the **correlation matrix** between all base signals.
5. Dropping rows with NaN introduced by lag/rolling operations.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from app.ml.fusion_engine.config import (
    LAGS,
    LagConfig,
    SIGNAL_NAMES,
    TARGET_NAMES,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Feature engineering
# ---------------------------------------------------------------------------

def build_lag_features(
    aligned: pd.DataFrame,
    *,
    lag_config: LagConfig | None = None,
    targets: List[str] | None = None,
) -> Tuple[pd.DataFrame, List[str]]:
    """
    Expand an aligned signal DataFrame with lag, rolling, and
    rate-of-change features.

    Parameters
    ----------
    aligned : pd.DataFrame
        Time-aligned signals (output of ``align_signals``).
    lag_config : LagConfig, optional
        Override default lag parameters.
    targets : list[str], optional
        Which columns are targets (default: TARGET_NAMES present in df).

    Returns
    -------
    (feature_df, feature_names)
        ``feature_df`` includes both features and target columns.
        ``feature_names`` lists only the input feature column names
        (excludes targets).
    """
    cfg = lag_config or LAGS
    tgt_cols = targets or [c for c in TARGET_NAMES if c in aligned.columns]
    signal_cols = [c for c in aligned.columns if c not in tgt_cols]

    df = aligned.copy()
    feature_cols: List[str] = list(signal_cols)  # base signals

    # ── Lag features ──────────────────────────────────────────────────
    for col in signal_cols:
        for lag in cfg.lag_periods:
            name = f"{col}_lag_{lag}"
            df[name] = df[col].shift(lag)
            feature_cols.append(name)

    # ── Rolling means ─────────────────────────────────────────────────
    for col in signal_cols:
        for win in cfg.rolling_windows:
            name = f"{col}_roll_{win}"
            df[name] = df[col].rolling(window=win, min_periods=1).mean()
            feature_cols.append(name)

    # ── Rate of change ────────────────────────────────────────────────
    for col in signal_cols:
        for roc in cfg.roc_periods:
            name = f"{col}_roc_{roc}"
            df[name] = df[col].diff(periods=roc)
            feature_cols.append(name)

    # ── Drop rows with NaN from lagging ───────────────────────────────
    max_lag = max(cfg.lag_periods) if cfg.lag_periods else 0
    if max_lag > 0:
        df = df.iloc[max_lag:].copy()

    # Fill remaining NaN in features with 0
    df[feature_cols] = df[feature_cols].fillna(0.0)

    logger.info(
        "Built %d features (%d base + %d lag + %d rolling + %d roc) "
        "over %d periods",
        len(feature_cols),
        len(signal_cols),
        len(signal_cols) * len(cfg.lag_periods),
        len(signal_cols) * len(cfg.rolling_windows),
        len(signal_cols) * len(cfg.roc_periods),
        len(df),
    )

    return df, feature_cols


# ---------------------------------------------------------------------------
# Correlation matrix
# ---------------------------------------------------------------------------

@dataclass
class CorrelationMatrix:
    """Holds the pair-wise Pearson correlation matrix of base signals."""

    matrix: pd.DataFrame          # signal × signal
    signal_names: List[str]

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-safe nested dict."""
        return {
            "signal_names": self.signal_names,
            "matrix": {
                row: {
                    col: round(float(self.matrix.loc[row, col]), 4)
                    for col in self.signal_names
                }
                for row in self.signal_names
            },
        }

    def strongest_pairs(
        self,
        threshold: float = 0.3,
        top_k: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Return the *top_k* signal pairs with |correlation| ≥ threshold,
        sorted by absolute correlation descending.
        """
        pairs: List[Dict[str, Any]] = []
        n = len(self.signal_names)
        for i in range(n):
            for j in range(i + 1, n):
                r = float(self.matrix.iloc[i, j])
                if abs(r) >= threshold:
                    pairs.append({
                        "signal_a": self.signal_names[i],
                        "signal_b": self.signal_names[j],
                        "correlation": round(r, 4),
                        "abs_correlation": round(abs(r), 4),
                    })
        pairs.sort(key=lambda p: p["abs_correlation"], reverse=True)
        return pairs[:top_k]


def compute_correlation_matrix(
    aligned: pd.DataFrame,
) -> CorrelationMatrix:
    """
    Compute Pearson correlation between all base signal columns.

    Parameters
    ----------
    aligned : pd.DataFrame
        Time-aligned signals (only base signal columns are used).

    Returns
    -------
    CorrelationMatrix
    """
    cols = [c for c in SIGNAL_NAMES if c in aligned.columns]
    if len(cols) < 2:
        # Return identity-like matrix for single signal
        mat = pd.DataFrame(
            np.eye(len(cols)),
            index=cols,
            columns=cols,
        )
        return CorrelationMatrix(matrix=mat, signal_names=cols)

    mat = aligned[cols].corr(method="pearson")
    # Replace NaN with 0 for signals with zero variance
    mat = mat.fillna(0.0)

    return CorrelationMatrix(matrix=mat, signal_names=cols)
