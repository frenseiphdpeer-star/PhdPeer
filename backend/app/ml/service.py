"""
High-level prediction service – the single entry-point consumed by the API layer.

Handles:
  * Lazy model loading (singleton, thread-safe via module-level cache).
  * Synthetic training-data generation for bootstrap / demo.
  * Orchestrates feature engineering → prediction → SHAP explanation.
  * Assembles the response contract expected by the API schema.
"""

from __future__ import annotations

import logging
import random
from typing import Any, Dict, List, Optional, Sequence, Union

from app.ml import explainability, model as ml_model
from app.ml.features import RawMilestoneRecord
from app.ml.persistence import load_model_bundle, model_exists

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Module-level model cache (loaded once, reused across requests)
# ---------------------------------------------------------------------------
_cached_bundle: Optional[Dict[str, Any]] = None


def _get_bundle() -> Dict[str, Any]:
    """Return the cached model bundle, loading from disk if needed."""
    global _cached_bundle
    if _cached_bundle is None:
        _cached_bundle = load_model_bundle()
    return _cached_bundle


def reload_model() -> None:
    """Force-reload the model from disk (e.g. after re-training)."""
    global _cached_bundle
    _cached_bundle = None
    _get_bundle()
    logger.info("Model cache reloaded.")


# ---------------------------------------------------------------------------
# Predict
# ---------------------------------------------------------------------------

def predict_duration(
    records: Sequence[Union[RawMilestoneRecord, Dict[str, Any]]],
    *,
    include_explanations: bool = True,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """
    Predict milestone duration with optional SHAP explanations.

    Parameters
    ----------
    records
        One or more milestone feature vectors.
    include_explanations
        Whether to run SHAP attribution (adds ~10-50 ms per row).
    top_k
        Number of top SHAP contributors to return.

    Returns
    -------
    list[dict]  – one dict per record with keys:
        ``predicted_duration_months``, ``ci_lower``, ``ci_upper``,
        and optionally ``explanation``.
    """
    bundle = _get_bundle()

    # --- Point + quantile predictions --------------------------------------
    predictions = ml_model.predict(records, bundle)

    # --- SHAP explanations -------------------------------------------------
    explanations: Optional[List] = None
    if include_explanations:
        explanations = explainability.explain(records, bundle, top_k=top_k)

    # --- Assemble response -------------------------------------------------
    results: List[Dict[str, Any]] = []
    for idx, pred in enumerate(predictions):
        entry: Dict[str, Any] = {
            "predicted_duration_months": pred.predicted_duration_months,
            "ci_lower": pred.ci_lower,
            "ci_upper": pred.ci_upper,
        }
        if explanations:
            entry["explanation"] = explanations[idx].to_dict()
        results.append(entry)

    return results


# ---------------------------------------------------------------------------
# Train  (delegates to ml_model.train, then refreshes cache)
# ---------------------------------------------------------------------------

def train_model(
    records: Sequence[Union[RawMilestoneRecord, Dict[str, Any]]],
    *,
    test_size: float = 0.2,
    version_tag: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Train (or re-train) the duration model.

    Returns a summary dict with metrics, path, and feature importances.
    """
    result = ml_model.train(records, test_size=test_size, version_tag=version_tag)
    reload_model()

    return {
        "metrics": result.metrics.to_dict(),
        "model_path": result.model_path,
        "feature_importances": result.feature_importances,
    }


# ---------------------------------------------------------------------------
# Synthetic data generator (for bootstrapping / demo / testing)
# ---------------------------------------------------------------------------

_STAGE_TYPES = [
    "literature_review", "methodology", "data_collection", "analysis",
    "writing", "defense_preparation", "revision", "publication",
    "coursework", "fieldwork",
]

_DISCIPLINES = [
    "computer_science", "biology", "physics", "chemistry", "psychology",
    "economics", "engineering", "mathematics", "medicine", "social_sciences",
    "humanities", "education", "environmental_science",
]

_MILESTONE_TYPES = [
    "paper", "presentation", "dataset", "code", "thesis_chapter",
    "proposal", "review", "report", "defense",
]


def _generate_synthetic_record(rng: random.Random) -> Dict[str, Any]:
    """Generate one plausible synthetic training record."""
    stage = rng.choice(_STAGE_TYPES)
    discipline = rng.choice(_DISCIPLINES)
    milestone_type = rng.choice(_MILESTONE_TYPES)
    n_prior = rng.randint(0, 20)

    supervision_latency = rng.uniform(1.0, 30.0)
    writing_velocity = rng.uniform(0.1, 1.0)
    engagement = rng.uniform(0.0, 1.0)
    health_trajectory = rng.uniform(0.3, 1.0)
    revision_density = rng.uniform(0.0, 5.0)
    prior_delays = [rng.random() > 0.65 for _ in range(max(n_prior, 1))]
    historical = rng.uniform(1.0, 18.0) if rng.random() > 0.3 else None

    # Simulate a realistic duration influenced by features
    base_duration = {
        "literature_review": 4, "methodology": 5, "data_collection": 8,
        "analysis": 6, "writing": 7, "defense_preparation": 3,
        "revision": 2, "publication": 4, "coursework": 6, "fieldwork": 10,
    }.get(stage, 5)

    noise = rng.gauss(0, 1.2)
    delay_penalty = sum(prior_delays) * 0.3
    velocity_bonus = (1.0 - writing_velocity) * 2
    latency_penalty = supervision_latency * 0.05
    health_bonus = (1.0 - health_trajectory) * 1.5

    actual = max(
        0.5,
        base_duration + delay_penalty + velocity_bonus
        + latency_penalty + health_bonus + noise,
    )

    return {
        "stage_type": stage,
        "discipline": discipline,
        "milestone_type": milestone_type,
        "number_of_prior_milestones": n_prior,
        "supervision_latency_avg": round(supervision_latency, 2),
        "writing_velocity_score": round(writing_velocity, 3),
        "prior_delay_patterns": prior_delays,
        "opportunity_engagement_score": round(engagement, 3),
        "health_score_trajectory": round(health_trajectory, 3),
        "revision_density": round(revision_density, 3),
        "historical_completion_time": round(historical, 2) if historical else None,
        "actual_duration_months": round(actual, 2),
    }


def generate_synthetic_dataset(n: int = 500, seed: int = 42) -> List[Dict[str, Any]]:
    """Return *n* synthetic training records (deterministic for given seed)."""
    rng = random.Random(seed)
    return [_generate_synthetic_record(rng) for _ in range(n)]


def bootstrap_model(n: int = 500, seed: int = 42) -> Dict[str, Any]:
    """Generate synthetic data, train, and return training summary."""
    data = generate_synthetic_dataset(n=n, seed=seed)
    return train_model(data, version_tag=f"bootstrap-{n}-seed{seed}")
