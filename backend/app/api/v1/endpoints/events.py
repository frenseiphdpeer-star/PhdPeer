"""
Audit API: query longitudinal event store (append-only, immutable).
Supports audit trail and analytics over standardized events.
"""

from datetime import datetime
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.core.security import get_current_user
from app.core.data_visibility import can_access_user_data, get_visible_student_ids
from app.core.event_taxonomy import SUPPORTED_EVENT_TYPES
from app.models.longitudinal_event import LongitudinalEvent
from app.models.user import User
from fastapi import HTTPException

router = APIRouter()


class EventResponse(BaseModel):
    """Schema for a single event (audit trail)."""

    event_id: UUID
    user_id: UUID
    role: str
    event_type: str
    entity_type: Optional[str]
    entity_id: Optional[UUID]
    metadata: dict
    timestamp: datetime
    source_module: str

    class Config:
        from_attributes = True


@router.get("", response_model=List[EventResponse])
def list_events(
    user_id: Optional[UUID] = Query(None, description="Filter by user ID"),
    event_type: Optional[str] = Query(None, description="Filter by event_type"),
    source_module: Optional[str] = Query(None, description="Filter by source_module"),
    from_ts: Optional[datetime] = Query(None, alias="from", description="From timestamp (UTC)"),
    to_ts: Optional[datetime] = Query(None, alias="to", description="To timestamp (UTC)"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[EventResponse]:
    """
    List events from the longitudinal event store (audit trail).
    Append-only, immutable. RBAC: researcher = own, supervisor = assigned students, admin = all.
    """
    if user_id is not None:
        if not can_access_user_data(db, current_user, user_id):
            raise HTTPException(status_code=403, detail="Not allowed to view events for this user")
    visible_ids = get_visible_student_ids(db, current_user)
    q = db.query(LongitudinalEvent)
    if user_id is not None:
        q = q.filter(LongitudinalEvent.user_id == user_id)
    elif visible_ids is not None:
        q = q.filter(LongitudinalEvent.user_id.in_(visible_ids))
    if event_type is not None:
        if event_type not in SUPPORTED_EVENT_TYPES:
            return []
        q = q.filter(LongitudinalEvent.event_type == event_type)
    if source_module is not None:
        q = q.filter(LongitudinalEvent.source_module == source_module)
    if from_ts is not None:
        q = q.filter(LongitudinalEvent.timestamp >= from_ts)
    if to_ts is not None:
        q = q.filter(LongitudinalEvent.timestamp <= to_ts)
    rows = q.order_by(LongitudinalEvent.timestamp.desc()).offset(offset).limit(limit).all()
    return [
        EventResponse(
            event_id=r.event_id,
            user_id=r.user_id,
            role=r.role,
            event_type=r.event_type,
            entity_type=r.entity_type,
            entity_id=r.entity_id,
            metadata=r.metadata_ or {},
            timestamp=r.timestamp,
            source_module=r.source_module,
        )
        for r in rows
    ]


@router.get("/types", response_model=List[str])
def list_event_types() -> List[str]:
    """Return supported event types (taxonomy)."""
    return sorted(SUPPORTED_EVENT_TYPES)
