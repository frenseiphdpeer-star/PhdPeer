"""Analytics API endpoints. RBAC: Researcher (own), Supervisor (assigned students), Admin (all)."""
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.security import get_current_user, require_permission, Permission
from app.core.data_visibility import can_access_user_data
from app.orchestrators.analytics_orchestrator import (
    AnalyticsOrchestrator,
    AnalyticsOrchestratorError,
)
from app.models.user import User
from app.models.analytics_snapshot import AnalyticsSnapshot
from app.models.committed_timeline import CommittedTimeline

router = APIRouter()


@router.get("/summary")
async def get_analytics_summary(
    timeline_id: Optional[UUID] = Query(None, description="Optional timeline ID (uses latest if not provided)"),
    user_id: UUID = Query(..., description="User ID (target; must be visible to current user)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Get analytics summary for a user's timeline.
    RBAC: Researcher sees own only; Supervisor sees assigned students; Admin sees any.
    """
    if not can_access_user_data(db, current_user, user_id):
        raise HTTPException(
            status_code=403,
            detail="Not allowed to access this user's analytics",
        )
    try:
        # Get committed timeline to determine version
        if timeline_id:
            committed_timeline = db.query(CommittedTimeline).filter(
                CommittedTimeline.id == timeline_id,
                CommittedTimeline.user_id == user_id
            ).first()
            if not committed_timeline:
                raise HTTPException(
                    status_code=404,
                    detail=f"Timeline {timeline_id} not found or not owned by user {user_id}"
                )
        else:
            # #region agent log
            with open(r'd:\Frensei-Engine\.cursor\debug.log', 'a') as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"C","location":"analytics.py:58","message":"Querying for latest committed timeline","data":{"user_id":str(user_id)},"timestamp":int(__import__('time').time()*1000)}) + '\n')
            # #endregion
            # Get latest committed timeline
            committed_timeline = db.query(CommittedTimeline).filter(
                CommittedTimeline.user_id == user_id
            ).order_by(CommittedTimeline.committed_date.desc()).first()
            # #region agent log
            with open(r'd:\Frensei-Engine\.cursor\debug.log', 'a') as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"C","location":"analytics.py:63","message":"Committed timeline query result","data":{"found":committed_timeline is not None,"timeline_id":str(committed_timeline.id) if committed_timeline else None},"timestamp":int(__import__('time').time()*1000)}) + '\n')
            # #endregion
            if not committed_timeline:
                # #region agent log
                with open(r'd:\Frensei-Engine\.cursor\debug.log', 'a') as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"C","location":"analytics.py:65","message":"No committed timeline found - raising 404","data":{"user_id":str(user_id)},"timestamp":int(__import__('time').time()*1000)}) + '\n')
                # #endregion
                raise HTTPException(
                    status_code=404,
                    detail=f"No committed timeline found for user {user_id}"
                )
        
        # Extract timeline version
        # Try to get version from draft_timeline
        timeline_version = "1.0"  # Default
        if committed_timeline.draft_timeline_id:
            from app.models.draft_timeline import DraftTimeline
            draft = db.query(DraftTimeline).filter(
                DraftTimeline.id == committed_timeline.draft_timeline_id
            ).first()
            if draft and draft.version_number:
                timeline_version = draft.version_number
        
        # Try to extract from notes if not found
        if timeline_version == "1.0" and committed_timeline.notes:
            import re
            match = re.search(r'Version\s+(\d+\.\d+)', committed_timeline.notes)
            if match:
                timeline_version = match.group(1)
        
        # Check if snapshot already exists for this timeline version (idempotency)
        existing_snapshot = db.query(AnalyticsSnapshot).filter(
            AnalyticsSnapshot.user_id == user_id,
            AnalyticsSnapshot.timeline_version == timeline_version
        ).order_by(AnalyticsSnapshot.created_at.desc()).first()
        
        if existing_snapshot:
            # Return existing snapshot (idempotent)
            return {
                "snapshot_id": str(existing_snapshot.id),
                "timeline_version": existing_snapshot.timeline_version,
                "created_at": existing_snapshot.created_at.isoformat(),
                "summary": existing_snapshot.summary_json,
                "from_cache": True
            }
        
        # Generate new snapshot
        # #region agent log
        with open(r'd:\Frensei-Engine\.cursor\debug.log', 'a') as f:
            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"E","location":"analytics.py:104","message":"Starting analytics orchestrator","data":{"user_id":str(user_id),"timeline_id":str(committed_timeline.id),"timeline_version":timeline_version},"timestamp":int(__import__('time').time()*1000)}) + '\n')
        # #endregion
        orchestrator = AnalyticsOrchestrator(db, user_id)
        request_id = f"analytics-{user_id}-{committed_timeline.id}-{timeline_version}"
        result = orchestrator.run(
            request_id=request_id,
            user_id=user_id,
            timeline_id=committed_timeline.id
        )
        # #region agent log
        with open(r'd:\Frensei-Engine\.cursor\debug.log', 'a') as f:
            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"E","location":"analytics.py:111","message":"Orchestrator completed","data":{"has_result":result is not None},"timestamp":int(__import__('time').time()*1000)}) + '\n')
        # #endregion
        
        # Get the newly created snapshot
        new_snapshot = db.query(AnalyticsSnapshot).filter(
            AnalyticsSnapshot.user_id == user_id,
            AnalyticsSnapshot.timeline_version == timeline_version
        ).order_by(AnalyticsSnapshot.created_at.desc()).first()
        
        if not new_snapshot:
            raise HTTPException(
                status_code=500,
                detail="Failed to retrieve created snapshot"
            )
        
        response_data = {
            "snapshot_id": str(new_snapshot.id),
            "timeline_version": new_snapshot.timeline_version,
            "created_at": new_snapshot.created_at.isoformat(),
            "summary": new_snapshot.summary_json,
            "from_cache": False
        }
        # #region agent log
        with open(r'd:\Frensei-Engine\.cursor\debug.log', 'a') as f:
            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"F","location":"analytics.py:130","message":"Returning response","data":{"has_summary":"summary" in response_data,"summary_type":type(response_data.get("summary")).__name__},"timestamp":int(__import__('time').time()*1000)}) + '\n')
        # #endregion
        return response_data
        
    except AnalyticsOrchestratorError as e:
        # #region agent log
        with open(r'd:\Frensei-Engine\.cursor\debug.log', 'a') as f:
            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"E","location":"analytics.py:133","message":"AnalyticsOrchestratorError caught","data":{"error":str(e)},"timestamp":int(__import__('time').time()*1000)}) + '\n')
        # #endregion
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except Exception as e:
        # #region agent log
        with open(r'd:\Frensei-Engine\.cursor\debug.log', 'a') as f:
            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"D","location":"analytics.py:138","message":"Unexpected exception","data":{"error_type":type(e).__name__,"error":str(e)},"timestamp":int(__import__('time').time()*1000)}) + '\n')
        # #endregion
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )
