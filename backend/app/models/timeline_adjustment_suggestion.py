"""
TimelineAdjustmentSuggestion: bidirectional feedback from signals to user.

When signals indicate milestone delay, supervision inactivity, or writing stagnation,
the system generates a suggestion. User may accept or reject; timeline is never auto-modified.
"""

from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.base import BaseModel


# Suggestion trigger reasons (from signals)
REASON_MILESTONE_DELAY = "milestone_delay"
REASON_SUPERVISION_INACTIVITY = "supervision_inactivity"
REASON_WRITING_STAGNATION = "writing_stagnation"

REASONS = {REASON_MILESTONE_DELAY, REASON_SUPERVISION_INACTIVITY, REASON_WRITING_STAGNATION}

# User response status
STATUS_PENDING = "pending"
STATUS_ACCEPTED = "accepted"
STATUS_REJECTED = "rejected"


class TimelineAdjustmentSuggestion(Base, BaseModel):
    """
    A suggested timeline adjustment generated from signals. User-controlled:
    no milestones are auto-modified; user accepts or rejects the suggestion.
    """

    __tablename__ = "timeline_adjustment_suggestions"

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    committed_timeline_id = Column(
        UUID(as_uuid=True),
        ForeignKey("committed_timelines.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reason = Column(String(64), nullable=False, index=True)  # milestone_delay | supervision_inactivity | writing_stagnation
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)  # Human-readable suggestion text
    suggestion_payload = Column(JSONB, nullable=False, server_default="{}")  # e.g. delayed_milestone_ids, recommended_actions
    status = Column(String(32), nullable=False, default=STATUS_PENDING, index=True)
    responded_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User", back_populates="timeline_adjustment_suggestions")
    committed_timeline = relationship("CommittedTimeline", back_populates="timeline_adjustment_suggestions")
