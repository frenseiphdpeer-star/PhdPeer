"""
Engagement events: reminders (inactivity flags) and monthly digest snapshots.

Consumed by dashboard/API; no UI logic in backend. Feeds engagement signals into intelligence layer.
"""

from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.base import BaseModel


# Engagement event kinds (reminders + digest)
ENGAGEMENT_KIND_LOW_ENGAGEMENT = "low_engagement"
ENGAGEMENT_KIND_WRITING_INACTIVITY = "writing_inactivity"
ENGAGEMENT_KIND_SUPERVISION_DRIFT = "supervision_drift"
ENGAGEMENT_KIND_MONTHLY_DIGEST = "monthly_digest"

ENGAGEMENT_KINDS = {
    ENGAGEMENT_KIND_LOW_ENGAGEMENT,
    ENGAGEMENT_KIND_WRITING_INACTIVITY,
    ENGAGEMENT_KIND_SUPERVISION_DRIFT,
    ENGAGEMENT_KIND_MONTHLY_DIGEST,
}


class EngagementEvent(Base, BaseModel):
    """
    Reminder or digest entry for engagement monitoring.

    - Reminders: kind in (low_engagement, writing_inactivity, supervision_drift),
      message = reminder text, payload = optional extra (e.g. last_activity_at).
    - Digest: kind = monthly_digest, payload = summary counts (milestones, documents, etc.).
    acknowledged_at set when user/dashboard marks as seen (optional).
    """

    __tablename__ = "engagement_events"

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind = Column(String(64), nullable=False, index=True)  # low_engagement | writing_inactivity | supervision_drift | monthly_digest
    message = Column(Text, nullable=True)  # Reminder title/message; null for digest
    payload = Column(JSONB, nullable=False, server_default="{}")  # Extra data (digest summary, last_activity_at, etc.)
    triggered_at = Column(DateTime(timezone=True), nullable=False)  # When the rule fired or digest was generated
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User", back_populates="engagement_events")
