"""
Research Twin Service – public entry-point for the API layer.

Provides:
  * ``analyse()``                     – full twin from raw events
  * ``analyse_researcher()``          – single-researcher analysis
  * ``generate_synthetic_events()``   – deterministic synthetic data
  * ``get_model_status()``            – LSTM model availability
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from app.ml.research_twin import config as _cfg
from app.ml.research_twin.config import (
    EVENT_TYPES,
    LSTM_FILENAME,
)
from app.ml.research_twin.scorer import (
    TwinAnalysis,
    analyse as _analyse,
    analyse_single as _analyse_single,
)
from app.ml.research_twin.temporal import BehaviourEvent

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Full analysis
# ---------------------------------------------------------------------------

def analyse(
    events: Sequence[BehaviourEvent],
    *,
    save_model: bool = True,
) -> Dict[str, Any]:
    """Run full Research Twin pipeline and return serialisable dict."""
    result = _analyse(events, save_model=save_model)
    return result.to_dict()


def analyse_researcher(
    events: Sequence[BehaviourEvent],
    researcher_id: str,
    *,
    save_model: bool = True,
) -> Dict[str, Any]:
    """Analyse and return recommendation for one researcher."""
    rec = _analyse_single(
        events, researcher_id, save_model=save_model,
    )
    if rec is None:
        return {"error": f"Researcher '{researcher_id}' not found in events."}
    return rec.to_dict()


# ---------------------------------------------------------------------------
# Model status
# ---------------------------------------------------------------------------

def get_model_status() -> Dict[str, Any]:
    """Check whether a trained LSTM model exists on disk."""
    model_path = _cfg.TWIN_ARTIFACTS_DIR / LSTM_FILENAME
    return {
        "model_trained": model_path.exists(),
        "model_path": str(model_path),
        "artifacts_dir": str(_cfg.TWIN_ARTIFACTS_DIR),
    }


# ---------------------------------------------------------------------------
# Synthetic data generation
# ---------------------------------------------------------------------------

def generate_synthetic_events(
    n_researchers: int = 3,
    n_days: int = 30,
    seed: int = 42,
) -> Dict[str, Any]:
    """
    Generate synthetic behavioural events with realistic temporal
    patterns (more writing during work hours, revisions in evenings,
    submissions near deadlines, etc.).

    Returns dict with ``events``, ``researcher_ids``, ``metadata``.
    """
    rng = np.random.RandomState(seed)

    researcher_ids = [f"R{i:03d}" for i in range(n_researchers)]
    start = pd.Timestamp("2023-01-01")

    events: List[BehaviourEvent] = []

    for rid in researcher_ids:
        # Each researcher gets a slightly different productivity profile
        peak_hour = rng.randint(8, 16)  # peak productivity hour
        activity_level = rng.uniform(0.3, 1.0)

        for day in range(n_days):
            dt = start + pd.Timedelta(days=day)
            dow = dt.dayofweek  # 0=Mon

            # Fewer events on weekends
            day_scale = 0.3 if dow >= 5 else 1.0

            for hour in range(24):
                ts = (dt + pd.Timedelta(hours=hour)).isoformat()

                # Hour-based probability curve (Gaussian around peak)
                hour_prob = np.exp(
                    -0.5 * ((hour - peak_hour) / 3.0) ** 2
                ) * activity_level * day_scale

                # Writing events
                if rng.random() < hour_prob * 0.6:
                    events.append(BehaviourEvent(
                        timestamp=ts,
                        event_type="writing",
                        researcher_id=rid,
                    ))

                # Revision events (slightly shifted)
                if rng.random() < hour_prob * 0.4:
                    events.append(BehaviourEvent(
                        timestamp=ts,
                        event_type="revision",
                        researcher_id=rid,
                    ))

                # Opportunity engagement (lower freq)
                if rng.random() < hour_prob * 0.1:
                    events.append(BehaviourEvent(
                        timestamp=ts,
                        event_type="opportunity_engagement",
                        researcher_id=rid,
                    ))

                # Supervision (work hours only, very rare)
                if 9 <= hour <= 17 and rng.random() < 0.02 * day_scale:
                    events.append(BehaviourEvent(
                        timestamp=ts,
                        event_type="supervision",
                        researcher_id=rid,
                    ))

            # Submission events (weekly-ish, near end of day)
            if rng.random() < 0.15 * day_scale:
                sub_hour = rng.choice([15, 16, 17, 18, 23])
                ts = (dt + pd.Timedelta(hours=sub_hour)).isoformat()
                events.append(BehaviourEvent(
                    timestamp=ts,
                    event_type="submission",
                    researcher_id=rid,
                ))

    logger.info(
        "Generated synthetic events: %d researchers × %d days = %d events",
        n_researchers, n_days, len(events),
    )

    return {
        "events": events,
        "researcher_ids": researcher_ids,
        "n_days": n_days,
        "n_events": len(events),
        "seed": seed,
    }
