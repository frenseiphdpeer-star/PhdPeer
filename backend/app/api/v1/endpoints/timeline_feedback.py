"""
Timeline adjustment suggestions: list, generate, accept, reject.

Bidirectional feedback from signals (milestone delay, supervision inactivity,
writing stagnation).  Timeline remains user-controlled; no auto-modification.
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.security import get_current_user, require_permission, Permission
from app.core.data_visibility import can_access_user_data
from app.models.user import User
from app.models.timeline_adjustment_suggestion import TimelineAdjustmentSuggestion
from app.schemas.timeline import TimelineSuggestionOut
from app.services.timeline_feedback_service import TimelineFeedbackService

router = APIRouter()


def _suggestion_to_schema(s: TimelineAdjustmentSuggestion) -> TimelineSuggestionOut:
    return TimelineSuggestionOut.model_validate(s)


@router.get(
    "/suggestions",
    response_model=list[TimelineSuggestionOut],
    summary="List timeline adjustment suggestions for a user",
)
def list_timeline_adjustment_suggestions(
    user_id: Optional[UUID] = Query(None, description="Target user (default: current)"),
    status: Optional[str] = Query(None, description="Filter: pending, accepted, rejected"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[TimelineSuggestionOut]:
    target_id = user_id or current_user.id
    if not can_access_user_data(db, current_user, target_id):
        raise HTTPException(status_code=403, detail="Not allowed to view this user's suggestions")

    q = db.query(TimelineAdjustmentSuggestion).filter(
        TimelineAdjustmentSuggestion.user_id == target_id
    )
    if status:
        q = q.filter(TimelineAdjustmentSuggestion.status == status)

    rows = q.order_by(TimelineAdjustmentSuggestion.created_at.desc()).all()
    return [_suggestion_to_schema(r) for r in rows]


@router.post(
    "/suggestions/generate",
    response_model=list[TimelineSuggestionOut],
    summary="Generate adjustment suggestions from signals",
)
def generate_timeline_adjustment_suggestions(
    user_id: Optional[UUID] = Query(None),
    committed_timeline_id: Optional[UUID] = Query(None, description="Timeline (default: latest)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.TIMELINE_EDIT)),
) -> list[TimelineSuggestionOut]:
    target_id = user_id or current_user.id
    if current_user.id != target_id and not can_access_user_data(db, current_user, target_id):
        raise HTTPException(status_code=403, detail="Not allowed to generate suggestions for this user")

    svc = TimelineFeedbackService(db)
    created = svc.generate_suggestions_for_user(target_id, committed_timeline_id=committed_timeline_id)
    db.commit()
    return [_suggestion_to_schema(s) for s in created]


@router.post(
    "/suggestions/{suggestion_id}/accept",
    response_model=TimelineSuggestionOut,
    summary="Accept an adjustment suggestion",
)
def accept_timeline_adjustment(
    suggestion_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.TIMELINE_EDIT)),
) -> TimelineSuggestionOut:
    svc = TimelineFeedbackService(db)
    suggestion = svc.accept_suggestion(suggestion_id, current_user.id)
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found or already responded")
    return _suggestion_to_schema(suggestion)


@router.post(
    "/suggestions/{suggestion_id}/reject",
    response_model=TimelineSuggestionOut,
    summary="Reject an adjustment suggestion",
)
def reject_timeline_adjustment(
    suggestion_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.TIMELINE_EDIT)),
) -> TimelineSuggestionOut:
    svc = TimelineFeedbackService(db)
    suggestion = svc.reject_suggestion(suggestion_id, current_user.id)
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found or already responded")
    return _suggestion_to_schema(suggestion)
