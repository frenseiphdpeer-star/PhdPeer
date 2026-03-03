"""
REST endpoints for Cross-Feature Intelligence Fusion Engine.

Routes
------
POST /analyse     – full fusion pipeline from raw observations
POST /synthetic   – generate & analyse synthetic signal data
GET  /status      – check model availability
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from app.ml.fusion_engine.signals import SignalObservation
from app.schemas.fusion_engine import (
    AnalyseRequest,
    AnalyseResponse,
    ModelStatusResponse,
    SyntheticRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/analyse", response_model=AnalyseResponse)
async def analyse(req: AnalyseRequest):
    """Run full cross-feature fusion analysis."""
    from app.ml.fusion_engine import service

    try:
        obs = [
            SignalObservation(
                timestamp=o.timestamp,
                signal_name=o.signal_name,
                value=o.value,
                researcher_id=o.researcher_id,
            )
            for o in req.observations
        ]
        result = service.analyse(obs, save_model=req.save_model)

        # Enrich correlation with strongest_pairs for the response
        if "correlation" in result and "strongest_pairs" not in result["correlation"]:
            result["correlation"]["strongest_pairs"] = []

        return result
    except Exception as exc:
        logger.exception("Fusion analysis failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/synthetic")
async def generate_and_analyse(req: SyntheticRequest):
    """Generate synthetic signal data and optionally analyse it."""
    from app.ml.fusion_engine import service

    try:
        synth = service.generate_synthetic_dataset(
            n_researchers=req.n_researchers,
            n_weeks=req.n_weeks,
            seed=req.seed,
        )

        if not req.run_analysis:
            return {
                "n_researchers": req.n_researchers,
                "n_weeks": req.n_weeks,
                "n_observations": synth["n_observations"],
                "seed": req.seed,
            }

        result = service.analyse(
            synth["observations"],
            save_model=True,
        )
        return {
            "n_researchers": req.n_researchers,
            "n_weeks": req.n_weeks,
            "n_observations": synth["n_observations"],
            "seed": req.seed,
            "analysis": result,
        }
    except Exception as exc:
        logger.exception("Synthetic fusion analysis failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/status", response_model=ModelStatusResponse)
async def model_status():
    """Check whether a trained fusion model exists."""
    from app.ml.fusion_engine import service

    return service.get_model_status()
