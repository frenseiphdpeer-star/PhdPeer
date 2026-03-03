"""
REST endpoints for Dropout Risk Prediction.

Routes
------
POST /predict           – predict dropout risk for student snapshots
POST /explain           – predict with SHAP explanations
POST /train             – train models on labelled data
POST /bootstrap         – train on synthetic data (quick start)
GET  /status            – model metadata
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from app.ml.dropout_risk.features import RawDropoutRecord
from app.schemas.dropout_risk import (
    BootstrapRequest,
    ClassificationMetricsOut,
    ExplainRequest,
    ExplainResponse,
    ExplanationOut,
    ModelStatusOut,
    PredictRequest,
    PredictResponse,
    PredictionOut,
    RiskFactorOut,
    StudentSnapshot,
    TrainRequest,
    TrainResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _snapshot_to_record(s: StudentSnapshot) -> RawDropoutRecord:
    """Convert a Pydantic StudentSnapshot into a RawDropoutRecord."""
    return RawDropoutRecord(
        supervision_latency_avg=s.supervision_latency_avg,
        supervision_gap_max=s.supervision_gap_max,
        milestone_delay_ratio=s.milestone_delay_ratio,
        health_score_decline_slope=s.health_score_decline_slope,
        opportunity_engagement_count=s.opportunity_engagement_count,
        writing_coherence_trend=s.writing_coherence_trend,
        revision_response_rate=s.revision_response_rate,
        peer_connection_count=s.peer_connection_count,
        health_score_history=s.health_score_history,
        engagement_history=s.engagement_history,
        weeks_since_last_supervision=s.weeks_since_last_supervision,
    )


def _dict_to_record(d: Dict[str, Any]) -> RawDropoutRecord:
    """Convert a raw dict (from training payload) into a RawDropoutRecord."""
    return RawDropoutRecord(
        supervision_latency_avg=d.get("supervision_latency_avg"),
        supervision_gap_max=d.get("supervision_gap_max"),
        milestone_delay_ratio=d.get("milestone_delay_ratio"),
        health_score_decline_slope=d.get("health_score_decline_slope"),
        opportunity_engagement_count=d.get("opportunity_engagement_count"),
        writing_coherence_trend=d.get("writing_coherence_trend"),
        revision_response_rate=d.get("revision_response_rate"),
        peer_connection_count=d.get("peer_connection_count"),
        dropout=d.get("dropout"),
        health_score_history=d.get("health_score_history"),
        engagement_history=d.get("engagement_history"),
        weeks_since_last_supervision=d.get("weeks_since_last_supervision"),
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/predict", response_model=PredictResponse)
async def predict_dropout(req: PredictRequest):
    """Predict dropout risk for one or more student snapshots."""
    from app.ml.dropout_risk import service

    records = [_snapshot_to_record(s) for s in req.students]
    try:
        results = service.predict_risk(records, model=req.model)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    return PredictResponse(
        predictions=[PredictionOut(**r) for r in results]
    )


@router.post("/explain", response_model=ExplainResponse)
async def explain_dropout(req: ExplainRequest):
    """Predict dropout risk with SHAP-based explanations."""
    from app.ml.dropout_risk import service

    records = [_snapshot_to_record(s) for s in req.students]
    try:
        results = service.explain_risk(records, model=req.model, top_n=req.top_n)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    explanations = []
    for r in results:
        factors = [
            RiskFactorOut(**f) for f in r["top_risk_factors"]
        ]
        explanations.append(ExplanationOut(
            base_probability=r["base_probability"],
            predicted_probability=r["predicted_probability"],
            risk_category=r["risk_category"],
            top_risk_factors=factors,
        ))
    return ExplainResponse(explanations=explanations)


@router.post("/train", response_model=TrainResponse)
async def train_models(req: TrainRequest):
    """Train dropout models on labelled data."""
    from app.ml.dropout_risk import service

    records = [_dict_to_record(d) for d in req.records]
    result = service.train_model(records, save=True)
    return TrainResponse(**result)


@router.post("/bootstrap", response_model=TrainResponse)
async def bootstrap_models(req: BootstrapRequest):
    """Bootstrap training on synthetic data."""
    from app.ml.dropout_risk import service

    result = service.bootstrap_model(n=req.n, save=False)
    return TrainResponse(**result)


@router.get("/status", response_model=ModelStatusOut)
async def model_status():
    """Return metadata about the current trained dropout model."""
    from app.ml.dropout_risk import service

    status = service.get_model_status()
    if not status.get("loaded"):
        return ModelStatusOut(loaded=False)
    return ModelStatusOut(
        loaded=True,
        lr_metrics=ClassificationMetricsOut(**status.get("lr_metrics", {})) if status.get("lr_metrics") else None,
        xgb_metrics=ClassificationMetricsOut(**status.get("xgb_metrics", {})) if status.get("xgb_metrics") else None,
        n_samples=status.get("n_samples"),
        n_features=status.get("n_features"),
    )
