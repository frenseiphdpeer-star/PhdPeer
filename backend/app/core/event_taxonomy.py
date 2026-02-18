"""
Standardized event taxonomy for the longitudinal event store.

Event types and entity types are fixed for consistent analytics and audit.
Metadata is versioned (metadata.v) for schema evolution.

Emission by module (emit when feature exists):
- document_uploaded: documents (DocumentService)
- milestone_updated: progress (ProgressService)
- questionnaire_completed: questionnaire_draft (QuestionnaireDraftService)
- opportunity_saved: opportunity_feed (OpportunityFeedOrchestrator)
- opportunity_applied: opportunity/application module when apply action exists
- supervision_logged: supervision module when log is created
- supervision_feedback_received: supervision module when feedback is recorded
- collaboration_added: collaboration module when collaborator is added
- stage_override: progress/admin when stage is overridden
"""

from enum import Enum
from typing import Any, Dict, Optional
from uuid import UUID


class EventType(str, Enum):
    """Supported event types — all feature modules must use these."""

    DOCUMENT_UPLOADED = "document_uploaded"
    MILESTONE_UPDATED = "milestone_updated"
    SUPERVISION_LOGGED = "supervision_logged"
    SUPERVISION_FEEDBACK_RECEIVED = "supervision_feedback_received"
    QUESTIONNAIRE_COMPLETED = "questionnaire_completed"
    OPPORTUNITY_SAVED = "opportunity_saved"
    OPPORTUNITY_APPLIED = "opportunity_applied"
    COLLABORATION_ADDED = "collaboration_added"
    STAGE_OVERRIDE = "stage_override"
    ENGAGEMENT_MONTHLY_DIGEST = "engagement_monthly_digest"
    STATE_TRANSITION = "state_transition"
    TIMELINE_ADJUSTMENT_SUGGESTION = "timeline_adjustment_suggestion"
    TIMELINE_ADJUSTMENT_ACCEPTED = "timeline_adjustment_accepted"
    TIMELINE_ADJUSTMENT_REJECTED = "timeline_adjustment_rejected"


# Allowed event types (for validation)
SUPPORTED_EVENT_TYPES = {e.value for e in EventType}


def metadata_with_version(metadata: Optional[Dict[str, Any]] = None, version: int = 1) -> Dict[str, Any]:
    """Build versioned metadata dict. Ensures 'v' key for schema evolution."""
    out = dict(metadata or {})
    out["v"] = version
    return out
