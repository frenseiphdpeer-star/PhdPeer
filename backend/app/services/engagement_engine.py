"""
Engagement engine: monitors user activity from longitudinal event store.

Rules (configurable thresholds, no hard-coded UI logic):
- No event for 14 days → low_engagement
- No writing event for 30 days → writing_inactivity
- No supervision event for 45 days → supervision_drift

Trigger: create engagement_event entry with reminder message; dashboard consumes via API.
Monthly digest: aggregate counts from event store, store snapshot (engagement_event + longitudinal event).
Engagement signals exposed for intelligence layer.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.longitudinal_event import LongitudinalEvent
from app.models.engagement_event import (
    EngagementEvent,
    ENGAGEMENT_KIND_LOW_ENGAGEMENT,
    ENGAGEMENT_KIND_WRITING_INACTIVITY,
    ENGAGEMENT_KIND_SUPERVISION_DRIFT,
    ENGAGEMENT_KIND_MONTHLY_DIGEST,
)
from app.models.user import User
from app.core.event_taxonomy import EventType
from app.services.event_store import emit_event


# Inactivity thresholds (days)
DAYS_ANY_ACTIVITY = 14
DAYS_WRITING_ACTIVITY = 30
DAYS_SUPERVISION_ACTIVITY = 45

# Event types that count as "writing" (document uploads, etc.)
WRITING_EVENT_TYPES = {EventType.DOCUMENT_UPLOADED.value}

# Event types that count as "supervision"
SUPERVISION_EVENT_TYPES = {
    EventType.SUPERVISION_LOGGED.value,
    EventType.SUPERVISION_FEEDBACK_RECEIVED.value,
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class EngagementEngine:
    """
    Evaluates inactivity rules from longitudinal events and creates engagement_events.
    No UI logic; data-only reminders and digests for dashboard/intelligence.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_last_activity_timestamps(self, user_id: UUID) -> Dict[str, Optional[datetime]]:
        """
        Return last timestamp for: any event, writing event, supervision event.
        Used by inactivity rules and by get_engagement_signals.
        """
        q_any = (
            self.db.query(func.max(LongitudinalEvent.timestamp))
            .filter(LongitudinalEvent.user_id == user_id)
        )
        last_any = q_any.scalar()

        q_writing = (
            self.db.query(func.max(LongitudinalEvent.timestamp))
            .filter(
                LongitudinalEvent.user_id == user_id,
                LongitudinalEvent.event_type.in_(WRITING_EVENT_TYPES),
            )
        )
        last_writing = q_writing.scalar()

        q_supervision = (
            self.db.query(func.max(LongitudinalEvent.timestamp))
            .filter(
                LongitudinalEvent.user_id == user_id,
                LongitudinalEvent.event_type.in_(SUPERVISION_EVENT_TYPES),
            )
        )
        last_supervision = q_supervision.scalar()

        return {
            "last_any_activity": last_any,
            "last_writing_activity": last_writing,
            "last_supervision_activity": last_supervision,
        }

    def get_engagement_signals(self, user_id: UUID) -> Dict[str, Any]:
        """
        Return engagement flags and last-activity timestamps for intelligence layer.
        No UI logic; consumers (e.g. opportunity engine, notifications) decide how to use.
        """
        ts = self.get_last_activity_timestamps(user_id)
        now = _utcnow()
        last_any = ts["last_any_activity"]
        last_writing = ts["last_writing_activity"]
        last_supervision = ts["last_supervision_activity"]

        def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
            if dt is None:
                return None
            return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt

        last_any = _ensure_utc(last_any)
        last_writing = _ensure_utc(last_writing)
        last_supervision = _ensure_utc(last_supervision)

        def days_ago(dt: Optional[datetime]) -> Optional[int]:
            if dt is None:
                return None
            delta = now - dt
            return delta.days

        low_engagement = last_any is None or (days_ago(last_any) or 0) >= DAYS_ANY_ACTIVITY
        writing_inactivity = last_writing is None or (days_ago(last_writing) or 0) >= DAYS_WRITING_ACTIVITY
        supervision_drift = last_supervision is None or (days_ago(last_supervision) or 0) >= DAYS_SUPERVISION_ACTIVITY

        return {
            "user_id": str(user_id),
            "low_engagement": low_engagement,
            "writing_inactivity": writing_inactivity,
            "supervision_drift": supervision_drift,
            "last_any_activity_at": last_any.isoformat() if last_any else None,
            "last_writing_activity_at": last_writing.isoformat() if last_writing else None,
            "last_supervision_activity_at": last_supervision.isoformat() if last_supervision else None,
            "days_since_any": days_ago(last_any),
            "days_since_writing": days_ago(last_writing),
            "days_since_supervision": days_ago(last_supervision),
        }

    def _create_reminder(
        self,
        user_id: UUID,
        kind: str,
        message: str,
        payload: Dict[str, Any],
    ) -> EngagementEvent:
        entry = EngagementEvent(
            user_id=user_id,
            kind=kind,
            message=message,
            payload=payload,
            triggered_at=_utcnow(),
        )
        self.db.add(entry)
        self.db.flush()
        return entry

    def run_inactivity_detection(self, user_id: UUID) -> List[EngagementEvent]:
        """
        Evaluate inactivity rules for one user; create engagement_events for each triggered rule.
        Returns list of created reminder events (for idempotency you may want to avoid duplicates
        per day per kind; we create one per run).
        """
        signals = self.get_engagement_signals(user_id)
        created: List[EngagementEvent] = []

        if signals["low_engagement"]:
            days = signals.get("days_since_any") or DAYS_ANY_ACTIVITY
            msg = f"No activity for {days} days. Consider updating your progress or uploading a document."
            created.append(
                self._create_reminder(
                    user_id,
                    ENGAGEMENT_KIND_LOW_ENGAGEMENT,
                    msg,
                    {
                        "days_since_activity": days,
                        "last_activity_at": signals.get("last_any_activity_at"),
                    },
                )
            )

        if signals["writing_inactivity"]:
            days = signals.get("days_since_writing") or DAYS_WRITING_ACTIVITY
            msg = f"No document upload or writing-related activity for {days} days."
            created.append(
                self._create_reminder(
                    user_id,
                    ENGAGEMENT_KIND_WRITING_INACTIVITY,
                    msg,
                    {
                        "days_since_writing": days,
                        "last_writing_activity_at": signals.get("last_writing_activity_at"),
                    },
                )
            )

        if signals["supervision_drift"]:
            days = signals.get("days_since_supervision") or DAYS_SUPERVISION_ACTIVITY
            msg = f"No supervision log or feedback for {days} days. Consider logging a meeting or requesting feedback."
            created.append(
                self._create_reminder(
                    user_id,
                    ENGAGEMENT_KIND_SUPERVISION_DRIFT,
                    msg,
                    {
                        "days_since_supervision": days,
                        "last_supervision_activity_at": signals.get("last_supervision_activity_at"),
                    },
                )
            )

        return created

    def run_inactivity_detection_for_all_users(self) -> Dict[UUID, List[EngagementEvent]]:
        """Run inactivity detection for every user (e.g. from a scheduled job)."""
        user_ids = [r[0] for r in self.db.query(User.id).all()]
        result: Dict[UUID, List[EngagementEvent]] = {}
        for uid in user_ids:
            result[uid] = self.run_inactivity_detection(uid)
        return result

    def generate_monthly_digest(
        self,
        user_id: UUID,
        year: int,
        month: int,
        user_role: str = "researcher",
    ) -> Optional[EngagementEvent]:
        """
        Summarize longitudinal events for the given month; store digest as engagement_event
        and emit engagement_monthly_digest to longitudinal event store.
        """
        start = datetime(year, month, 1, tzinfo=timezone.utc)
        if month == 12:
            end = datetime(year + 1, 1, 1, tzinfo=timezone.utc) - timedelta(microseconds=1)
        else:
            end = datetime(year, month + 1, 1, tzinfo=timezone.utc) - timedelta(microseconds=1)

        q = (
            self.db.query(LongitudinalEvent.event_type, func.count(LongitudinalEvent.event_id))
            .filter(
                LongitudinalEvent.user_id == user_id,
                LongitudinalEvent.timestamp >= start,
                LongitudinalEvent.timestamp <= end,
            )
            .group_by(LongitudinalEvent.event_type)
        )
        counts = dict(q.all())

        summary = {
            "year": year,
            "month": month,
            "milestones_updated": counts.get(EventType.MILESTONE_UPDATED.value, 0),
            "documents_uploaded": counts.get(EventType.DOCUMENT_UPLOADED.value, 0),
            "supervision_logs": counts.get(EventType.SUPERVISION_LOGGED.value, 0),
            "supervision_feedback": counts.get(EventType.SUPERVISION_FEEDBACK_RECEIVED.value, 0),
            "opportunity_saved": counts.get(EventType.OPPORTUNITY_SAVED.value, 0),
            "opportunity_applied": counts.get(EventType.OPPORTUNITY_APPLIED.value, 0),
            "questionnaire_completed": counts.get(EventType.QUESTIONNAIRE_COMPLETED.value, 0),
        }

        digest_entry = EngagementEvent(
            user_id=user_id,
            kind=ENGAGEMENT_KIND_MONTHLY_DIGEST,
            message=None,
            payload=summary,
            triggered_at=_utcnow(),
        )
        self.db.add(digest_entry)
        self.db.flush()

        emit_event(
            self.db,
            user_id=user_id,
            role=user_role,
            event_type=EventType.ENGAGEMENT_MONTHLY_DIGEST.value,
            source_module="engagement_engine",
            entity_type="engagement_event",
            entity_id=digest_entry.id,
            metadata=summary,
        )
        self.db.commit()
        self.db.refresh(digest_entry)
        return digest_entry
