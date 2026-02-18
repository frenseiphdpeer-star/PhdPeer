"""
Longitudinal event store: immutable, append-only event logging.

Architecture: Event normalization layer. All feature modules must emit standardized
events via this store. No update or delete methods — audit trail only.
All signals in the intelligence layer are traceable to raw events (event_id) in this store.
"""

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.longitudinal_event import LongitudinalEvent
from app.core.event_taxonomy import (
    EventType,
    SUPPORTED_EVENT_TYPES,
    metadata_with_version,
)


class EventStoreError(Exception):
    """Raised when event emission fails."""
    pass


class EventStore:
    """
    Append-only event store. Immutable logging only.
    """

    def __init__(self, db: Session):
        self.db = db

    def emit(
        self,
        user_id: UUID,
        role: str,
        event_type: str,
        source_module: str,
        *,
        entity_type: Optional[str] = None,
        entity_id: Optional[UUID] = None,
        metadata: Optional[Dict[str, Any]] = None,
        metadata_version: int = 1,
        timestamp: Optional[datetime] = None,
    ) -> UUID:
        """
        Append a single event. Immutable; no update/delete.

        Args:
            user_id: Actor user ID.
            role: Actor role (researcher, supervisor, institution_admin).
            event_type: Must be one of EventType (e.g. document_uploaded).
            source_module: Module that emitted (e.g. documents, progress).
            entity_type: Optional entity type (e.g. document_artifact, milestone).
            entity_id: Optional entity ID.
            metadata: Optional JSON-serializable payload; will get "v" key.
            metadata_version: Version for metadata schema.
            timestamp: Optional; defaults to now (UTC).

        Returns:
            event_id (UUID) of the created record.

        Raises:
            EventStoreError: If event_type is invalid or insert fails.
        """
        if event_type not in SUPPORTED_EVENT_TYPES:
            raise EventStoreError(
                f"Unsupported event_type: {event_type}. "
                f"Allowed: {sorted(SUPPORTED_EVENT_TYPES)}"
            )
        payload = metadata_with_version(metadata, metadata_version)
        ts = timestamp or datetime.utcnow()
        event = LongitudinalEvent(
            user_id=user_id,
            role=role,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata_=payload,
            timestamp=ts,
            source_module=source_module,
        )
        self.db.add(event)
        self.db.flush()
        return event.event_id


def emit_event(
    db: Session,
    user_id: UUID,
    role: str,
    event_type: str,
    source_module: str,
    *,
    entity_type: Optional[str] = None,
    entity_id: Optional[UUID] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[UUID]:
    """
    Convenience: append one event and return event_id.
    Swallows EventStoreError and returns None so feature code does not fail on log failure.
    """
    try:
        store = EventStore(db)
        return store.emit(
            user_id=user_id,
            role=role,
            event_type=event_type,
            source_module=source_module,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata=metadata,
        )
    except EventStoreError:
        return None
