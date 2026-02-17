"""
Models Package

Imports all SQLAlchemy models for application use.
"""

from app.models.base import BaseModel
from app.models.user import User
from app.models.document_artifact import DocumentArtifact
from app.models.baseline import Baseline
from app.models.draft_timeline import DraftTimeline
from app.models.committed_timeline import CommittedTimeline
from app.models.timeline_stage import TimelineStage
from app.models.timeline_milestone import TimelineMilestone
from app.models.progress_event import ProgressEvent
from app.models.journey_assessment import JourneyAssessment
from app.models.idempotency import IdempotencyKey, DecisionTrace, EvidenceBundle
from app.models.timeline_edit_history import TimelineEditHistory
from app.models.questionnaire_draft import QuestionnaireDraft, QuestionnaireVersion
from app.models.analytics_snapshot import AnalyticsSnapshot
from app.models.opportunity import (
    OpportunityCatalog,
    OpportunityFeedSnapshot,
    OpportunityFeedItem,
)
from app.models.supervisor_assignment import SupervisorAssignment
from app.models.longitudinal_event import LongitudinalEvent

# Import Base from database for Alembic
from app.database import Base

__all__ = [
    'Base',
    'BaseModel',
    'User',
    'DocumentArtifact',
    'Baseline',
    'DraftTimeline',
    'CommittedTimeline',
    'TimelineStage',
    'TimelineMilestone',
    'ProgressEvent',
    'JourneyAssessment',
    'IdempotencyKey',
    'DecisionTrace',
    'EvidenceBundle',
    'TimelineEditHistory',
    'QuestionnaireDraft',
    'QuestionnaireVersion',
    'AnalyticsSnapshot',
    'OpportunityCatalog',
    'OpportunityFeedSnapshot',
    'OpportunityFeedItem',
    'SupervisorAssignment',
    'LongitudinalEvent',
]

# Ensure all models are imported for Alembic to detect them
# This is necessary for automatic migration generation
