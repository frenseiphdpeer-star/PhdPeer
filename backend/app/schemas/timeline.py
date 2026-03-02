"""
Timeline Pydantic schemas.

These models define the OpenAPI contract for all timeline endpoints.
The frontend TypeScript types in lib/types/timeline.ts must stay in sync
with these definitions.
"""
from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enums – exposed in the OpenAPI schema for frontend codegen
# ---------------------------------------------------------------------------

class StageType(str, Enum):
    """Classification of a timeline stage."""

    LITERATURE_REVIEW = "literature_review"
    METHODOLOGY = "methodology"
    DATA_COLLECTION = "data_collection"
    ANALYSIS = "analysis"
    WRITING = "writing"
    DEFENSE_PREPARATION = "defense_preparation"
    REVISION = "revision"
    PUBLICATION = "publication"
    COURSEWORK = "coursework"
    FIELDWORK = "fieldwork"
    OTHER = "other"


class StageStatus(str, Enum):
    """Current progress status of a stage."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    DELAYED = "delayed"


class DeliverableType(str, Enum):
    """Type of deliverable associated with a milestone."""

    PAPER = "paper"
    PRESENTATION = "presentation"
    DATASET = "dataset"
    CODE = "code"
    THESIS_CHAPTER = "thesis_chapter"
    PROPOSAL = "proposal"
    REVIEW = "review"
    REPORT = "report"
    DEFENSE = "defense"
    OTHER = "other"


class MilestoneState(str, Enum):
    """State-machine state for a milestone."""

    UPCOMING = "upcoming"
    ACTIVE = "active"
    COMPLETED = "completed"
    DELAYED = "delayed"


class SuggestionStatus(str, Enum):
    """Status of a timeline adjustment suggestion."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class SuggestionReason(str, Enum):
    """Trigger reason for an adjustment suggestion."""

    MILESTONE_DELAY = "milestone_delay"
    SUPERVISION_INACTIVITY = "supervision_inactivity"
    WRITING_STAGNATION = "writing_stagnation"


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class GenerateTimelineRequest(BaseModel):
    baseline_id: UUID
    title: Optional[str] = None


class UpdateMilestoneRequest(BaseModel):
    is_completed: bool


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class DurationEstimate(BaseModel):
    """Per-stage duration estimate (planned vs actual)."""

    stage_id: UUID
    estimated_months: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class Dependency(BaseModel):
    """Directed dependency edge between two stages or milestones."""

    from_id: str = Field(..., alias="from")
    to_id: str = Field(..., alias="to")

    model_config = ConfigDict(populate_by_name=True)


class TimelineStageOut(BaseModel):
    """A single stage within a timeline."""

    id: UUID
    title: str
    description: Optional[str] = None
    stage_type: Optional[StageType] = None
    stage_order: int
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    duration_months: Optional[int] = None
    status: StageStatus = StageStatus.NOT_STARTED
    notes: Optional[str] = None
    confidence: Optional[float] = Field(
        None, ge=0, le=100, description="AI confidence score 0–100"
    )

    model_config = ConfigDict(from_attributes=True)


class TimelineMilestoneOut(BaseModel):
    """A single milestone within a stage."""

    id: UUID
    title: str
    description: Optional[str] = None
    deliverable_type: Optional[DeliverableType] = None
    is_critical: bool = False
    is_completed: bool = False
    milestone_order: int
    target_date: Optional[date] = None
    actual_completion_date: Optional[date] = None
    state: MilestoneState = MilestoneState.UPCOMING
    notes: Optional[str] = None
    stage_id: UUID = Field(..., description="Parent stage ID")

    model_config = ConfigDict(from_attributes=True)


class TimelineResponse(BaseModel):
    """
    Full timeline payload – the canonical response contract.

    Frontend ``TimelineResponse`` in ``lib/types/timeline.ts`` mirrors this.
    """

    timeline_id: UUID
    baseline_id: UUID
    title: str
    description: Optional[str] = None
    stages: list[TimelineStageOut]
    milestones: list[TimelineMilestoneOut]
    dependencies: list[Dependency] = []
    durations: list[DurationEstimate] = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class GenerateTimelineResponse(BaseModel):
    """Response after generating a draft timeline."""

    timeline_id: UUID
    baseline_id: UUID
    draft_timeline_id: UUID


class TimelineSuggestionOut(BaseModel):
    """A timeline adjustment suggestion."""

    id: UUID
    committed_timeline_id: UUID
    reason: SuggestionReason
    title: str
    message: str
    suggestion_payload: dict
    status: SuggestionStatus
    responded_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
