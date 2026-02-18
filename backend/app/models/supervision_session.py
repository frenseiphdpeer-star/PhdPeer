"""
SupervisionSession: state machine for a supervision meeting.
States: scheduled → occurred → feedback_pending → feedback_logged
"""

from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.base import BaseModel
from app.core.state_machines import SUPERVISION_SESSION_INITIAL_STATE


class SupervisionSession(Base, BaseModel):
    """
    A scheduled supervision meeting with state lifecycle.
    state_entered_at captures timestamp for each transition.
    """

    __tablename__ = "supervision_sessions"

    supervisor_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    state = Column(String(32), nullable=False, default=SUPERVISION_SESSION_INITIAL_STATE, index=True)
    state_entered_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    scheduled_at = Column(DateTime(timezone=True), nullable=True)
    occurred_at = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)

    # Relationships
    supervisor = relationship("User", foreign_keys=[supervisor_id], back_populates="supervision_sessions_as_supervisor")
    student = relationship("User", foreign_keys=[student_id], back_populates="supervision_sessions_as_student")
