"""
Bidirectional feedback: generate timeline_adjustment_suggestions from signals.

When signals indicate milestone delay, supervision inactivity, or writing stagnation,
the system generates a suggestion. User can accept or reject; milestones are never auto-modified.
Logs: suggestion_event, acceptance_event, rejection_event.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.timeline_adjustment_suggestion import (
    TimelineAdjustmentSuggestion,
    REASON_MILESTONE_DELAY,
    REASON_SUPERVISION_INACTIVITY,
    REASON_WRITING_STAGNATION,
    STATUS_PENDING,
    STATUS_ACCEPTED,
    STATUS_REJECTED,
)
from app.models.committed_timeline import CommittedTimeline
from app.models.user import User
from app.core.event_taxonomy import EventType
from app.services.event_store import emit_event
from app.services.engagement_engine import EngagementEngine
from app.services.progress_service import ProgressService


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimelineFeedbackServiceError(Exception):
    pass


class TimelineFeedbackService:
    """
    Generates timeline adjustment suggestions from signals. Does not auto-modify milestones.
    User accepts or rejects; all actions are logged to the event store.
    """

    # Avoid duplicate suggestions for same reason within days
    SUGGESTION_COOLDOWN_DAYS = 7

    def __init__(self, db: Session) -> None:
        self.db = db
        self.engagement_engine = EngagementEngine(db)
        self.progress_service = ProgressService(db)

    def _has_recent_suggestion(
        self,
        user_id: UUID,
        committed_timeline_id: UUID,
        reason: str,
    ) -> bool:
        """True if a pending or recently responded suggestion exists for this reason."""
        from datetime import timedelta
        cutoff = _utcnow() - timedelta(days=self.SUGGESTION_COOLDOWN_DAYS)
        q = self.db.query(TimelineAdjustmentSuggestion).filter(
            TimelineAdjustmentSuggestion.user_id == user_id,
            TimelineAdjustmentSuggestion.committed_timeline_id == committed_timeline_id,
            TimelineAdjustmentSuggestion.reason == reason,
            TimelineAdjustmentSuggestion.created_at >= cutoff,
        )
        return q.first() is not None

    def generate_suggestions_for_user(
        self,
        user_id: UUID,
        committed_timeline_id: Optional[UUID] = None,
    ) -> List[TimelineAdjustmentSuggestion]:
        """
        Evaluate signals and create timeline_adjustment_suggestions where applicable.
        Does not modify any milestones. Emits suggestion_event for each created suggestion.
        """
        # Resolve timeline
        if committed_timeline_id:
            timeline = self.db.query(CommittedTimeline).filter(
                CommittedTimeline.id == committed_timeline_id,
                CommittedTimeline.user_id == user_id,
            ).first()
        else:
            timeline = self.db.query(CommittedTimeline).filter(
                CommittedTimeline.user_id == user_id,
            ).order_by(CommittedTimeline.committed_date.desc()).first()
        if not timeline:
            return []

        user = self.db.query(User).filter(User.id == user_id).first()
        role = getattr(user, "role", "researcher") if user else "researcher"
        created: List[TimelineAdjustmentSuggestion] = []

        # 1) Milestone delay
        delayed = self.progress_service.get_all_delayed_milestones(timeline.id, include_completed=False)
        if delayed and not self._has_recent_suggestion(user_id, timeline.id, REASON_MILESTONE_DELAY):
            suggestion = TimelineAdjustmentSuggestion(
                user_id=user_id,
                committed_timeline_id=timeline.id,
                reason=REASON_MILESTONE_DELAY,
                title="Milestone delay detected",
                message=(
                    f"You have {len(delayed)} delayed milestone(s). "
                    "Consider reviewing target dates or marking progress. The timeline has not been changed."
                ),
                suggestion_payload={
                    "delayed_milestone_count": len(delayed),
                    "delayed_milestone_ids": [str(m["milestone_id"]) for m in delayed[:20] if m.get("milestone_id")],
                    "recommended_action": "Review timeline and update target dates or log completion as appropriate.",
                },
                status=STATUS_PENDING,
            )
            self.db.add(suggestion)
            self.db.flush()
            emit_event(
                self.db,
                user_id=user_id,
                role=role,
                event_type=EventType.TIMELINE_ADJUSTMENT_SUGGESTION.value,
                source_module="timeline_feedback",
                entity_type="timeline_adjustment_suggestion",
                entity_id=suggestion.id,
                metadata={
                    "reason": REASON_MILESTONE_DELAY,
                    "committed_timeline_id": str(timeline.id),
                    "delayed_count": len(delayed),
                },
            )
            created.append(suggestion)

        # 2) Supervision inactivity
        signals = self.engagement_engine.get_engagement_signals(user_id)
        if signals.get("supervision_drift") and not self._has_recent_suggestion(user_id, timeline.id, REASON_SUPERVISION_INACTIVITY):
            suggestion = TimelineAdjustmentSuggestion(
                user_id=user_id,
                committed_timeline_id=timeline.id,
                reason=REASON_SUPERVISION_INACTIVITY,
                title="Supervision gap",
                message=(
                    "No recent supervision meeting or feedback has been logged. "
                    "Consider scheduling a meeting and logging it. Your timeline has not been changed."
                ),
                suggestion_payload={
                    "days_since_supervision": signals.get("days_since_supervision"),
                    "recommended_action": "Schedule a supervision meeting and log it in the system.",
                },
                status=STATUS_PENDING,
            )
            self.db.add(suggestion)
            self.db.flush()
            emit_event(
                self.db,
                user_id=user_id,
                role=role,
                event_type=EventType.TIMELINE_ADJUSTMENT_SUGGESTION.value,
                source_module="timeline_feedback",
                entity_type="timeline_adjustment_suggestion",
                entity_id=suggestion.id,
                metadata={
                    "reason": REASON_SUPERVISION_INACTIVITY,
                    "committed_timeline_id": str(timeline.id),
                },
            )
            created.append(suggestion)

        # 3) Writing stagnation
        if signals.get("writing_inactivity") and not self._has_recent_suggestion(user_id, timeline.id, REASON_WRITING_STAGNATION):
            suggestion = TimelineAdjustmentSuggestion(
                user_id=user_id,
                committed_timeline_id=timeline.id,
                reason=REASON_WRITING_STAGNATION,
                title="Prolonged writing inactivity",
                message=(
                    "No document upload or writing-related activity has been recorded recently. "
                    "Consider uploading a draft or logging writing progress. Your timeline has not been changed."
                ),
                suggestion_payload={
                    "days_since_writing": signals.get("days_since_writing"),
                    "recommended_action": "Upload a document or log writing progress to keep your timeline aligned.",
                },
                status=STATUS_PENDING,
            )
            self.db.add(suggestion)
            self.db.flush()
            emit_event(
                self.db,
                user_id=user_id,
                role=role,
                event_type=EventType.TIMELINE_ADJUSTMENT_SUGGESTION.value,
                source_module="timeline_feedback",
                entity_type="timeline_adjustment_suggestion",
                entity_id=suggestion.id,
                metadata={
                    "reason": REASON_WRITING_STAGNATION,
                    "committed_timeline_id": str(timeline.id),
                },
            )
            created.append(suggestion)

        return created

    def accept_suggestion(
        self,
        suggestion_id: UUID,
        user_id: UUID,
    ) -> Optional[TimelineAdjustmentSuggestion]:
        """
        Mark suggestion as accepted. Does not auto-modify milestones; timeline remains user-controlled.
        Logs acceptance_event.
        """
        suggestion = self.db.query(TimelineAdjustmentSuggestion).filter(
            TimelineAdjustmentSuggestion.id == suggestion_id,
            TimelineAdjustmentSuggestion.user_id == user_id,
            TimelineAdjustmentSuggestion.status == STATUS_PENDING,
        ).first()
        if not suggestion:
            return None
        user = self.db.query(User).filter(User.id == user_id).first()
        role = getattr(user, "role", "researcher") if user else "researcher"
        suggestion.status = STATUS_ACCEPTED
        suggestion.responded_at = _utcnow()
        self.db.add(suggestion)
        self.db.flush()
        emit_event(
            self.db,
            user_id=user_id,
            role=role,
            event_type=EventType.TIMELINE_ADJUSTMENT_ACCEPTED.value,
            source_module="timeline_feedback",
            entity_type="timeline_adjustment_suggestion",
            entity_id=suggestion.id,
            metadata={
                "reason": suggestion.reason,
                "committed_timeline_id": str(suggestion.committed_timeline_id),
                "responded_at": suggestion.responded_at.isoformat(),
            },
        )
        self.db.commit()
        self.db.refresh(suggestion)
        return suggestion

    def reject_suggestion(
        self,
        suggestion_id: UUID,
        user_id: UUID,
    ) -> Optional[TimelineAdjustmentSuggestion]:
        """Mark suggestion as rejected. Logs rejection_event."""
        suggestion = self.db.query(TimelineAdjustmentSuggestion).filter(
            TimelineAdjustmentSuggestion.id == suggestion_id,
            TimelineAdjustmentSuggestion.user_id == user_id,
            TimelineAdjustmentSuggestion.status == STATUS_PENDING,
        ).first()
        if not suggestion:
            return None
        user = self.db.query(User).filter(User.id == user_id).first()
        role = getattr(user, "role", "researcher") if user else "researcher"
        suggestion.status = STATUS_REJECTED
        suggestion.responded_at = _utcnow()
        self.db.add(suggestion)
        self.db.flush()
        emit_event(
            self.db,
            user_id=user_id,
            role=role,
            event_type=EventType.TIMELINE_ADJUSTMENT_REJECTED.value,
            source_module="timeline_feedback",
            entity_type="timeline_adjustment_suggestion",
            entity_id=suggestion.id,
            metadata={
                "reason": suggestion.reason,
                "committed_timeline_id": str(suggestion.committed_timeline_id),
                "responded_at": suggestion.responded_at.isoformat(),
            },
        )
        self.db.commit()
        self.db.refresh(suggestion)
        return suggestion
