"""
UserOpportunity: per-user opportunity state machine.
States: saved → applied → rejected|accepted → outcome_logged
"""

from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.base import BaseModel
from app.core.state_machines import OPPORTUNITY_INITIAL_STATE


class UserOpportunity(Base, BaseModel):
    """
    Tracks a user's interaction with an opportunity (from catalog).
    State and state_entered_at updated only via valid transitions.
    """

    __tablename__ = "user_opportunities"

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    opportunity_id = Column(
        UUID(as_uuid=True),
        ForeignKey("opportunities_catalog.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    state = Column(String(32), nullable=False, default=OPPORTUNITY_INITIAL_STATE, index=True)
    state_entered_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    user = relationship("User", back_populates="user_opportunities")
    opportunity = relationship("OpportunityCatalog", back_populates="user_opportunities")
