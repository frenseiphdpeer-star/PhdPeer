"""
Intelligence signals with interpretability: evidence, explanation, recommendation.

Each signal is computed from longitudinal events; evidence lists contributing event_ids
and time window so outputs are traceable to raw events. Signals cannot be displayed
without the explanation payload.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.longitudinal_event import LongitudinalEvent
from app.core.event_taxonomy import EventType
from app.core.interpretability import (
    Evidence,
    ExplanationPayload,
    InterpretableSignal,
    TimeWindow,
    SIGNAL_CONTINUITY_INDEX,
    SIGNAL_DROPOUT_RISK,
    SIGNAL_SUPERVISOR_ENGAGEMENT,
    SIGNAL_OPPORTUNITY_MATCH,
)
from app.services.engagement_engine import EngagementEngine


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _days_ago(dt: Optional[datetime]) -> Optional[int]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (_utcnow() - dt).days


class IntelligenceSignalsService:
    """
    Produces interpretable intelligence signals from longitudinal event store.
    Every signal includes evidence (event_ids, time_window), explanation, recommendation.
    """

    DEFAULT_LOOKBACK_DAYS = 90

    def __init__(self, db: Session) -> None:
        self.db = db

    def _events_in_window(
        self,
        user_id: UUID,
        window_start: datetime,
        window_end: datetime,
        event_types: Optional[List[str]] = None,
    ) -> List[Any]:
        """Return longitudinal events in time window; optionally filter by event_type."""
        q = self.db.query(LongitudinalEvent).filter(
            LongitudinalEvent.user_id == user_id,
            LongitudinalEvent.timestamp >= window_start,
            LongitudinalEvent.timestamp <= window_end,
        )
        if event_types:
            q = q.filter(LongitudinalEvent.event_type.in_(event_types))
        return q.order_by(LongitudinalEvent.timestamp.asc()).all()

    def continuity_index(
        self,
        user_id: UUID,
        lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    ) -> Optional[InterpretableSignal]:
        """
        Continuity index: regularity of activity over the window.
        Value in [0, 1]; higher = more regular activity. Evidence = event_ids in window.
        """
        window_end = _utcnow()
        window_start = window_end - timedelta(days=lookback_days)
        events = self._events_in_window(user_id, window_start, window_end)
        event_ids = [e.event_id for e in events]

        if not events:
            value = 0.0
            explanation = (
                f"No activity events in the last {lookback_days} days. "
                "Continuity is zero when there is no recorded activity in the time window."
            )
            recommendation = "Log progress, upload a document, or complete a questionnaire to build continuity."
        else:
            # Simple continuity: number of weeks with at least one event / total weeks
            weeks = max(1, lookback_days // 7)
            by_week: Dict[int, int] = {}
            for e in events:
                ts = e.timestamp.replace(tzinfo=timezone.utc) if e.timestamp.tzinfo is None else e.timestamp
                week_key = int((ts - window_start).total_seconds() // (7 * 24 * 3600))
                by_week[week_key] = by_week.get(week_key, 0) + 1
            value = round(len(by_week) / weeks, 4)
            value = min(1.0, value)
            explanation = (
                f"Activity on {len(by_week)} of the last {weeks} weeks ({len(events)} events total). "
                "Continuity index reflects how regularly you engage within the time window."
            )
            recommendation = "Maintain weekly activity (e.g. progress updates or document uploads) to keep continuity high."

        return InterpretableSignal(
            signal_type=SIGNAL_CONTINUITY_INDEX,
            value=value,
            explanation_payload=ExplanationPayload(
                evidence=Evidence(
                    contributing_event_ids=event_ids,
                    time_window=TimeWindow(start=window_start, end=window_end),
                ),
                explanation=explanation,
                recommendation=recommendation,
            ),
        )

    def dropout_risk_signal(
        self,
        user_id: UUID,
        lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    ) -> Optional[InterpretableSignal]:
        """
        Dropout risk: derived from long inactivity and lack of progress/supervision.
        Evidence = event_ids in window used to assess risk.
        """
        window_end = _utcnow()
        window_start = window_end - timedelta(days=lookback_days)
        events = self._events_in_window(user_id, window_start, window_end)
        event_ids = [e.event_id for e in events]

        engine = EngagementEngine(self.db)
        signals = engine.get_engagement_signals(user_id)
        low_engagement = signals.get("low_engagement", False)
        writing_inactive = signals.get("writing_inactivity", False)
        supervision_drift = signals.get("supervision_drift", False)

        risk_score = 0.0
        if low_engagement:
            risk_score += 0.4
        if writing_inactive:
            risk_score += 0.3
        if supervision_drift:
            risk_score += 0.3
        risk_score = round(min(1.0, risk_score), 4)

        reasons = []
        if low_engagement:
            reasons.append("no recent activity")
        if writing_inactive:
            reasons.append("no recent writing/document activity")
        if supervision_drift:
            reasons.append("no recent supervision contact")
        explanation = (
            f"Risk assessment based on {len(events)} events in the last {lookback_days} days. "
            + ("Risk factors: " + "; ".join(reasons) + "." if reasons else "No strong risk factors in the window.")
        )
        recommendation = (
            "Upload a document, log progress, or schedule a supervision meeting to reduce dropout risk."
            if risk_score > 0.3
            else "Continue current engagement level; consider logging milestones when completed."
        )

        return InterpretableSignal(
            signal_type=SIGNAL_DROPOUT_RISK,
            value={"score": risk_score, "flags": {"low_engagement": low_engagement, "writing_inactivity": writing_inactive, "supervision_drift": supervision_drift}},
            explanation_payload=ExplanationPayload(
                evidence=Evidence(
                    contributing_event_ids=event_ids,
                    time_window=TimeWindow(start=window_start, end=window_end),
                ),
                explanation=explanation,
                recommendation=recommendation,
            ),
        )

    def supervisor_engagement_alert(
        self,
        user_id: UUID,
        lookback_days: int = 45,
    ) -> Optional[InterpretableSignal]:
        """
        Supervisor engagement: alert when supervision events are absent or sparse.
        Evidence = supervision-related event_ids in window.
        """
        window_end = _utcnow()
        window_start = window_end - timedelta(days=lookback_days)
        supervision_types = [
            EventType.SUPERVISION_LOGGED.value,
            EventType.SUPERVISION_FEEDBACK_RECEIVED.value,
        ]
        events = self._events_in_window(user_id, window_start, window_end, event_types=supervision_types)
        event_ids = [e.event_id for e in events]

        alert = len(events) == 0
        value = {"alert": alert, "supervision_event_count": len(events)}

        if alert:
            explanation = (
                f"No supervision events (meetings or feedback) in the last {lookback_days} days. "
                "Regular supervision contact supports progress and reduces isolation."
            )
            recommendation = "Schedule a supervision meeting and log it, or request feedback from your supervisor."
        else:
            explanation = (
                f"Found {len(events)} supervision-related event(s) in the last {lookback_days} days. "
                "Alert is off when there is recent supervision activity."
            )
            recommendation = "Keep logging supervision meetings and feedback to maintain visibility."

        return InterpretableSignal(
            signal_type=SIGNAL_SUPERVISOR_ENGAGEMENT,
            value=value,
            explanation_payload=ExplanationPayload(
                evidence=Evidence(
                    contributing_event_ids=event_ids,
                    time_window=TimeWindow(start=window_start, end=window_end),
                ),
                explanation=explanation,
                recommendation=recommendation,
            ),
        )

    def opportunity_match_score(
        self,
        user_id: UUID,
        opportunity_id: Optional[UUID] = None,
        lookback_days: int = 30,
    ) -> Optional[InterpretableSignal]:
        """
        Opportunity match: relevance of opportunities based on profile/timeline.
        Evidence = event_ids that inform context (e.g. opportunity_saved, document_uploaded, milestone_updated).
        When opportunity_id is provided, value can be a single score; otherwise a summary.
        """
        window_end = _utcnow()
        window_start = window_end - timedelta(days=lookback_days)
        # Events that inform opportunity matching: profile activity and opportunity actions
        context_types = [
            EventType.OPPORTUNITY_SAVED.value,
            EventType.OPPORTUNITY_APPLIED.value,
            EventType.DOCUMENT_UPLOADED.value,
            EventType.MILESTONE_UPDATED.value,
        ]
        events = self._events_in_window(user_id, window_start, window_end, event_types=context_types)
        event_ids = [e.event_id for e in events]

        # Placeholder: real score would come from OpportunityRelevanceEngine for a specific opportunity
        # Here we return a summary signal with interpretability
        value = {
            "context_events_in_window": len(events),
            "opportunity_id": str(opportunity_id) if opportunity_id else None,
        }
        explanation = (
            f"Opportunity match context is based on {len(events)} relevant events in the last {lookback_days} days "
            "(e.g. documents uploaded, milestones updated, opportunities saved or applied). "
            "Scores depend on discipline, stage, and timeline alignment."
        )
        recommendation = "Update your progress and documents so opportunity recommendations stay relevant; apply to high-match opportunities when ready."

        return InterpretableSignal(
            signal_type=SIGNAL_OPPORTUNITY_MATCH,
            value=value,
            explanation_payload=ExplanationPayload(
                evidence=Evidence(
                    contributing_event_ids=event_ids,
                    time_window=TimeWindow(start=window_start, end=window_end),
                ),
                explanation=explanation,
                recommendation=recommendation,
            ),
        )

    def get_all_signals(
        self,
        user_id: UUID,
        lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    ) -> List[Dict[str, Any]]:
        """
        Return all four signals with full interpretability payload.
        Only returns signals that have evidence, explanation, and recommendation (enforced).
        """
        results = []
        try:
            sig = self.continuity_index(user_id, lookback_days=lookback_days)
            if sig is not None:
                results.append(sig.for_display())
        except Exception:
            pass
        try:
            sig = self.dropout_risk_signal(user_id, lookback_days=lookback_days)
            if sig is not None:
                results.append(sig.for_display())
        except Exception:
            pass
        try:
            sig = self.supervisor_engagement_alert(user_id, lookback_days=45)
            if sig is not None:
                results.append(sig.for_display())
        except Exception:
            pass
        try:
            sig = self.opportunity_match_score(user_id, lookback_days=lookback_days)
            if sig is not None:
                results.append(sig.for_display())
        except Exception:
            pass
        return results
