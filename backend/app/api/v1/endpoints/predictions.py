"""
Prediction API endpoints.

Provides:
  POST /predictions/predict   – predict milestone duration(s)
  POST /predictions/train     – train or re-train the model
  GET  /predictions/status    – model health / metadata
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, status

from app.ml.persistence import load_model_metadata, model_exists
from app.ml.service import (
    bootstrap_model,
    predict_duration,
    reload_model,
    train_model,
)
from app.schemas.prediction import (
    MilestonePredictionOut,
    ModelStatusOut,
    PredictRequest,
    PredictResponse,
    TrainRequest,
    TrainResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# POST /predict
# ---------------------------------------------------------------------------
@router.post(
    "/predict",
    response_model=PredictResponse,
    summary="Predict milestone duration",
    description=(
        "Given one or more milestone feature vectors, return predicted duration "
        "(months) with 80 % confidence interval and optional SHAP explanations."
    ),
)
async def predict(req: PredictRequest) -> PredictResponse:
    if not model_exists():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "No trained model available. "
                "POST /predictions/train to train one first."
            ),
        )

    try:
        # Convert Pydantic models → dicts the ML pipeline understands
        raw_records = [m.model_dump() for m in req.milestones]

        results = predict_duration(
            raw_records,
            include_explanations=req.include_explanations,
            top_k=req.top_k,
        )

        predictions = [MilestonePredictionOut(**r) for r in results]
        return PredictResponse(predictions=predictions)

    except Exception as exc:
        logger.exception("Prediction failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Prediction error: {exc}",
        ) from exc


# ---------------------------------------------------------------------------
# POST /train
# ---------------------------------------------------------------------------
@router.post(
    "/train",
    response_model=TrainResponse,
    summary="Train or re-train the duration model",
    description=(
        "Supply training records or let the system generate synthetic data. "
        "Returns evaluation metrics and persists the model for future predictions."
    ),
)
async def train(req: TrainRequest) -> TrainResponse:
    try:
        if req.records:
            summary = train_model(
                req.records,
                test_size=req.test_size,
                version_tag=req.version_tag,
            )
        else:
            summary = bootstrap_model(
                n=req.n_synthetic,
                seed=42,
            )

        return TrainResponse(
            metrics=summary["metrics"],
            model_path=summary["model_path"],
            feature_importances=summary["feature_importances"],
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Training failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Training error: {exc}",
        ) from exc


# ---------------------------------------------------------------------------
# GET /status
# ---------------------------------------------------------------------------
@router.get(
    "/status",
    response_model=ModelStatusOut,
    summary="Model status & metadata",
    description="Check whether a trained model is loaded and view its metadata.",
)
async def get_status() -> ModelStatusOut:
    if not model_exists():
        return ModelStatusOut(model_loaded=False)

    meta = load_model_metadata()
    metrics_raw = meta.get("metrics")

    return ModelStatusOut(
        model_loaded=True,
        version=meta.get("version"),
        trained_at=meta.get("trained_at"),
        metrics=metrics_raw if metrics_raw else None,
        feature_names=meta.get("feature_names"),
    )
