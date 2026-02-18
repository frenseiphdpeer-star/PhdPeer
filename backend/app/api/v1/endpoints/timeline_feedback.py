"""
Timeline adjustment suggestions: list, generate, accept, reject.

Bidirectional feedback from signals (milestone delay, supervision inactivity, writing stagnation).
Timeline remains user-controlled; no auto-modification of milestones.
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.security import get_current_user, require_permission, Permission
from app.core.data_visibility import can_access_user_data
from app.models.user import User
from app.models.timeline_adjustment_suggestion import TimelineAdjustmentSuggestion
from app.services.timeline_feedback_service import TimelineFeedbackService

router = APIRouter()


class SuggestionResponse(BaseModel):
    id: UUID
    committed_timeline_id: UUID
    reason: str
    title: str
    message: str
    suggestion_payload: dict
    status: str
    responded_at: Optional[str]

    class Config:
        from_attributes = True


@router.get("/suggestions", response_model=List[SuggestionResponse])
def list_timeline_adjustment_suggestions(
    user_id: Optional[UUID] = Query(None, description="User (default: current; must be visible)"),
    status: Optional[str] = Query(None, description="Filter: pending, accepted, rejected"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[SuggestionResponse]:
    """
    List timeline adjustment suggestions for a user.
    RBAC: user can only see own; supervisor/admin per data_visibility.
    """
    target_id = user_id or current_user.id
    if not can_access_user_data(db, current_user, target_id):
        raise HTTPException(status_code=403, detail="Not allowed to view this user's suggestions")
    q = db.query(TimelineAdjustmentSuggestion).filter(TimelineAdjustmentSuggestion.user_id == target_id)
    if status:
        q = q.filter(TimelineAdjustmentSuggestion.status == status)
    rows = q.order_by(TimelineAdjustmentSuggestion.created_at.desc()).all()
    return [
        SuggestionResponse(
            id=r.id,
            committed_timeline_id=r.committed_timeline_id,
            reason=r.reason,
            title=r.title,
            message=r.message,
            suggestion_payload=r.suggestion_payload or {},
            status=r.status,
            responded_at=r.responded_at.isoformat() if r.responded_at else None,
        )
        for r in rows
    ]


@router.post("/suggestions/generate", response_model=List[SuggestionResponse])
def generate_timeline_adjustment_suggestions(
    user_id: Optional[UUID] = Query(None),
    committed_timeline_id: Optional[UUID] = Query(None, description="Timeline (default: latest)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.TIMELINE_EDIT)),
) -> List[SuggestionResponse]:
    """
    Run signal evaluation and create pending suggestions where applicable (milestone delay,
    supervision inactivity, writing stagnation). Does not modify any milestones.
    """
    target_id = user_id or current_user.id
    if current_user.id != target_id and not can_access_user_data(db, current_user, target_id):
        raise HTTPException(status_code=403, detail="Not allowed to generate suggestions for this user")
    svc = TimelineFeedbackService(db)
    created = svc.generate_suggestions_for_user(target_id, committed_timeline_id=committed_timeline_id)
    db.commit()
    return [
        SuggestionResponse(
            id=s.id,
            committed_timeline_id=s.committed_timeline_id,
            reason=s.reason,
            title=s.title,
            message=s.message,
            suggestion_payload=s.suggestion_payload or {},
            status=s.status,
            responded_at=s.responded_at.isoformat() if s.responded_at else None,
        )
        for s in created
    ]


@router.post("/suggestions/{suggestion_id}/accept", response_model=SuggestionResponse)
def accept_timeline_adjustment(
    suggestion_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.TIMELINE_EDIT)),
) -> SuggestionResponse:
    """
    Accept a timeline adjustment suggestion. Records acceptance and logs acceptance_event.
    Does not auto-modify milestones; timeline remains user-controlled.
    """
    svc = TimelineFeedbackService(db)
    suggestion = svc.accept_suggestion(suggestion_id, current_user.id)
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found or already responded")
    return SuggestionResponse(
        id=suggestion.id,
        committed_timeline_id=suggestion.committed_timeline_id,
        reason=suggestion.reason,
        title=suggestion.title,
        message=suggestion.message,
        suggestion_payload=suggestion.suggestion_payload or {},
        status=suggestion.status,
        responded_at=suggestion.responded_at.isoformat() if suggestion.responded_at else None,
    )


@router.post("/suggestions/{suggestion_id}/reject", response_model=SuggestionResponse)
def reject_timeline_adjustment(
    suggestion_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.TIMELINE_EDIT)),
) -> SuggestionResponse:
    """Reject a timeline adjustment suggestion. Logs rejection_event."""
    svc = TimelineFeedbackService(db)
    suggestion = svc.reject_suggestion(suggestion_id, current_user.id)
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found or already responded")
    return SuggestionResponse(
        id=suggestion.id,
        committed_timeline_id=suggestion.committed_timeline_id,
        reason=suggestion.reason,
        title=suggestion.title,
        message=suggestion.message,
        suggestion_payload=suggestion.suggestion_payload or {},
        status=suggestion.status,
        responded_at=suggestion.responded_at.isoformat() if suggestion.responded_at else None,
    )
