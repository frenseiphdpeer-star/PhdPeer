"""
Opportunity Matching Service – public entry-point for the API layer.

Manages model lifecycle, synthetic data generation, and exposes
high-level functions for matching, training, and bootstrapping.

Provides:
  * ``match_opportunities()``   – score multiple opportunities for a researcher
  * ``train_model()``           – train the ranking model
  * ``bootstrap_model()``       – train on synthetic data for quick start
  * ``get_model_status()``      – report model metadata
  * ``generate_synthetic_dataset()`` – deterministic dataset
"""

from __future__ import annotations

import logging
import random as _random
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from app.ml.opportunity_matching.config import (
    ALL_FEATURES,
    DISCIPLINES,
    SCORING,
    STAGE_TYPES,
)
from app.ml.opportunity_matching.features import MatchRecord

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Match
# ---------------------------------------------------------------------------

def match_opportunities(
    records: Sequence[MatchRecord],
    *,
    _bundle: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Score researcher ↔ opportunity pairs and return enriched results
    with preparation recommendations.
    """
    from app.ml.opportunity_matching.scorer import score_matches

    results = score_matches(records, _bundle=_bundle)
    return [r.to_dict() for r in results]


def match_from_texts(
    researcher_text: str,
    opportunity_texts: List[str],
    *,
    records: Sequence[MatchRecord],
    _bundle: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Embed texts, compute similarity, score, and return preparation recs.
    """
    from app.ml.opportunity_matching.scorer import score_from_texts

    results = score_from_texts(
        researcher_text,
        opportunity_texts,
        records=records,
        _bundle=_bundle,
    )
    return [r.to_dict() for r in results]


# ---------------------------------------------------------------------------
# Train
# ---------------------------------------------------------------------------

def train_model(
    records: Sequence[MatchRecord],
    *,
    save: bool = True,
) -> Dict[str, Any]:
    """Train the ranking model and return evaluation metrics."""
    from app.ml.opportunity_matching.model import train

    result = train(records, save=save)
    return result.to_dict()


def bootstrap_model(
    n: int = 500,
    *,
    save: bool = True,
) -> Dict[str, Any]:
    """Train on a synthetic dataset for quick-start / demo."""
    records = generate_synthetic_dataset(n=n)
    return train_model(records, save=save)


# ---------------------------------------------------------------------------
# Model status
# ---------------------------------------------------------------------------

def get_model_status() -> Dict[str, Any]:
    """Return metadata about the current trained model."""
    from app.ml.opportunity_matching import config as _cfg
    import json

    meta_path = _cfg.MATCHING_ARTIFACTS_DIR / _cfg.METADATA_FILENAME
    if meta_path.exists():
        with open(meta_path) as f:
            meta = json.load(f)
        return {"loaded": True, **meta}
    return {"loaded": False}


# ---------------------------------------------------------------------------
# Synthetic data generation
# ---------------------------------------------------------------------------

def generate_synthetic_dataset(
    n: int = 500,
    seed: int = 42,
) -> List[MatchRecord]:
    """
    Generate *n* synthetic researcher ↔ opportunity match records with
    realistic correlations between features and the acceptance label.

    High cosine similarity, strong prior success, matching discipline,
    and shorter deadlines correlate with acceptance.
    """
    rng = np.random.RandomState(seed)
    py_rng = _random.Random(seed)

    records: List[MatchRecord] = []

    for _ in range(n):
        # Latent quality factor
        quality = rng.beta(2, 3)  # skewed toward lower quality

        # Cosine similarity (higher quality → higher sim)
        cos_sim = float(np.clip(
            rng.normal(0.3 + quality * 0.5, 0.12),
            0.0, 1.0,
        ))

        # Stage and discipline
        stage = py_rng.choice(STAGE_TYPES)
        res_disc = py_rng.choice(DISCIPLINES)
        # Discipline match more likely for higher quality
        if rng.random() < 0.5 + quality * 0.35:
            opp_disc = res_disc
        else:
            opp_disc = py_rng.choice(DISCIPLINES)

        # Prior success
        success_rate = float(np.clip(
            rng.beta(2 + quality * 5, 3),
            0.0, 1.0,
        ))
        app_count = int(np.clip(rng.poisson(max(1, 3 + quality * 8)), 0, 30))

        # Timeline readiness
        timeline = float(np.clip(
            rng.normal(0.4 + quality * 0.4, 0.15),
            0.0, 1.0,
        ))

        # Days to deadline
        days = float(np.clip(
            rng.exponential(60) + 5,
            1.0, 365.0,
        ))

        # Acceptance label (noisy logistic of quality + signals)
        logit = (
            quality * 3.0
            + cos_sim * 2.0
            + success_rate * 1.5
            + (1.0 if res_disc == opp_disc else 0.0) * 0.5
            + timeline * 1.0
            - 3.5
            + rng.normal(0, 0.5)
        )
        prob = 1.0 / (1.0 + np.exp(-logit))
        accepted = int(rng.random() < prob)

        records.append(MatchRecord(
            cosine_similarity=round(cos_sim, 4),
            stage_type=stage,
            researcher_discipline=res_disc,
            opportunity_discipline=opp_disc,
            prior_success_rate=round(success_rate, 4),
            prior_application_count=app_count,
            timeline_readiness_score=round(timeline, 4),
            days_to_deadline=round(days, 1),
            accepted=accepted,
        ))

    pos = sum(1 for r in records if r.accepted == 1)
    logger.info(
        "Generated %d synthetic match records (%.1f%% accepted)",
        n,
        100 * pos / n,
    )
    return records
