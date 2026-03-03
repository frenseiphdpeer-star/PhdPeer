"""
Model persistence – save / load model artefacts.

Artefacts stored per model version:
  - ``milestone_duration_model.joblib``  – fitted LightGBM model bundle
  - ``milestone_duration_metadata.json`` – training metadata (date, metrics, params)

The *bundle* is a dict::

    {
        "model": fitted LGBMRegressor (point estimate),
        "model_lower": fitted LGBMRegressor (lower quantile),
        "model_upper": fitted LGBMRegressor (upper quantile),
        "feature_engineer_state": dict from FeatureEngineer.get_state(),
        "feature_names": list[str],
    }
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import joblib

from app.ml.config import METADATA_FILENAME, MODEL_DIR, MODEL_FILENAME

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------

def save_model_bundle(
    bundle: Dict[str, Any],
    metrics: Dict[str, float],
    params: Dict[str, Any],
    version_tag: Optional[str] = None,
) -> Path:
    """
    Persist a trained model bundle + metadata to ``MODEL_DIR``.

    Parameters
    ----------
    bundle : dict
        Must contain keys ``model``, ``model_lower``, ``model_upper``,
        ``feature_engineer_state``, ``feature_names``.
    metrics : dict
        Evaluation metrics (e.g. MAE, RMSE).
    params : dict
        Hyper-parameter dict used for training.
    version_tag : str, optional
        Human-readable version label (default: ISO timestamp).

    Returns
    -------
    Path to the saved model file.
    """
    model_path = MODEL_DIR / MODEL_FILENAME
    metadata_path = MODEL_DIR / METADATA_FILENAME

    joblib.dump(bundle, model_path)
    logger.info("Model bundle saved → %s", model_path)

    metadata = {
        "version": version_tag or datetime.now(timezone.utc).isoformat(),
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "metrics": metrics,
        "params": params,
        "feature_names": bundle.get("feature_names", []),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2))
    logger.info("Metadata saved → %s", metadata_path)

    return model_path


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------

def load_model_bundle() -> Dict[str, Any]:
    """
    Load the latest model bundle from ``MODEL_DIR``.

    Returns
    -------
    dict  with keys ``model``, ``model_lower``, ``model_upper``,
    ``feature_engineer_state``, ``feature_names``.

    Raises
    ------
    FileNotFoundError
        If no model has been trained yet.
    """
    model_path = MODEL_DIR / MODEL_FILENAME
    if not model_path.exists():
        raise FileNotFoundError(
            f"No trained model found at {model_path}. "
            "Run the training pipeline first."
        )
    bundle: Dict[str, Any] = joblib.load(model_path)
    logger.info("Model bundle loaded ← %s", model_path)
    return bundle


def load_model_metadata() -> Dict[str, Any]:
    """Load training metadata JSON."""
    metadata_path = MODEL_DIR / METADATA_FILENAME
    if not metadata_path.exists():
        return {}
    return json.loads(metadata_path.read_text())


def model_exists() -> bool:
    """Return ``True`` if a persisted model exists."""
    return (MODEL_DIR / MODEL_FILENAME).exists()
