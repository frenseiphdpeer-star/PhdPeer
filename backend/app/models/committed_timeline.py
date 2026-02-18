"""CommittedTimeline model."""
from sqlalchemy import Column, String, Text, Date, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.base import BaseModel


class CommittedTimeline(Base, BaseModel):
    """
    CommittedTimeline model representing a finalized, committed timeline.
    
    Committed timelines are the official, active timelines that users
    track their progress against.
    
    Attributes:
        user_id: Reference to the user
        baseline_id: Reference to the baseline
        draft_timeline_id: Reference to the draft timeline this was created from
        title: Timeline title
        description: Timeline description
        committed_date: Date when timeline was committed
        target_completion_date: Target completion date
        notes: Additional notes
    """
    
    __tablename__ = "committed_timelines"
    
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    baseline_id = Column(
        UUID(as_uuid=True),
        ForeignKey("baselines.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    draft_timeline_id = Column(
        UUID(as_uuid=True),
        ForeignKey("draft_timelines.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    committed_date = Column(Date, nullable=False)
    target_completion_date = Column(Date, nullable=True)
    notes = Column(Text, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="committed_timelines")
    baseline = relationship("Baseline")
    draft_timeline = relationship("DraftTimeline")
    timeline_stages = relationship(
        "TimelineStage",
        back_populates="committed_timeline",
        cascade="all, delete-orphan",
        foreign_keys="TimelineStage.committed_timeline_id"
    )
    timeline_adjustment_suggestions = relationship(
        "TimelineAdjustmentSuggestion",
        back_populates="committed_timeline",
        cascade="all, delete-orphan",
    )
