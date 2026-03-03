"""
REST endpoints for Collaboration Network Intelligence.

Routes
------
POST /analyse             – full network analysis
POST /analyse/researcher  – single-researcher analysis
POST /synthetic           – generate & analyse synthetic network
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from app.ml.collaboration_network.graph import CitationEdge, CoauthorEdge
from app.schemas.collaboration_network import (
    AnalyseRequest,
    AnalyseResponse,
    ResearcherAnalyseRequest,
    ResearcherAnalyseResponse,
    SyntheticRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_citation_edge(e) -> CitationEdge:
    return CitationEdge(source=e.source, target=e.target, weight=e.weight)


def _to_coauthor_edge(e) -> CoauthorEdge:
    return CoauthorEdge(source=e.source, target=e.target, weight=e.weight)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/analyse", response_model=AnalyseResponse)
async def analyse_network(req: AnalyseRequest):
    """Run full collaboration network analysis."""
    from app.ml.collaboration_network import service

    try:
        cit = [_to_citation_edge(e) for e in req.citation_edges]
        coauth = [_to_coauthor_edge(e) for e in req.coauthor_edges]

        result = service.analyse(
            cit, coauth, target_nodes=req.target_nodes,
        )
        return result
    except Exception as exc:
        logger.exception("Network analysis failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/analyse/researcher", response_model=ResearcherAnalyseResponse)
async def analyse_researcher(req: ResearcherAnalyseRequest):
    """Run analysis scoped to one researcher."""
    from app.ml.collaboration_network import service

    try:
        cit = [_to_citation_edge(e) for e in req.citation_edges]
        coauth = [_to_coauthor_edge(e) for e in req.coauthor_edges]

        result = service.analyse_for_researcher(
            req.researcher_id, cit, coauth,
        )
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Researcher analysis failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/synthetic")
async def generate_and_analyse(req: SyntheticRequest):
    """Generate a synthetic network and run full analysis."""
    from app.ml.collaboration_network import service

    try:
        synth = service.generate_synthetic_network(
            n_researchers=req.n_researchers, seed=req.seed,
        )
        result = service.analyse(
            synth["citation_edges"],
            synth["coauthor_edges"],
        )
        return {
            "n_researchers": req.n_researchers,
            "seed": req.seed,
            "analysis": result,
        }
    except Exception as exc:
        logger.exception("Synthetic network analysis failed")
        raise HTTPException(status_code=500, detail=str(exc))
