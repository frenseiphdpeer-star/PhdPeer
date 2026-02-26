"""
Models Package

Imports all SQLAlchemy models for application use.
"""

from app.database import Base
from app.models.base import BaseModel
from app.models.user import User, UserRole, SubscriptionTier
from app.models.document_artifact import DocumentArtifact
from app.models.baseline import Baseline
from app.models.draft_timeline import DraftTimeline
from app.models.committed_timeline import CommittedTimeline
from app.models.timeline_stage import TimelineStage
from app.models.timeline_milestone import TimelineMilestone
from app.models.progress_event import ProgressEvent, ProgressEventType
from app.models.journey_assessment import JourneyAssessment
from app.models.idempotency import IdempotencyKey, DecisionTrace, EvidenceBundle
from app.models.timeline_edit_history import TimelineEditHistory
from app.models.questionnaire_draft import QuestionnaireDraft, QuestionnaireVersion
from app.models.analytics_snapshot import AnalyticsSnapshot
from app.models.feedback_record import FeedbackRecord
from app.models.audit_log import AuditLog
from app.models.document_stage_suggestion import DocumentStageSuggestion
from app.models.engagement_event import EngagementEvent
from app.models.user_opportunity import UserOpportunity
from app.models.writing_version import WritingVersion
from app.models.supervision_session import SupervisionSession
from app.models.timeline_adjustment_suggestion import TimelineAdjustmentSuggestion
from app.models.supervisor_assignment import SupervisorAssignment
from app.models.opportunity import (
    OpportunityCatalog,
    OpportunityFeedSnapshot,
    OpportunityFeedItem,
)
from app.models.risk_fusion import RiskWeightConfig, RiskAssessmentSnapshot
from app.models.scoring_config import ScoringConfig

__all__ = [
    'Base',
    'BaseModel',
    'User',
    'UserRole',
    'SubscriptionTier',
    'DocumentArtifact',
    'Baseline',
    'DraftTimeline',
    'CommittedTimeline',
    'TimelineStage',
    'TimelineMilestone',
    'ProgressEvent',
    'ProgressEventType',
    'JourneyAssessment',
    'IdempotencyKey',
    'DecisionTrace',
    'EvidenceBundle',
    'TimelineEditHistory',
    'QuestionnaireDraft',
    'QuestionnaireVersion',
    'AnalyticsSnapshot',
    'FeedbackRecord',
    'AuditLog',
    'DocumentStageSuggestion',
    'EngagementEvent',
    'UserOpportunity',
    'WritingVersion',
    'SupervisionSession',
    'TimelineAdjustmentSuggestion',
    'SupervisorAssignment',
    'OpportunityCatalog',
    'OpportunityFeedSnapshot',
    'OpportunityFeedItem',
    'RiskWeightConfig',
    'RiskAssessmentSnapshot',
    'ScoringConfig',
]

# Ensure all models are imported for Alembic to detect them
# This is necessary for automatic migration generation
