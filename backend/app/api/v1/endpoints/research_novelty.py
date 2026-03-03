"""
REST endpoints for Research Novelty Scoring.

Routes
------
POST /score-text         – score raw manuscript text
POST /score-document     – score an uploaded document by ID
POST /build-corpus       – build / replace the FAISS corpus index
POST /build-demo-corpus  – generate & index a synthetic demo corpus
GET  /corpus-status      – metadata about the current index
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.schemas.research_novelty import (
    BuildCorpusRequest,
    BuildCorpusResponse,
    BuildDemoCorpusRequest,
    CorpusStatusOut,
    NoveltyScoreOut,
    RareTermOut,
    ScoreDocumentRequest,
    ScoreResponse,
    ScoreTextRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dict_to_novelty_out(d: dict) -> NoveltyScoreOut:
    """Convert the service dict into the Pydantic response model."""
    rare_terms = [
        RareTermOut(term=t, idf=v)
        for t, v in d.get("top_rare_terms", [])
    ]
    return NoveltyScoreOut(
        novelty_score=d["novelty_score"],
        field_distance=d["field_distance"],
        mean_knn_distance=d["mean_knn_distance"],
        terminology_uniqueness_index=d["terminology_uniqueness_index"],
        citation_novelty=d["citation_novelty"],
        distance_component=d["distance_component"],
        terminology_component=d["terminology_component"],
        citation_component=d["citation_component"],
        top_rare_terms=rare_terms,
        oov_ratio=d["oov_ratio"],
        n_neighbours_used=d["n_neighbours_used"],
        corpus_size=d["corpus_size"],
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/score-text", response_model=ScoreResponse)
async def score_text(req: ScoreTextRequest):
    """Score the novelty of raw manuscript text against the field corpus."""
    from app.ml.research_novelty import service

    try:
        result = service.score_text(
            req.text,
            citations=req.citations,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    return ScoreResponse(data=_dict_to_novelty_out(result))


@router.post("/score-document", response_model=ScoreResponse)
async def score_document(req: ScoreDocumentRequest):
    """Score novelty of an already-uploaded document by ID."""
    from app.ml.research_novelty import service
    from app.services.document_service import DocumentService

    doc_svc = DocumentService()
    doc = await doc_svc.get_document(str(req.document_id))
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    text = getattr(doc, "document_text", None) or getattr(doc, "raw_text", "")
    if not text:
        raise HTTPException(status_code=422, detail="Document has no text content.")

    try:
        result = service.score_text(
            text,
            citations=req.citations,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    return ScoreResponse(data=_dict_to_novelty_out(result))


@router.post("/build-corpus", response_model=BuildCorpusResponse)
async def build_corpus(req: BuildCorpusRequest):
    """Build or replace the FAISS field-corpus index."""
    from app.ml.research_novelty import service

    info = service.build_corpus_index(
        req.texts,
        ids=req.ids,
    )
    return BuildCorpusResponse(**info)


@router.post("/build-demo-corpus", response_model=BuildCorpusResponse)
async def build_demo_corpus(req: BuildDemoCorpusRequest):
    """Generate a synthetic demo corpus and build the index."""
    from app.ml.research_novelty import service

    texts = service.generate_demo_corpus(n=req.n)
    info = service.build_corpus_index(texts, save=False)
    return BuildCorpusResponse(**info)


@router.get("/corpus-status", response_model=CorpusStatusOut)
async def corpus_status():
    """Return metadata about the current corpus index."""
    from app.ml.research_novelty import service

    return CorpusStatusOut(**service.get_corpus_status())
