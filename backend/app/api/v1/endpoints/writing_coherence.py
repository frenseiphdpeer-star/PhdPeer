"""
Writing Coherence API endpoints.

Provides:
  POST /writing-coherence/score-text       – score raw text
  POST /writing-coherence/score-document   – score an uploaded document by ID
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.ml.writing_coherence.service import (
    score_document_by_id,
    score_document_text,
)
from app.schemas.writing_coherence import (
    ScoreDocumentRequest,
    ScoreResponse,
    ScoreTextRequest,
    WritingCoherenceOut,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# POST /score-text
# ---------------------------------------------------------------------------
@router.post(
    "/score-text",
    response_model=ScoreResponse,
    summary="Score writing coherence from raw text",
    description=(
        "Analyse paragraph-level coherence, topic drift, and structural "
        "consistency of the supplied text.  Returns three sub-scores plus a "
        "weighted composite (all 0–100)."
    ),
)
async def score_text_endpoint(req: ScoreTextRequest) -> ScoreResponse:
    try:
        result = score_document_text(
            req.text,
            paragraphs=req.paragraphs,
        )
        return ScoreResponse(data=WritingCoherenceOut(**result))

    except Exception as exc:
        logger.exception("Writing coherence scoring failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Scoring error: {exc}",
        ) from exc


# ---------------------------------------------------------------------------
# POST /score-document
# ---------------------------------------------------------------------------
@router.post(
    "/score-document",
    response_model=ScoreResponse,
    summary="Score coherence of an uploaded document",
    description=(
        "Fetch an already-uploaded document by its ID and score its coherence."
    ),
)
async def score_document_endpoint(
    req: ScoreDocumentRequest,
    db: Session = Depends(get_db),
) -> ScoreResponse:
    try:
        result = score_document_by_id(str(req.document_id), db)
        return ScoreResponse(data=WritingCoherenceOut(**result))

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Document coherence scoring failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Scoring error: {exc}",
        ) from exc
