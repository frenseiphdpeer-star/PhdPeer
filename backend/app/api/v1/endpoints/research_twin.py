"""
REST endpoints for AI Research Twin Behavioural Modelling.

Routes
------
POST /analyse              – full twin pipeline from raw events
POST /analyse/researcher   – single-researcher analysis
POST /synthetic            – generate & analyse synthetic events
GET  /status               – check LSTM model availability
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from app.schemas.research_twin import (
    AnalyseRequest,
    AnalyseResponse,
    ModelStatusResponse,
    ResearcherAnalyseRequest,
    SyntheticRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/analyse", response_model=AnalyseResponse)
async def analyse(req: AnalyseRequest):
    """Run the full AI Research Twin pipeline across all researchers."""
    from app.ml.research_twin import service
    from app.ml.research_twin.temporal import BehaviourEvent

    try:
        events = [
            BehaviourEvent(
                timestamp=e.timestamp,
                event_type=e.event_type,
                researcher_id=e.researcher_id or "default",
            )
            for e in req.events
        ]
        result = service.analyse(events, save_model=req.save_model)
        return result
    except Exception as exc:
        logger.exception("Research Twin analysis failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/analyse/researcher")
async def analyse_researcher(req: ResearcherAnalyseRequest):
    """Run the Research Twin pipeline for a single researcher."""
    from app.ml.research_twin import service
    from app.ml.research_twin.temporal import BehaviourEvent

    try:
        events = [
            BehaviourEvent(
                timestamp=e.timestamp,
                event_type=e.event_type,
                researcher_id=req.researcher_id,
            )
            for e in req.events
        ]
        result = service.analyse_researcher(req.researcher_id, events)
        return result
    except Exception as exc:
        logger.exception("Single-researcher Research Twin analysis failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/synthetic")
async def generate_and_analyse(req: SyntheticRequest):
    """Generate synthetic behavioural events and optionally analyse."""
    from app.ml.research_twin import service

    try:
        synth = service.generate_synthetic_events(
            n_researchers=req.n_researchers,
            n_days=req.n_days,
            seed=req.seed,
        )

        if not req.run_analysis:
            return {
                "n_researchers": req.n_researchers,
                "n_days": req.n_days,
                "n_events": synth["n_events"],
                "seed": req.seed,
            }

        result = service.analyse(
            synth["events"],
            save_model=True,
        )
        return {
            "n_researchers": req.n_researchers,
            "n_days": req.n_days,
            "n_events": synth["n_events"],
            "seed": req.seed,
            "analysis": result,
        }
    except Exception as exc:
        logger.exception("Synthetic Research Twin analysis failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/status", response_model=ModelStatusResponse)
async def model_status():
    """Check whether a trained LSTM model exists on disk."""
    from app.ml.research_twin import service

    return service.get_model_status()
