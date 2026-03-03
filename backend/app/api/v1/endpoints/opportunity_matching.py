"""
REST endpoints for Opportunity Matching.

Routes
------
POST /match             – match researcher with opportunities
POST /train             – train the ranking model on historical data
POST /bootstrap         – train on synthetic data (quick start)
GET  /status            – model metadata
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

from app.ml.opportunity_matching.features import MatchRecord
from app.schemas.opportunity_matching import (
    BootstrapRequest,
    MatchRequest,
    MatchResponse,
    MatchResultOut,
    MetricsOut,
    ModelStatusOut,
    PreparationOut,
    RecommendationOut,
    TrainRequest,
    TrainResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _input_to_record(opp) -> MatchRecord:
    """Convert an OpportunityInput schema to a MatchRecord."""
    return MatchRecord(
        cosine_similarity=opp.cosine_similarity,
        stage_type=opp.stage_type,
        researcher_discipline=opp.researcher_discipline,
        opportunity_discipline=opp.opportunity_discipline,
        prior_success_rate=opp.prior_success_rate,
        prior_application_count=opp.prior_application_count,
        timeline_readiness_score=opp.timeline_readiness_score,
        days_to_deadline=opp.days_to_deadline,
    )


def _train_record_to_match(tr) -> MatchRecord:
    """Convert a TrainRecord schema to a MatchRecord (with label)."""
    return MatchRecord(
        cosine_similarity=tr.cosine_similarity,
        stage_type=tr.stage_type,
        researcher_discipline=tr.researcher_discipline,
        opportunity_discipline=tr.opportunity_discipline,
        prior_success_rate=tr.prior_success_rate,
        prior_application_count=tr.prior_application_count,
        timeline_readiness_score=tr.timeline_readiness_score,
        days_to_deadline=tr.days_to_deadline,
        accepted=tr.accepted,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/match", response_model=MatchResponse)
async def match_opportunities(req: MatchRequest):
    """Score one or more opportunities for a researcher."""
    from app.ml.opportunity_matching import service

    records: List[MatchRecord] = []
    researcher_texts: List[str] = []
    opp_texts: List[str] = []
    use_text_embedding = False

    for opp in req.opportunities:
        rec = _input_to_record(opp)
        records.append(rec)

        if (
            opp.researcher_text
            and opp.opportunity_text
            and opp.cosine_similarity is None
        ):
            use_text_embedding = True
            researcher_texts.append(opp.researcher_text)
            opp_texts.append(opp.opportunity_text)

    try:
        if use_text_embedding and researcher_texts:
            # All inputs use the same researcher text (first one)
            results = service.match_from_texts(
                researcher_texts[0],
                opp_texts,
                records=records,
            )
        else:
            results = service.match_opportunities(records)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    return MatchResponse(
        results=[MatchResultOut(**r) for r in results]
    )


@router.post("/train", response_model=TrainResponse)
async def train_model(req: TrainRequest):
    """Train the ranking model on historical acceptance outcomes."""
    from app.ml.opportunity_matching import service

    records = [_train_record_to_match(r) for r in req.records]
    try:
        result = service.train_model(records)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return TrainResponse(
        metrics=MetricsOut(**result["metrics"]),
        feature_importances=result["feature_importances"],
        n_samples=result["n_samples"],
        n_features=result["n_features"],
    )


@router.post("/bootstrap", response_model=TrainResponse)
async def bootstrap_model(req: BootstrapRequest):
    """Train the ranking model on synthetic data for quick start."""
    from app.ml.opportunity_matching import service

    result = service.bootstrap_model(n=req.n)
    return TrainResponse(
        metrics=MetricsOut(**result["metrics"]),
        feature_importances=result["feature_importances"],
        n_samples=result["n_samples"],
        n_features=result["n_features"],
    )


@router.get("/status", response_model=ModelStatusOut)
async def model_status():
    """Return metadata about the current trained model."""
    from app.ml.opportunity_matching import service

    status = service.get_model_status()
    if status["loaded"]:
        return ModelStatusOut(
            loaded=True,
            metrics=MetricsOut(**status["metrics"]),
            n_samples=status.get("n_samples"),
            n_features=status.get("n_features"),
        )
    return ModelStatusOut(loaded=False)
