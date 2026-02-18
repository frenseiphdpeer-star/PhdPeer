"""
Institutional analytics: aggregation only, admin-only.

Constraints:
- No exposure of document content (DocumentArtifact is never queried here).
- No raw questionnaire answers visible to admin (QuestionnaireDraft content not used).
- Aggregation threshold (AGGREGATION_THRESHOLD) applied to prevent single-user inference;
  cells with count below threshold are suppressed.
Data sources: longitudinal events (event_type/counts only), engagement signals, timeline/stage counts.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.user import User
from app.models.longitudinal_event import LongitudinalEvent
from app.models.committed_timeline import CommittedTimeline
from app.models.timeline_stage import TimelineStage
from app.models.timeline_milestone import TimelineMilestone
from app.core.event_taxonomy import EventType
from app.services.engagement_engine import EngagementEngine
from app.services.progress_service import ProgressService


# Minimum count in a cell to be reported; smaller cells are suppressed to prevent inference
AGGREGATION_THRESHOLD = 5

LOOKBACK_DAYS = 90
SUPERVISION_LOOKBACK_DAYS = 45

SUPERVISION_EVENT_TYPES = [
    EventType.SUPERVISION_LOGGED.value,
    EventType.SUPERVISION_FEEDBACK_RECEIVED.value,
]


def _apply_threshold(buckets: Dict[str, int], threshold: int = AGGREGATION_THRESHOLD) -> Dict[str, Any]:
    """Suppress buckets below threshold; return only safe aggregates and suppressed count."""
    safe = {k: v for k, v in buckets.items() if v >= threshold}
    suppressed_count = sum(v for k, v in buckets.items() if v < threshold)
    return {
        "distribution": safe,
        "suppressed_cells": suppressed_count,
        "threshold": threshold,
    }


def _continuity_for_user(db: Session, user_id: UUID, lookback_days: int) -> float:
    """Compute continuity index (0-1) from longitudinal events; no content."""
    window_end = datetime.now(timezone.utc)
    window_start = window_end - timedelta(days=lookback_days)
    events = (
        db.query(LongitudinalEvent)
        .filter(
            LongitudinalEvent.user_id == user_id,
            LongitudinalEvent.timestamp >= window_start,
            LongitudinalEvent.timestamp <= window_end,
        )
        .all()
    )
    if not events:
        return 0.0
    weeks = max(1, lookback_days // 7)
    by_week: Dict[int, bool] = {}
    for e in events:
        ts = e.timestamp.replace(tzinfo=timezone.utc) if e.timestamp.tzinfo is None else e.timestamp
        week_key = int((ts - window_start).total_seconds() // (7 * 24 * 3600))
        by_week[week_key] = True
    return min(1.0, len(by_week) / weeks)


def _risk_segment_for_user(engagement_engine: EngagementEngine, user_id: UUID) -> str:
    """Segment: low, medium, high from engagement flags only (no content)."""
    s = engagement_engine.get_engagement_signals(user_id)
    low = s.get("low_engagement", False)
    writing = s.get("writing_inactivity", False)
    super_ = s.get("supervision_drift", False)
    n = sum([low, writing, super_])
    if n == 0:
        return "low"
    if n == 1:
        return "medium"
    return "high"


class InstitutionalAnalyticsService:
    """
    Aggregated institutional analytics. No PII, no document/questionnaire content.
    All outputs respect AGGREGATION_THRESHOLD.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.engagement_engine = EngagementEngine(db)
        self.progress_service = ProgressService(db)

    def cohort_continuity_distribution(
        self,
        lookback_days: int = LOOKBACK_DAYS,
    ) -> Dict[str, Any]:
        """
        Distribution of continuity index across researchers (bucketed).
        No document or questionnaire content used.
        """
        researcher_ids = [r[0] for r in self.db.query(User.id).filter(User.role == "researcher").all()]
        buckets: Dict[str, int] = {
            "0.0-0.2": 0,
            "0.2-0.4": 0,
            "0.4-0.6": 0,
            "0.6-0.8": 0,
            "0.8-1.0": 0,
        }
        for uid in researcher_ids:
            c = _continuity_for_user(self.db, uid, lookback_days)
            if c < 0.2:
                buckets["0.0-0.2"] += 1
            elif c < 0.4:
                buckets["0.2-0.4"] += 1
            elif c < 0.6:
                buckets["0.4-0.6"] += 1
            elif c < 0.8:
                buckets["0.6-0.8"] += 1
            else:
                buckets["0.8-1.0"] += 1
        return {
            "cohort_size": len(researcher_ids),
            "lookback_days": lookback_days,
            **_apply_threshold(buckets),
        }

    def risk_segmentation_summary(
        self,
    ) -> Dict[str, Any]:
        """
        Count of researchers in each risk segment (low/medium/high).
        Based on engagement signals only; no content.
        """
        researcher_ids = [r[0] for r in self.db.query(User.id).filter(User.role == "researcher").all()]
        buckets: Dict[str, int] = {"low": 0, "medium": 0, "high": 0}
        for uid in researcher_ids:
            seg = _risk_segment_for_user(self.engagement_engine, uid)
            buckets[seg] += 1
        return {
            "cohort_size": len(researcher_ids),
            **_apply_threshold(buckets),
        }

    def supervisor_engagement_averages(
        self,
        lookback_days: int = SUPERVISION_LOOKBACK_DAYS,
    ) -> Dict[str, Any]:
        """
        Average supervision event count per researcher and % with at least one.
        Uses event counts only; no content.
        """
        researcher_ids = [r[0] for r in self.db.query(User.id).filter(User.role == "researcher").all()]
        window_end = datetime.now(timezone.utc)
        window_start = window_end - timedelta(days=lookback_days)
        counts: List[int] = []
        for uid in researcher_ids:
            n = (
                self.db.query(func.count(LongitudinalEvent.event_id))
                .filter(
                    LongitudinalEvent.user_id == uid,
                    LongitudinalEvent.event_type.in_(SUPERVISION_EVENT_TYPES),
                    LongitudinalEvent.timestamp >= window_start,
                    LongitudinalEvent.timestamp <= window_end,
                )
                .scalar()
                or 0
            )
            counts.append(n)
        total = len(counts)
        with_at_least_one = sum(1 for c in counts if c >= 1)
        avg = sum(counts) / total if total else 0.0
        return {
            "cohort_size": total,
            "lookback_days": lookback_days,
            "average_supervision_events_per_researcher": round(avg, 2),
            "percent_with_at_least_one_supervision_event": round(100.0 * with_at_least_one / total, 1) if total else 0,
        }

    def stage_distribution_counts(
        self,
    ) -> Dict[str, Any]:
        """
        Count of stages by stage title (committed timelines only).
        No document or questionnaire data.
        """
        rows = (
            self.db.query(TimelineStage.title, func.count(TimelineStage.id))
            .filter(TimelineStage.committed_timeline_id.isnot(None))
            .group_by(TimelineStage.title)
            .all()
        )
        buckets = {str(title): count for title, count in rows}
        return {
            "stage_counts": _apply_threshold(buckets),
        }

    def timeline_delay_frequency(
        self,
    ) -> Dict[str, Any]:
        """
        Distribution of timelines by number of overdue milestones (0, 1-2, 3+).
        Uses progress aggregates only; no content.
        """
        timelines = self.db.query(CommittedTimeline).filter(CommittedTimeline.user_id.isnot(None)).all()
        buckets: Dict[str, int] = {"0_overdue": 0, "1_2_overdue": 0, "3_plus_overdue": 0}
        for tl in timelines:
            progress = self.progress_service.get_timeline_progress(tl.id)
            if not progress or not progress.get("has_data"):
                continue
            overdue = progress.get("overdue_milestones", 0) or 0
            if overdue == 0:
                buckets["0_overdue"] += 1
            elif overdue <= 2:
                buckets["1_2_overdue"] += 1
            else:
                buckets["3_plus_overdue"] += 1
        return {
            "timelines_with_data": sum(buckets.values()),
            **_apply_threshold(buckets),
        }
