"""
Engagement API: reminders, digests, and engagement signals.

Data-only; no UI logic. Dashboard consumes reminders/digests; intelligence layer uses signals.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.engagement_event import EngagementEvent, ENGAGEMENT_KIND_MONTHLY_DIGEST
from app.services.engagement_engine import EngagementEngine

router = APIRouter()


class ReminderResponse(BaseModel):
    id: UUID
    kind: str
    message: Optional[str]
    payload: Dict[str, Any]
    triggered_at: datetime
    acknowledged_at: Optional[datetime]


class DigestResponse(BaseModel):
    id: UUID
    year: int
    month: int
    payload: Dict[str, Any]
    triggered_at: datetime


class EngagementSignalsResponse(BaseModel):
    user_id: str
    low_engagement: bool
    writing_inactivity: bool
    supervision_drift: bool
    last_any_activity_at: Optional[str]
    last_writing_activity_at: Optional[str]
    last_supervision_activity_at: Optional[str]
    days_since_any: Optional[int]
    days_since_writing: Optional[int]
    days_since_supervision: Optional[int]


@router.get("/reminders", response_model=List[ReminderResponse])
def list_reminders(
    acknowledged: Optional[bool] = Query(None, description="Filter by acknowledged (true/false); omit for all"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[ReminderResponse]:
    """
    List engagement reminders for the current user (for dashboard).
    Excludes monthly_digest; use /engagement/digests for those.
    """
    q = db.query(EngagementEvent).filter(
        EngagementEvent.user_id == current_user.id,
        EngagementEvent.kind != ENGAGEMENT_KIND_MONTHLY_DIGEST,
    )
    if acknowledged is not None:
        if acknowledged:
            q = q.filter(EngagementEvent.acknowledged_at.isnot(None))
        else:
            q = q.filter(EngagementEvent.acknowledged_at.is_(None))
    rows = q.order_by(EngagementEvent.triggered_at.desc()).limit(limit).all()
    return [
        ReminderResponse(
            id=r.id,
            kind=r.kind,
            message=r.message,
            payload=r.payload or {},
            triggered_at=r.triggered_at,
            acknowledged_at=r.acknowledged_at,
        )
        for r in rows
    ]


@router.get("/digests", response_model=List[DigestResponse])
def list_digests(
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None),
    limit: int = Query(12, ge=1, le=24),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[DigestResponse]:
    """List monthly digest snapshots for the current user."""
    q = db.query(EngagementEvent).filter(
        EngagementEvent.user_id == current_user.id,
        EngagementEvent.kind == ENGAGEMENT_KIND_MONTHLY_DIGEST,
    )
    rows = q.order_by(EngagementEvent.triggered_at.desc()).limit(limit * 2 if (year is not None or month is not None) else limit).all()
    out = []
    for r in rows:
        py = r.payload or {}
        if year is not None and py.get("year") != year:
            continue
        if month is not None and py.get("month") != month:
            continue
        out.append(
            DigestResponse(
                id=r.id,
                year=py.get("year", 0),
                month=py.get("month", 0),
                payload=py,
                triggered_at=r.triggered_at,
            )
        )
        if len(out) >= limit:
            break
    return out


@router.get("/signals", response_model=EngagementSignalsResponse)
def get_engagement_signals(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EngagementSignalsResponse:
    """
    Engagement signals for the current user (for intelligence layer / dashboard).
    No UI logic; consumers interpret flags (low_engagement, writing_inactivity, supervision_drift).
    """
    engine = EngagementEngine(db)
    signals = engine.get_engagement_signals(current_user.id)
    return EngagementSignalsResponse(**signals)


class AcknowledgeBody(BaseModel):
    pass


@router.post("/reminders/{reminder_id}/acknowledge")
def acknowledge_reminder(
    reminder_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Mark a reminder as acknowledged (e.g. when user dismisses in dashboard)."""
    from datetime import timezone
    from fastapi import HTTPException
    r = db.query(EngagementEvent).filter(EngagementEvent.id == reminder_id, EngagementEvent.user_id == current_user.id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Reminder not found")
    r.acknowledged_at = datetime.now(timezone.utc)
    db.add(r)
    db.commit()
    return {"acknowledged": True, "reminder_id": str(reminder_id)}


@router.post("/run-detection")
def run_inactivity_detection(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Run inactivity detection for the current user and create any new reminder entries.
    Safe to call periodically (e.g. from dashboard or a job).
    """
    engine = EngagementEngine(db)
    created = engine.run_inactivity_detection(current_user.id)
    db.commit()
    return {
        "created": len(created),
        "kinds": [e.kind for e in created],
    }


@router.post("/digests/generate")
def generate_monthly_digest(
    year: int = Query(..., description="Year (e.g. 2026)"),
    month: int = Query(..., ge=1, le=12, description="Month (1-12)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Generate and store monthly digest for the given month (summary from event store).
    Stores engagement_event and emits engagement_monthly_digest to longitudinal event store.
    """
    engine = EngagementEngine(db)
    digest = engine.generate_monthly_digest(
        current_user.id,
        year,
        month,
        user_role=getattr(current_user, "role", "researcher"),
    )
    return {
        "digest_id": str(digest.id),
        "year": year,
        "month": month,
        "payload": digest.payload,
    }
