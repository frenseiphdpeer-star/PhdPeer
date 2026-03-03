"""
REST endpoints for the Publisher Readiness Index.

Routes
------
POST /analyse    – train + score from raw readiness records
POST /score      – score with pre-trained model (no training)
POST /synthetic  – generate & optionally analyse synthetic data
GET  /status     – check model availability
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from app.schemas.publisher_readiness import (
    AnalyseRequest,
    AnalyseResponse,
    ModelStatusResponse,
    ScoreRequest,
    SyntheticRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/analyse", response_model=AnalyseResponse)
async def analyse(req: AnalyseRequest):
    """Train the readiness model and score all records."""
    from app.ml.publisher_readiness import service
    from app.ml.publisher_readiness.features import RawReadinessRecord

    try:
        records = [
            RawReadinessRecord(
                coherence_score=r.coherence_score,
                novelty_score=r.novelty_score,
                supervision_quality_score=r.supervision_quality_score,
                revision_density=r.revision_density,
                citation_consistency=r.citation_consistency,
                stage_completion_ratio=r.stage_completion_ratio,
                acceptance_outcome=r.acceptance_outcome,
                researcher_id=r.researcher_id,
            )
            for r in req.records
        ]
        result = service.analyse(records, save_model=req.save_model)
        return result
    except Exception as exc:
        logger.exception("Publisher readiness analysis failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/score")
async def score(req: ScoreRequest):
    """Score records using an already-trained model."""
    from app.ml.publisher_readiness import service
    from app.ml.publisher_readiness.features import RawReadinessRecord

    try:
        records = [
            RawReadinessRecord(
                coherence_score=r.coherence_score,
                novelty_score=r.novelty_score,
                supervision_quality_score=r.supervision_quality_score,
                revision_density=r.revision_density,
                citation_consistency=r.citation_consistency,
                stage_completion_ratio=r.stage_completion_ratio,
                researcher_id=r.researcher_id,
            )
            for r in req.records
        ]
        predictions = service.score(records)
        return {"predictions": predictions}
    except Exception as exc:
        logger.exception("Publisher readiness scoring failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/synthetic")
async def generate_and_analyse(req: SyntheticRequest):
    """Generate synthetic readiness data and optionally analyse."""
    from app.ml.publisher_readiness import service

    try:
        records = service.generate_synthetic_dataset(n=req.n, seed=req.seed)

        if not req.run_analysis:
            return {
                "n": req.n,
                "seed": req.seed,
                "n_records": len(records),
            }

        result = service.analyse(records, save_model=True)
        return {
            "n": req.n,
            "seed": req.seed,
            "n_records": len(records),
            "analysis": result,
        }
    except Exception as exc:
        logger.exception("Synthetic readiness analysis failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/status", response_model=ModelStatusResponse)
async def model_status():
    """Check whether a trained readiness model exists."""
    from app.ml.publisher_readiness import service

    return service.get_model_status()
