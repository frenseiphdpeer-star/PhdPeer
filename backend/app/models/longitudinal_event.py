"""
Longitudinal event store — immutable, append-only audit events.

Schema: event_id, user_id, role, event_type, entity_type, entity_id,
        metadata (JSON), timestamp, source_module.
No update/delete; audit trail only.
"""

from datetime import datetime
from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid

from app.database import Base


class LongitudinalEvent(Base):
    """
    Immutable event record for audit trail and longitudinal analytics.
    Append-only: no updates or deletes.
    """

    __tablename__ = "longitudinal_events"
    __table_args__ = {"comment": "Append-only event log; do not update or delete rows."}

    event_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    role = Column(String(32), nullable=False, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    entity_type = Column(String(64), nullable=True, index=True)
    entity_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    metadata_ = Column("metadata", JSONB, nullable=False, default=dict)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    source_module = Column(String(128), nullable=False, index=True)
