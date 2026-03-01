"""Timeline API endpoints."""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.draft_timeline import DraftTimeline
from app.models.timeline_stage import TimelineStage
from app.models.timeline_milestone import TimelineMilestone
from app.orchestrators.timeline_orchestrator import (
    TimelineOrchestrator,
    TimelineOrchestratorError,
)

router = APIRouter()


class GenerateTimelineRequest(BaseModel):
    baseline_id: str
    title: str | None = None


@router.post("/generate")
def generate_timeline(
    body: GenerateTimelineRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Generate a draft timeline from a baseline."""
    orch = TimelineOrchestrator(db, user_id=current_user.id)
    try:
        result = orch.generate(
            request_id=f"tl_{body.baseline_id.replace('-', '')[:16]}",
            baseline_id=UUID(body.baseline_id),
            user_id=current_user.id,
            title=body.title,
        )
        tl = result.get("timeline", {})
        return {
            "timeline_id": tl.get("id"),
            "baseline_id": body.baseline_id,
            "draft_timeline_id": tl.get("id"),
        }
    except TimelineOrchestratorError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{baseline_id}")
def get_timeline(
    baseline_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Get timeline (stages, milestones) for a baseline."""
    draft = (
        db.query(DraftTimeline)
        .filter(
            DraftTimeline.baseline_id == baseline_id,
            DraftTimeline.user_id == current_user.id,
        )
        .order_by(DraftTimeline.created_at.desc())
        .first()
    )
    if not draft:
        raise HTTPException(status_code=404, detail="Timeline not found")

    stages = (
        db.query(TimelineStage)
        .filter(TimelineStage.draft_timeline_id == draft.id)
        .order_by(TimelineStage.stage_order)
        .all()
    )
    stage_ids = [s.id for s in stages]
    milestones = (
        db.query(TimelineMilestone)
        .filter(TimelineMilestone.timeline_stage_id.in_(stage_ids))
        .order_by(TimelineMilestone.timeline_stage_id, TimelineMilestone.milestone_order)
        .all()
    ) if stage_ids else []

    stage_list = [
        {
            "id": str(s.id),
            "title": s.title,
            "description": s.description,
            "stage_order": s.stage_order,
            "duration_months": s.duration_months,
            "status": s.status,
            "notes": s.notes,
            "confidence": _extract_confidence(s.notes),
        }
        for s in stages
    ]
    milestone_list = [
        {
            "id": str(m.id),
            "title": m.title,
            "description": m.description,
            "deliverable_type": m.deliverable_type,
            "is_critical": m.is_critical,
            "is_completed": m.is_completed,
            "milestone_order": m.milestone_order,
            "notes": m.notes,
            "stage_id": str(m.timeline_stage_id),
        }
        for m in milestones
    ]

    return {
        "stages": stage_list,
        "milestones": milestone_list,
        "dependencies": [],
        "durations": {},
    }


def _extract_confidence(notes: str | None) -> float | None:
    if not notes or "Confidence:" not in notes:
        return None
    try:
        part = notes.split("Confidence:")[-1].strip().split()[0]
        return float(part) * 100
    except (ValueError, IndexError):
        return None
