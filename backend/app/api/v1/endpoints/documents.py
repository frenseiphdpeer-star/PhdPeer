"""Document API endpoints. RBAC: Timeline/edit context — Researcher uploads for self only."""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.core.security import get_current_user, require_permission, Permission
from app.models.user import User
from app.services.document_service import (
    DocumentService,
    DocumentServiceError,
    UnsupportedFileTypeError,
)
from app.services.stage_suggestion_service import StageSuggestionService

router = APIRouter()


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(..., description="Document file (PDF or DOCX)"),
    user_id: UUID = Form(..., description="User ID (must match current user for researchers)"),
    title: str | None = Form(None, description="Document title (defaults to filename)"),
    description: str | None = Form(None, description="Document description"),
    document_type: str | None = Form(None, description="Document type (e.g., 'research_proposal')"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.TIMELINE_EDIT)),
) -> dict:
    """
    Upload and process a document.
    
    Behavior:
    - Validates file type (PDF/DOCX)
    - Extracts and normalizes text
    - Saves file to storage
    - Creates DocumentArtifact record
    - Returns document ID
    
    Uses: DocumentService.upload_document()
    
    Args:
        file: Uploaded file (PDF or DOCX)
        user_id: User ID
        title: Optional document title
        description: Optional document description
        document_type: Optional document type
        db: Database session
        
    Returns:
        Dictionary with document_id (UUID)
        
    Raises:
        HTTPException: If upload fails
    """
    if current_user.id != user_id:
        raise HTTPException(
            status_code=403,
            detail="Can only upload documents for your own account",
        )
    try:
        # Read file content
        file_content = await file.read()
        filename = file.filename or "document"
        
        # Create service and upload
        service = DocumentService(db)
        document_id = service.upload_document(
            user_id=user_id,
            file_content=file_content,
            filename=filename,
            title=title,
            description=description,
            document_type=document_type,
        )
        
        return {
            "document_id": str(document_id),
        }
        
    except UnsupportedFileTypeError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except DocumentServiceError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Document upload failed: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {str(e)}"
        )


class StageOverrideBody(BaseModel):
    stage: str
    reason: str = ""


@router.get("/{document_id}/stage-suggestion")
def get_stage_suggestion(
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Get stage classification suggestion for a document (after upload).
    Returns suggested_stage, confidence_score; reasoning_tokens are internal.
    """
    svc = StageSuggestionService(db)
    suggestion = svc.get_suggestion(document_id, current_user.id)
    if not suggestion:
        raise HTTPException(status_code=404, detail="Document or stage suggestion not found")
    return {
        "document_id": str(document_id),
        "suggested_stage": suggestion.suggested_stage,
        "confidence_score": suggestion.confidence_score,
        "accepted_stage": suggestion.accepted_stage,
        "override_stage": suggestion.override_stage,
        "override_reason": suggestion.override_reason,
        "system_suggested_stage": suggestion.system_suggested_stage,
    }


@router.post("/{document_id}/stage-suggestion/accept")
def accept_stage_suggestion(
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.TIMELINE_EDIT)),
) -> dict:
    """Accept the suggested stage (accepted_stage = suggested_stage). Does not delete history."""
    svc = StageSuggestionService(db)
    suggestion = svc.accept_stage(document_id, current_user.id)
    if not suggestion:
        raise HTTPException(status_code=404, detail="Document or stage suggestion not found")
    return {
        "document_id": str(document_id),
        "accepted_stage": suggestion.accepted_stage,
    }


@router.post("/{document_id}/stage-suggestion/override")
def override_stage_suggestion(
    document_id: UUID,
    body: StageOverrideBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.TIMELINE_EDIT)),
) -> dict:
    """
    Override with user-chosen stage. Logs stage_override event, stores override_reason
    and system_suggested_stage, triggers timeline regeneration. Does not delete historical data.
    """
    if not body.stage.strip():
        raise HTTPException(status_code=400, detail="stage is required")
    svc = StageSuggestionService(db)
    suggestion = svc.override_stage(
        document_id, current_user.id, override_stage=body.stage.strip(), override_reason=body.reason or ""
    )
    if not suggestion:
        raise HTTPException(status_code=404, detail="Document or stage suggestion not found")
    return {
        "document_id": str(document_id),
        "override_stage": suggestion.override_stage,
        "system_suggested_stage": suggestion.system_suggested_stage,
        "timeline_regeneration_triggered": True,
    }
