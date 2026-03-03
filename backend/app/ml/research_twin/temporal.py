"""
Temporal feature engineering for the AI Research Twin.

Converts raw timestamped behavioural events into fixed-size temporal
feature vectors suitable for LSTM ingestion.

Pipeline
--------
1. Parse events into (timestamp, event_type) records.
2. Bin into hourly buckets → event-rate per channel.
3. Add **cyclic time encodings** (hour-of-day sin/cos, day-of-week sin/cos).
4. Apply rolling-mean smoothing.
5. Slice into overlapping sequences of length ``seq_length``.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from app.ml.research_twin.config import (
    EVENT_TYPES,
    FEATURE_CHANNELS,
    SEQ_CFG,
    TEMPORAL_CFG,
    SequenceConfig,
    TemporalFeatureConfig,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Input record
# ---------------------------------------------------------------------------

@dataclass
class BehaviourEvent:
    """A single timestamped behavioural event."""

    timestamp: str              # ISO-8601
    event_type: str             # must be in EVENT_TYPES
    researcher_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Event → hourly rate matrix
# ---------------------------------------------------------------------------

_EVENT_TO_CHANNEL = {
    "writing": "writing_rate",
    "revision": "revision_density",
    "opportunity_engagement": "engagement_rate",
    "submission": "submission_rate",
    "supervision": "supervision_rate",
}


def events_to_hourly_rates(
    events: Sequence[BehaviourEvent],
    *,
    cfg: TemporalFeatureConfig | None = None,
) -> pd.DataFrame:
    """
    Aggregate raw events into hourly event-rate columns.

    Returns a DataFrame indexed by hourly ``DatetimeIndex`` with one
    column per ``FEATURE_CHANNELS`` entry.
    """
    c = cfg or TEMPORAL_CFG

    if not events:
        return pd.DataFrame(columns=FEATURE_CHANNELS)

    rows: List[Dict[str, Any]] = []
    for ev in events:
        if ev.event_type not in EVENT_TYPES:
            logger.warning("Unknown event type '%s' – skipping", ev.event_type)
            continue
        rows.append({
            "timestamp": pd.Timestamp(ev.timestamp),
            "channel": _EVENT_TO_CHANNEL[ev.event_type],
        })

    if not rows:
        return pd.DataFrame(columns=FEATURE_CHANNELS)

    long = pd.DataFrame(rows)
    long["value"] = 1.0

    # Pivot to wide form
    wide = long.pivot_table(
        index="timestamp",
        columns="channel",
        values="value",
        aggfunc="sum",
    )

    # Ensure all channels present
    for ch in FEATURE_CHANNELS:
        if ch not in wide.columns:
            wide[ch] = 0.0
    wide = wide[FEATURE_CHANNELS]

    # Resample to hourly bins
    freq = f"{c.bin_hours}h"
    wide = wide.resample(freq).sum().fillna(0.0)

    return wide


# ---------------------------------------------------------------------------
# Cyclic time encodings
# ---------------------------------------------------------------------------

def add_cyclic_encodings(df: pd.DataFrame) -> pd.DataFrame:
    """
    Append four cyclic encoding columns:
      hour_sin, hour_cos, dow_sin, dow_cos

    Uses sin/cos to preserve circularity of hour-of-day and day-of-week.
    """
    idx = df.index
    hours = np.array([t.hour for t in idx], dtype=np.float64)
    dows = np.array([t.dayofweek for t in idx], dtype=np.float64)

    out = df.copy()
    out["hour_sin"] = np.sin(2 * math.pi * hours / 24.0)
    out["hour_cos"] = np.cos(2 * math.pi * hours / 24.0)
    out["dow_sin"] = np.sin(2 * math.pi * dows / 7.0)
    out["dow_cos"] = np.cos(2 * math.pi * dows / 7.0)

    return out


# ---------------------------------------------------------------------------
# Rolling smoothing
# ---------------------------------------------------------------------------

def apply_rolling_smooth(
    df: pd.DataFrame,
    *,
    window: int | None = None,
) -> pd.DataFrame:
    """
    Apply rolling-mean smoothing to the event-rate channels only
    (cyclic encodings are left untouched).
    """
    w = window or TEMPORAL_CFG.rolling_window
    rate_cols = [c for c in FEATURE_CHANNELS if c in df.columns]
    other_cols = [c for c in df.columns if c not in rate_cols]

    smoothed = df[rate_cols].rolling(window=w, min_periods=1).mean()
    return pd.concat([smoothed, df[other_cols]], axis=1)


# ---------------------------------------------------------------------------
# Build full temporal feature matrix
# ---------------------------------------------------------------------------

def build_temporal_features(
    events: Sequence[BehaviourEvent],
    *,
    cfg: TemporalFeatureConfig | None = None,
) -> pd.DataFrame:
    """
    Full pipeline: events → hourly rates → cyclic encodings → smoothing.

    Returns a DataFrame with ``len(FEATURE_CHANNELS) + 4`` columns.
    """
    rates = events_to_hourly_rates(events, cfg=cfg)
    if rates.empty:
        return rates

    with_cyclic = add_cyclic_encodings(rates)
    smoothed = apply_rolling_smooth(with_cyclic)

    logger.info(
        "Built temporal features: %d hours × %d channels",
        len(smoothed),
        smoothed.shape[1],
    )
    return smoothed


# ---------------------------------------------------------------------------
# Sequence slicing
# ---------------------------------------------------------------------------

def slice_sequences(
    features: pd.DataFrame,
    *,
    seq_cfg: SequenceConfig | None = None,
) -> np.ndarray:
    """
    Slice the temporal feature matrix into overlapping windows for
    LSTM training / inference.

    Returns
    -------
    np.ndarray  shape (N, seq_length, n_features)
    """
    sc = seq_cfg or SEQ_CFG

    vals = features.values.astype(np.float32)
    n_rows, n_feat = vals.shape

    if n_rows < sc.seq_length:
        # Pad with zeros at the front
        pad = np.zeros((sc.seq_length - n_rows, n_feat), dtype=np.float32)
        vals = np.vstack([pad, vals])
        return vals[np.newaxis, :, :]  # single sequence

    sequences: List[np.ndarray] = []
    for start in range(0, n_rows - sc.seq_length + 1, sc.stride):
        sequences.append(vals[start : start + sc.seq_length])

    return np.array(sequences, dtype=np.float32)


# ---------------------------------------------------------------------------
# Multi-researcher helper
# ---------------------------------------------------------------------------

def build_multi_researcher(
    events: Sequence[BehaviourEvent],
    *,
    cfg: TemporalFeatureConfig | None = None,
) -> Dict[str, pd.DataFrame]:
    """Build per-researcher temporal feature matrices."""
    by_rid: Dict[str, List[BehaviourEvent]] = {}
    for ev in events:
        rid = ev.researcher_id or "__default__"
        by_rid.setdefault(rid, []).append(ev)

    result: Dict[str, pd.DataFrame] = {}
    for rid, evts in by_rid.items():
        df = build_temporal_features(evts, cfg=cfg)
        if not df.empty:
            result[rid] = df
    return result
