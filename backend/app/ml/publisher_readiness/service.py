"""
Publisher Readiness Service – public entry-point for the API layer.

Provides:
  * ``analyse()``                     – train + score from raw records
  * ``score()``                       – score with pre-trained model
  * ``get_model_status()``            – check artefact availability
  * ``generate_synthetic_dataset()``  – deterministic data for demos
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from app.ml.publisher_readiness import config as _cfg
from app.ml.publisher_readiness.config import (
    ALL_FEATURES,
    METADATA_FILENAME,
    MODEL_FILENAME,
    RAW_FEATURES,
)
from app.ml.publisher_readiness.features import RawReadinessRecord
from app.ml.publisher_readiness.scorer import (
    ReadinessAnalysis,
    analyse as _analyse,
    score_only as _score_only,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Full analysis (train + predict)
# ---------------------------------------------------------------------------

def analyse(
    records: Sequence[RawReadinessRecord],
    *,
    save_model: bool = True,
) -> Dict[str, Any]:
    """Run the full Publisher Readiness pipeline and return a dict."""
    result = _analyse(records, save_model=save_model)
    return result.to_dict()


# ---------------------------------------------------------------------------
# Score only (pre-trained model)
# ---------------------------------------------------------------------------

def score(
    records: Sequence[RawReadinessRecord],
) -> List[Dict[str, Any]]:
    """Score records with an already-trained model."""
    preds = _score_only(records)
    return [p.to_dict() for p in preds]


# ---------------------------------------------------------------------------
# Model status
# ---------------------------------------------------------------------------

def get_model_status() -> Dict[str, Any]:
    """Check whether a trained readiness model exists on disk."""
    model_path = _cfg.READINESS_ARTIFACTS_DIR / MODEL_FILENAME
    meta_path = _cfg.READINESS_ARTIFACTS_DIR / METADATA_FILENAME

    status: Dict[str, Any] = {
        "model_trained": model_path.exists(),
        "model_path": str(model_path),
        "artifacts_dir": str(_cfg.READINESS_ARTIFACTS_DIR),
    }

    if meta_path.exists():
        try:
            status["metadata"] = json.loads(meta_path.read_text())
        except Exception:
            pass

    return status


# ---------------------------------------------------------------------------
# Synthetic data generation
# ---------------------------------------------------------------------------

def generate_synthetic_dataset(
    n: int = 200,
    seed: int = 42,
) -> List[RawReadinessRecord]:
    """
    Generate a deterministic synthetic dataset for demos / testing.

    The acceptance_outcome is derived from a noisy linear combination
    of the six input signals so the model has a learnable target.
    """
    rng = np.random.RandomState(seed)

    records: List[RawReadinessRecord] = []

    for i in range(n):
        coherence = rng.beta(5, 2)            # skewed high 0–1
        novelty = rng.beta(4, 3)              # moderate 0–1
        supervision = rng.beta(3, 2)          # moderate-high 0–1
        revision = rng.exponential(3.0)       # unbounded count
        citation = rng.beta(4, 2)             # moderate-high 0–1
        stage = rng.beta(3, 3)                # symmetric 0–1

        # Noisy linear target (0–100 scale)
        signal = (
            20 * coherence
            + 15 * novelty
            + 10 * supervision
            + 10 * min(revision / 10.0, 1.0)  # cap contribution
            + 15 * citation
            + 20 * stage
            + rng.normal(0, 5)                 # noise
        )
        acceptance = float(np.clip(signal, 0, 100))

        records.append(RawReadinessRecord(
            coherence_score=coherence,
            novelty_score=novelty,
            supervision_quality_score=supervision,
            revision_density=revision,
            citation_consistency=citation,
            stage_completion_ratio=stage,
            acceptance_outcome=acceptance,
            researcher_id=f"R{i:03d}",
        ))

    logger.info("Generated %d synthetic readiness records (seed=%d)", n, seed)
    return records
