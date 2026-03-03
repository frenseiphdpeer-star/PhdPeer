"""
Temporal signal alignment for the Cross-Feature Fusion Engine.

Accepts raw timestamped observations from heterogeneous sources
(supervisor logs, writing scores, health snapshots, etc.) and
produces a single, time-aligned DataFrame where every recognised
signal occupies one column and rows are regular time periods.

Steps
-----
1. Parse each observation into (timestamp, signal_name, value).
2. Pivot into a wide DataFrame indexed by timestamp.
3. Resample to a regular cadence (default: weekly).
4. Forward-fill gaps (with configurable limit).
5. Drop rows with insufficient signal coverage.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from app.ml.fusion_engine.config import SIGNAL_NAMES, TARGET_NAMES, TEMPORAL, TemporalConfig

logger = logging.getLogger(__name__)

# All recognised column names (signals + targets)
_ALL_KNOWN_NAMES = set(SIGNAL_NAMES) | set(TARGET_NAMES)


# ---------------------------------------------------------------------------
# Input record
# ---------------------------------------------------------------------------

@dataclass
class SignalObservation:
    """A single timestamped observation of one signal."""

    timestamp: str                # ISO-8601 datetime string
    signal_name: str              # must be in SIGNAL_NAMES
    value: float
    researcher_id: Optional[str] = None  # for multi-researcher datasets
    metadata: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Alignment
# ---------------------------------------------------------------------------

def align_signals(
    observations: Sequence[SignalObservation],
    *,
    config: TemporalConfig | None = None,
    min_coverage: float = 0.3,
) -> pd.DataFrame:
    """
    Align heterogeneous signal observations into a regular time-series.

    Parameters
    ----------
    observations : sequence of SignalObservation
        Raw timestamped data from any PhdPeer module.
    config : TemporalConfig, optional
        Temporal alignment parameters (default from module config).
    min_coverage : float
        Minimum fraction of non-null signals required for a row to be kept.

    Returns
    -------
    pd.DataFrame
        Index = DatetimeIndex (regular periods).
        Columns = recognised signal names that have at least one observation.
    """
    cfg = config or TEMPORAL

    if not observations:
        return pd.DataFrame()

    # ── Build long-form DataFrame ─────────────────────────────────────
    rows = []
    for obs in observations:
        if obs.signal_name not in _ALL_KNOWN_NAMES:
            logger.warning("Unknown signal '%s' – skipping", obs.signal_name)
            continue
        rows.append({
            "timestamp": pd.Timestamp(obs.timestamp),
            "signal": obs.signal_name,
            "value": obs.value,
        })

    if not rows:
        return pd.DataFrame()

    long = pd.DataFrame(rows)

    # ── Pivot to wide form ────────────────────────────────────────────
    wide = long.pivot_table(
        index="timestamp",
        columns="signal",
        values="value",
        aggfunc=cfg.aggregation,
    )
    wide.sort_index(inplace=True)

    # ── Resample to regular cadence ───────────────────────────────────
    wide = wide.resample(cfg.resample_period).agg(cfg.aggregation)

    # ── Forward-fill gaps ─────────────────────────────────────────────
    wide = wide.ffill(limit=cfg.ffill_limit)

    # ── Drop rows with too few signals ────────────────────────────────
    present = wide.columns.tolist()
    threshold = int(max(1, min_coverage * len(present)))
    wide = wide.dropna(thresh=threshold)

    logger.info(
        "Aligned %d observations → %d periods × %d signals",
        len(observations),
        len(wide),
        len(present),
    )

    return wide


def align_multi_researcher(
    observations: Sequence[SignalObservation],
    *,
    config: TemporalConfig | None = None,
    min_coverage: float = 0.3,
) -> Dict[str, pd.DataFrame]:
    """
    Align signals per researcher, returning a dict of DataFrames.
    """
    by_researcher: Dict[str, List[SignalObservation]] = {}
    for obs in observations:
        rid = obs.researcher_id or "__default__"
        by_researcher.setdefault(rid, []).append(obs)

    results: Dict[str, pd.DataFrame] = {}
    for rid, obs_list in by_researcher.items():
        df = align_signals(obs_list, config=config, min_coverage=min_coverage)
        if not df.empty:
            results[rid] = df

    return results
