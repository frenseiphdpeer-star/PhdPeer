"""TimelineMilestone model."""
from sqlalchemy import Column, String, Text, Integer, Date, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.base import BaseModel
from app.core.state_machines import MILESTONE_INITIAL_STATE


class TimelineMilestone(Base, BaseModel):
    """
    TimelineMilestone model representing specific milestones within stages.
    
    Milestones are concrete deliverables or achievements within a stage,
    like "Complete literature review", "Submit paper", etc.
    
    Attributes:
        timeline_stage_id: Reference to the parent stage
        title: Milestone title
        description: Milestone description
        milestone_order: Order within the stage
        target_date: Target completion date
        actual_completion_date: Actual completion date
        is_completed: Whether milestone is completed
        is_critical: Whether this is a critical milestone
        deliverable_type: Type of deliverable (paper, presentation, etc.)
        notes: Additional notes
    """
    
    __tablename__ = "timeline_milestones"
    
    timeline_stage_id = Column(
        UUID(as_uuid=True),
        ForeignKey("timeline_stages.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    milestone_order = Column(Integer, nullable=False)
    target_date = Column(Date, nullable=True)
    actual_completion_date = Column(Date, nullable=True)
    is_completed = Column(Boolean, default=False, nullable=False)
    is_critical = Column(Boolean, default=False, nullable=False)
    deliverable_type = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    # State machine: upcoming → active → completed | delayed
    state = Column(String(32), nullable=False, default=MILESTONE_INITIAL_STATE, index=True)
    state_entered_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    timeline_stage = relationship("TimelineStage", back_populates="milestones")
    progress_events = relationship(
        "ProgressEvent",
        back_populates="milestone",
        cascade="all, delete-orphan"
    )
