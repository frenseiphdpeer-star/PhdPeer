"""Baseline API endpoints."""
from datetime import date
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.orchestrators.baseline_orchestrator import (
    BaselineOrchestrator,
    BaselineAlreadyExistsError,
    BaselineOrchestratorError,
)

router = APIRouter()


class CreateBaselineFromDocumentRequest(BaseModel):
    document_id: UUID
    program_name: str = "PhD Program"
    institution: str = "University"
    field_of_study: str = "Research"
    start_date: date | None = None


@router.post("/from-document")
def create_baseline_from_document(
    body: CreateBaselineFromDocumentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Create a baseline from an uploaded document."""
    orch = BaselineOrchestrator(db, user_id=current_user.id)
    start = body.start_date or date.today()
    try:
        result = orch.create(
            request_id=f"bl_{body.document_id.hex[:16]}",
            user_id=current_user.id,
            program_name=body.program_name,
            institution=body.institution,
            field_of_study=body.field_of_study,
            start_date=start,
            document_id=body.document_id,
        )
        return {"baseline_id": result["baseline_id"]}
    except BaselineAlreadyExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except BaselineOrchestratorError as e:
        raise HTTPException(status_code=400, detail=str(e))
