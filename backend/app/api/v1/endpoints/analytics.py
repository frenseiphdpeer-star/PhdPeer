"""Analytics API endpoints."""
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.tier_access import requires_tier
from app.database import get_db
from app.models.user import SubscriptionTier, User
from app.orchestrators.analytics_orchestrator import (
    AnalyticsOrchestrator,
    AnalyticsOrchestratorError,
)
from app.repositories.analytics_repository import AnalyticsRepository
from app.repositories.timeline_repository import TimelineRepository

router = APIRouter()


@router.get("/summary")
@requires_tier(SubscriptionTier.TEAM)
async def get_analytics_summary(
    timeline_id: Optional[UUID] = Query(None, description="Optional timeline ID (uses latest if not provided)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """
    Get analytics summary for a user's timeline.

    Behavior:
    - Triggers AnalyticsOrchestrator.run() if no snapshot exists for timeline version
    - Returns latest AnalyticsSnapshot
    - Idempotent for same timeline version (returns cached snapshot)

    No side effects beyond snapshot creation.
    """
    try:
        user_id = current_user.id
        timeline_repository = TimelineRepository(db)
        analytics_repository = AnalyticsRepository(db)

        if timeline_id:
            committed_timeline = timeline_repository.get_committed_timeline_for_user(
                timeline_id=timeline_id,
                user_id=user_id,
            )
            if not committed_timeline:
                raise HTTPException(
                    status_code=404,
                    detail=f"Timeline {timeline_id} not found or not owned by user {user_id}",
                )
        else:
            committed_timeline = timeline_repository.get_latest_committed_timeline_for_user(
                user_id=user_id,
            )
            if not committed_timeline:
                raise HTTPException(
                    status_code=404,
                    detail=f"No committed timeline found for user {user_id}",
                )

        timeline_version = "1.0"
        if committed_timeline.draft_timeline_id:
            draft = timeline_repository.get_draft_timeline_by_id(
                committed_timeline.draft_timeline_id
            )
            if draft and draft.version_number:
                timeline_version = draft.version_number

        if timeline_version == "1.0" and committed_timeline.notes:
            import re
            match = re.search(r"Version\s+(\d+\.\d+)", committed_timeline.notes)
            if match:
                timeline_version = match.group(1)

        existing_snapshot = analytics_repository.get_latest_snapshot_for_user_and_version(
            user_id=user_id,
            timeline_version=timeline_version,
        )

        if existing_snapshot:
            return {
                "snapshot_id": str(existing_snapshot.id),
                "timeline_version": existing_snapshot.timeline_version,
                "created_at": existing_snapshot.created_at.isoformat(),
                "summary": existing_snapshot.summary_json,
                "from_cache": True,
            }

        orchestrator = AnalyticsOrchestrator(db, user_id)
        request_id = f"analytics-{user_id}-{committed_timeline.id}-{timeline_version}"
        orchestrator.run(
            request_id=request_id,
            user_id=user_id,
            timeline_id=committed_timeline.id,
        )

        new_snapshot = analytics_repository.get_latest_snapshot_for_user_and_version(
            user_id=user_id,
            timeline_version=timeline_version,
        )

        if not new_snapshot:
            raise HTTPException(
                status_code=500,
                detail="Failed to retrieve created snapshot",
            )

        return {
            "snapshot_id": str(new_snapshot.id),
            "timeline_version": new_snapshot.timeline_version,
            "created_at": new_snapshot.created_at.isoformat(),
            "summary": new_snapshot.summary_json,
            "from_cache": False,
        }

    except AnalyticsOrchestratorError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}",
        )
