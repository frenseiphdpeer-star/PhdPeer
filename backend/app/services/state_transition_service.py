"""
State transition service: validate transitions, update entity state + timestamp, log to event store.
"""

from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.event_taxonomy import EventType
from app.services.event_store import EventStore, EventStoreError
from app.core.state_machines import (
    opportunity_can_transition,
    supervision_session_can_transition,
    milestone_can_transition,
    writing_version_can_transition,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class InvalidTransitionError(Exception):
    """Raised when a state transition is not allowed."""
    pass


# Entity type to validator
_TRANSITION_VALIDATORS: Dict[str, Callable[[str, str], bool]] = {
    "opportunity": opportunity_can_transition,
    "supervision_session": supervision_session_can_transition,
    "milestone": milestone_can_transition,
    "writing_version": writing_version_can_transition,
}


def validate_and_log_transition(
    db: Session,
    *,
    entity_type: str,
    entity_id: UUID,
    from_state: str,
    to_state: str,
    user_id: UUID,
    user_role: str,
    source_module: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> datetime:
    """
    Validate that the transition is allowed; emit state_transition event; return timestamp.
    Does not update the entity (caller must set state and state_entered_at).
    """
    validator = _TRANSITION_VALIDATORS.get(entity_type)
    if not validator:
        raise InvalidTransitionError(f"Unknown entity_type for state machine: {entity_type}")
    if not validator(from_state, to_state):
        raise InvalidTransitionError(
            f"Invalid transition for {entity_type}: {from_state} -> {to_state}"
        )
    ts = _utcnow()
    payload = dict(metadata or {})
    payload["from_state"] = from_state
    payload["to_state"] = to_state
    payload["entity_type"] = entity_type
    payload["entity_id"] = str(entity_id)
    payload["transitioned_at"] = ts.isoformat()
    try:
        EventStore(db).emit(
            user_id=user_id,
            role=user_role,
            event_type=EventType.STATE_TRANSITION.value,
            source_module=source_module,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata=payload,
            timestamp=ts,
        )
    except EventStoreError:
        pass  # do not fail transition if logging fails
    return ts


def transition_opportunity(
    db: Session,
    user_opportunity_id: UUID,
    to_state: str,
    user_id: UUID,
    user_role: str,
    source_module: str = "opportunity",
) -> "UserOpportunity":
    """Validate, log, and apply opportunity state transition. Returns updated entity."""
    from app.models.user_opportunity import UserOpportunity
    uo = db.query(UserOpportunity).filter(UserOpportunity.id == user_opportunity_id).first()
    if not uo:
        raise InvalidTransitionError("UserOpportunity not found")
    ts = validate_and_log_transition(
        db,
        entity_type="opportunity",
        entity_id=uo.id,
        from_state=uo.state,
        to_state=to_state,
        user_id=user_id,
        user_role=user_role,
        source_module=source_module,
    )
    uo.state = to_state
    uo.state_entered_at = ts
    db.add(uo)
    return uo


def transition_supervision_session(
    db: Session,
    session_id: UUID,
    to_state: str,
    user_id: UUID,
    user_role: str,
    source_module: str = "supervision",
) -> "SupervisionSession":
    """Validate, log, and apply supervision session state transition."""
    from app.models.supervision_session import SupervisionSession
    session = db.query(SupervisionSession).filter(SupervisionSession.id == session_id).first()
    if not session:
        raise InvalidTransitionError("SupervisionSession not found")
    ts = validate_and_log_transition(
        db,
        entity_type="supervision_session",
        entity_id=session.id,
        from_state=session.state,
        to_state=to_state,
        user_id=user_id,
        user_role=user_role,
        source_module=source_module,
    )
    session.state = to_state
    session.state_entered_at = ts
    db.add(session)
    return session


def transition_milestone(
    db: Session,
    milestone_id: UUID,
    to_state: str,
    user_id: UUID,
    user_role: str,
    source_module: str = "progress",
) -> "TimelineMilestone":
    """Validate, log, and apply milestone state transition."""
    from app.models.timeline_milestone import TimelineMilestone
    m = db.query(TimelineMilestone).filter(TimelineMilestone.id == milestone_id).first()
    if not m:
        raise InvalidTransitionError("TimelineMilestone not found")
    from_state = getattr(m, "state", "upcoming") or "upcoming"
    ts = validate_and_log_transition(
        db,
        entity_type="milestone",
        entity_id=m.id,
        from_state=from_state,
        to_state=to_state,
        user_id=user_id,
        user_role=user_role,
        source_module=source_module,
    )
    m.state = to_state
    m.state_entered_at = ts
    db.add(m)
    return m


def transition_writing_version(
    db: Session,
    writing_version_id: UUID,
    to_state: str,
    user_id: UUID,
    user_role: str,
    source_module: str = "writing",
) -> "WritingVersion":
    """Validate, log, and apply writing version state transition."""
    from app.models.writing_version import WritingVersion
    wv = db.query(WritingVersion).filter(WritingVersion.id == writing_version_id).first()
    if not wv:
        raise InvalidTransitionError("WritingVersion not found")
    ts = validate_and_log_transition(
        db,
        entity_type="writing_version",
        entity_id=wv.id,
        from_state=wv.state,
        to_state=to_state,
        user_id=user_id,
        user_role=user_role,
        source_module=source_module,
    )
    wv.state = to_state
    wv.state_entered_at = ts
    db.add(wv)
    return wv
