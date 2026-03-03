"""Baseline API endpoints."""
import logging
import re
from datetime import date
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.orchestrators.baseline_orchestrator import (
    BaselineOrchestrator,
    BaselineAlreadyExistsError,
    BaselineOrchestratorError,
)
from app.orchestrators.base import OrchestrationError

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
    """Create a baseline from an uploaded document. If one already exists, returns it so the flow can continue."""
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
        # Return existing baseline_id so frontend can continue to generate timeline
        existing_id = getattr(e, "details", {}).get("existing_baseline_id")
        if existing_id:
            return {"baseline_id": str(existing_id)}
        raise HTTPException(status_code=409, detail=str(e))
    except OrchestrationError as e:
        # Base orchestrator wraps BaselineAlreadyExistsError as OrchestrationError
        msg = str(e)
        if "Baseline already exists" in msg or "baseline already exists" in msg.lower():
            cause = getattr(e, "__cause__", None)
            existing_id = None
            if isinstance(cause, BaselineAlreadyExistsError):
                existing_id = getattr(cause, "details", {}).get("existing_baseline_id")
            if not existing_id:
                # Parse "Existing baseline ID: <uuid>" from message
                match = re.search(r"Existing baseline ID:\s*([0-9a-fA-F-]{36})", msg)
                if match:
                    existing_id = match.group(1)
            if existing_id:
                return {"baseline_id": str(existing_id)}
        raise HTTPException(status_code=400, detail=msg)
    except BaselineOrchestratorError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("create_baseline_from_document failed: %s", e)
        raise HTTPException(
            status_code=500,
            detail=str(e) or "Failed to create baseline from document",
        ) from e
