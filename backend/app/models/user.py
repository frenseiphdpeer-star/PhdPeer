"""User model."""
from enum import Enum
from sqlalchemy import Column, String, Boolean, Enum as SqlEnum
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.base import BaseModel


class UserRole(str, Enum):
    """Supported platform roles."""

    RESEARCHER = "researcher"
    SUPERVISOR = "supervisor"
    INSTITUTION_ADMIN = "institution_admin"
    ENTERPRISE_CLIENT = "enterprise_client"


class SubscriptionTier(str, Enum):
    """Supported subscription tiers."""

    FREE = "free"
    TEAM = "team"
    INSTITUTIONAL = "institutional"


class User(Base, BaseModel):
    __tablename__ = "users"

    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=True)
    full_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)
    oauth_provider = Column(String, nullable=True, index=True)
    oauth_provider_id = Column(String, nullable=True)
    role = Column(
        SqlEnum(UserRole, name="user_role", create_constraint=False, native_enum=False),
        default=UserRole.RESEARCHER,
        nullable=False,
        index=True,
    )
    subscription_tier = Column(
        SqlEnum(SubscriptionTier, name="subscription_tier", create_constraint=False, native_enum=False),
        default=SubscriptionTier.FREE,
        nullable=False,
        index=True,
    )
    institution = Column(String, nullable=True)
    field_of_study = Column(String, nullable=True)
    
    # Relationships
    document_artifacts = relationship(
        "DocumentArtifact",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    baselines = relationship(
        "Baseline",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    draft_timelines = relationship(
        "DraftTimeline",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    committed_timelines = relationship(
        "CommittedTimeline",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    progress_events = relationship(
        "ProgressEvent",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    journey_assessments = relationship(
        "JourneyAssessment",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    questionnaire_drafts = relationship(
        "QuestionnaireDraft",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    opportunity_feeds = relationship(
        "OpportunityFeedSnapshot",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    analytics_snapshots = relationship(
        "AnalyticsSnapshot",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    document_stage_suggestions = relationship(
        "DocumentStageSuggestion",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    engagement_events = relationship(
        "EngagementEvent",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    user_opportunities = relationship(
        "UserOpportunity",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    writing_versions = relationship(
        "WritingVersion",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    supervision_sessions_as_supervisor = relationship(
        "SupervisionSession",
        foreign_keys="[SupervisionSession.supervisor_id]",
        back_populates="supervisor",
        cascade="all, delete-orphan",
    )
    supervision_sessions_as_student = relationship(
        "SupervisionSession",
        foreign_keys="[SupervisionSession.student_id]",
        back_populates="student",
        cascade="all, delete-orphan",
    )
    timeline_adjustment_suggestions = relationship(
        "TimelineAdjustmentSuggestion",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    # RBAC: as supervisor, assigned students
    assigned_students = relationship(
        "SupervisorAssignment",
        back_populates="supervisor",
        foreign_keys="[SupervisorAssignment.supervisor_id]",
        cascade="all, delete-orphan",
    )
    # RBAC: as student, assigned supervisor(s)
    assigned_supervisors = relationship(
        "SupervisorAssignment",
        back_populates="student",
        foreign_keys="[SupervisorAssignment.student_id]",
        cascade="all, delete-orphan",
    )