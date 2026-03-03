"""
Fusion Engine Service – public entry-point for the API layer.

Provides:
  * ``analyse()``                    – full fusion from raw observations
  * ``analyse_from_dataframe()``     – fusion from pre-aligned data
  * ``generate_synthetic_dataset()`` – deterministic synthetic signal data
  * ``get_model_status()``           – check trained-model availability
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from app.ml.fusion_engine import config as _cfg
from app.ml.fusion_engine.config import (
    MODEL_FILENAME,
    SIGNAL_NAMES,
    TARGET_NAMES,
)
from app.ml.fusion_engine.signals import SignalObservation
from app.ml.fusion_engine.scorer import (
    FusionAnalysis,
    analyse as _analyse,
    analyse_from_dataframe as _analyse_from_df,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Full analysis (from raw observations)
# ---------------------------------------------------------------------------

def analyse(
    observations: Sequence[SignalObservation],
    *,
    save_model: bool = True,
) -> Dict[str, Any]:
    """Run full fusion pipeline and return serialisable dict."""
    result = _analyse(observations, save_model=save_model)
    return result.to_dict()


# ---------------------------------------------------------------------------
# Analysis from pre-aligned DataFrame
# ---------------------------------------------------------------------------

def analyse_dataframe(
    df: pd.DataFrame,
    *,
    save_model: bool = True,
) -> Dict[str, Any]:
    """Run fusion pipeline from a pre-aligned DataFrame."""
    result = _analyse_from_df(df, save_model=save_model)
    return result.to_dict()


# ---------------------------------------------------------------------------
# Model status
# ---------------------------------------------------------------------------

def get_model_status() -> Dict[str, Any]:
    """Check whether a trained fusion model exists on disk."""
    model_path = _cfg.FUSION_ARTIFACTS_DIR / MODEL_FILENAME
    return {
        "model_trained": model_path.exists(),
        "model_path": str(model_path),
        "artifacts_dir": str(_cfg.FUSION_ARTIFACTS_DIR),
    }


# ---------------------------------------------------------------------------
# Synthetic data generation
# ---------------------------------------------------------------------------

def generate_synthetic_dataset(
    n_researchers: int = 5,
    n_weeks: int = 52,
    seed: int = 42,
) -> Dict[str, Any]:
    """
    Generate synthetic weekly signal observations for *n_researchers*
    over *n_weeks*.  Includes all base signals plus three target
    columns with realistic cross-correlations.

    Returns a dict with ``observations`` (list), ``researcher_ids``,
    and ``metadata``.
    """
    rng = np.random.RandomState(seed)

    researcher_ids = [f"R{i:03d}" for i in range(n_researchers)]
    start = pd.Timestamp("2023-01-01")

    observations: List[SignalObservation] = []

    for rid in researcher_ids:
        # Base trends (random walk)
        supervision = _random_walk(rng, n_weeks, start=5, lo=0, hi=30)
        writing     = _random_walk(rng, n_weeks, start=0.5, lo=0, hi=1)
        health      = _random_walk(rng, n_weeks, start=70, lo=0, hi=100)
        opportunity = _random_walk(rng, n_weeks, start=50, lo=0, hi=100)
        centrality  = _random_walk(rng, n_weeks, start=0.3, lo=0, hi=1)
        publication = _random_walk(rng, n_weeks, start=0.4, lo=0, hi=1)

        # Targets: derived with noise so they're somewhat predictable
        pub_success = np.clip(
            0.3 * writing + 0.3 * centrality + 0.2 * (1 - supervision / 30)
            + 0.2 * rng.randn(n_weeks) * 0.1,
            0, 1,
        )
        milestone_accel = (
            health / 100 * 10
            + writing * 5
            - supervision / 30 * 5
            + rng.randn(n_weeks) * 1.5
        )
        dropout = np.clip(
            0.4 * supervision / 30
            + 0.3 * (1 - health / 100)
            + 0.2 * (1 - writing)
            + 0.1 * rng.randn(n_weeks) * 0.15,
            0, 1,
        )

        signal_arrays = {
            "supervision_latency":   supervision,
            "writing_coherence":     writing,
            "health_score":          health,
            "opportunity_engagement": opportunity,
            "network_centrality":    centrality,
            "publication_acceptance": publication,
            # Targets
            "publication_success":   pub_success,
            "milestone_acceleration": milestone_accel,
            "dropout_risk":          dropout,
        }

        for week in range(n_weeks):
            ts = (start + pd.Timedelta(weeks=week)).isoformat()
            for sig_name, arr in signal_arrays.items():
                observations.append(SignalObservation(
                    timestamp=ts,
                    signal_name=sig_name,
                    value=float(arr[week]),
                    researcher_id=rid,
                ))

    logger.info(
        "Generated synthetic dataset: %d researchers × %d weeks = %d obs",
        n_researchers, n_weeks, len(observations),
    )

    return {
        "observations": observations,
        "researcher_ids": researcher_ids,
        "n_weeks": n_weeks,
        "n_observations": len(observations),
        "seed": seed,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _random_walk(
    rng: np.random.RandomState,
    n: int,
    *,
    start: float,
    lo: float,
    hi: float,
    step_std: float | None = None,
) -> np.ndarray:
    """Bounded random walk with Gaussian steps."""
    if step_std is None:
        step_std = (hi - lo) * 0.03

    arr = np.empty(n, dtype=np.float64)
    arr[0] = start
    for i in range(1, n):
        arr[i] = np.clip(arr[i - 1] + rng.randn() * step_std, lo, hi)
    return arr
