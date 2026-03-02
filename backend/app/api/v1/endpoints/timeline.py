"""
Timeline API endpoints.

All responses use Pydantic models from ``app.schemas.timeline`` so that
FastAPI generates a complete OpenAPI schema.  The frontend TypeScript
types in ``lib/types/timeline.ts`` must mirror these models.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
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
from app.schemas.timeline import (
    DurationEstimate,
    GenerateTimelineRequest,
    GenerateTimelineResponse,
    StageStatus,
    TimelineMilestoneOut,
    TimelineResponse,
    TimelineStageOut,
    UpdateMilestoneRequest,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _stage_to_schema(s: TimelineStage) -> TimelineStageOut:
    return TimelineStageOut(
        id=s.id,
        title=s.title,
        description=s.description,
        stage_type=s.notes and _infer_stage_type(s.title),
        stage_order=s.stage_order,
        start_date=s.start_date,
        end_date=s.end_date,
        duration_months=s.duration_months,
        status=_normalise_status(s.status),
        notes=s.notes,
        confidence=_extract_confidence(s.notes),
    )


def _milestone_to_schema(m: TimelineMilestone) -> TimelineMilestoneOut:
    return TimelineMilestoneOut(
        id=m.id,
        title=m.title,
        description=m.description,
        deliverable_type=m.deliverable_type,
        is_critical=m.is_critical,
        is_completed=m.is_completed,
        milestone_order=m.milestone_order,
        target_date=m.target_date,
        actual_completion_date=m.actual_completion_date,
        state=getattr(m, "state", None) or ("completed" if m.is_completed else "upcoming"),
        notes=m.notes,
        stage_id=m.timeline_stage_id,
    )


def _normalise_status(raw: str) -> StageStatus:
    try:
        return StageStatus(raw.lower().replace(" ", "_"))
    except ValueError:
        return StageStatus.NOT_STARTED


_STAGE_TYPE_KEYWORDS = {
    "literature": "literature_review",
    "methodology": "methodology",
    "data collection": "data_collection",
    "analysis": "analysis",
    "writing": "writing",
    "defense": "defense_preparation",
    "revision": "revision",
    "publication": "publication",
    "coursework": "coursework",
    "fieldwork": "fieldwork",
}


def _infer_stage_type(title: str) -> str | None:
    lower = title.lower()
    for keyword, stage_type in _STAGE_TYPE_KEYWORDS.items():
        if keyword in lower:
            return stage_type
    return None


def _extract_confidence(notes: str | None) -> float | None:
    if not notes or "Confidence:" not in notes:
        return None
    try:
        part = notes.split("Confidence:")[-1].strip().split()[0]
        return float(part) * 100
    except (ValueError, IndexError):
        return None


def _build_durations(stages: list[TimelineStage]) -> list[DurationEstimate]:
    return [
        DurationEstimate(
            stage_id=s.id,
            estimated_months=s.duration_months,
            start_date=s.start_date,
            end_date=s.end_date,
        )
        for s in stages
        if s.duration_months is not None or s.start_date is not None
    ]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/generate",
    response_model=GenerateTimelineResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a draft timeline from a baseline",
)
def generate_timeline(
    body: GenerateTimelineRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GenerateTimelineResponse:
    orch = TimelineOrchestrator(db, user_id=current_user.id)
    try:
        result = orch.generate(
            request_id=f"tl_{str(body.baseline_id).replace('-', '')[:16]}",
            baseline_id=body.baseline_id,
            user_id=current_user.id,
            title=body.title,
        )
        tl = result.get("timeline", {})
        return GenerateTimelineResponse(
            timeline_id=UUID(str(tl["id"])),
            baseline_id=body.baseline_id,
            draft_timeline_id=UUID(str(tl["id"])),
        )
    except TimelineOrchestratorError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get(
    "/{baseline_id}",
    response_model=TimelineResponse,
    summary="Get the full timeline (stages + milestones) for a baseline",
)
def get_timeline(
    baseline_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TimelineResponse:
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Timeline not found")

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

    return TimelineResponse(
        timeline_id=draft.id,
        baseline_id=draft.baseline_id,
        title=draft.title,
        description=draft.description,
        stages=[_stage_to_schema(s) for s in stages],
        milestones=[_milestone_to_schema(m) for m in milestones],
        dependencies=[],
        durations=_build_durations(stages),
        created_at=draft.created_at,
        updated_at=draft.updated_at,
    )


@router.get(
    "/{baseline_id}/stages",
    response_model=list[TimelineStageOut],
    summary="List stages for a baseline's timeline",
)
def get_timeline_stages(
    baseline_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[TimelineStageOut]:
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Timeline not found")

    stages = (
        db.query(TimelineStage)
        .filter(TimelineStage.draft_timeline_id == draft.id)
        .order_by(TimelineStage.stage_order)
        .all()
    )
    return [_stage_to_schema(s) for s in stages]


@router.get(
    "/{baseline_id}/milestones",
    response_model=list[TimelineMilestoneOut],
    summary="List milestones for a baseline's timeline",
)
def get_timeline_milestones(
    baseline_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[TimelineMilestoneOut]:
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Timeline not found")

    stage_ids = [
        s.id
        for s in db.query(TimelineStage.id)
        .filter(TimelineStage.draft_timeline_id == draft.id)
        .all()
    ]

    milestones = (
        db.query(TimelineMilestone)
        .filter(TimelineMilestone.timeline_stage_id.in_(stage_ids))
        .order_by(TimelineMilestone.timeline_stage_id, TimelineMilestone.milestone_order)
        .all()
    ) if stage_ids else []

    return [_milestone_to_schema(m) for m in milestones]


@router.patch(
    "/milestones/{milestone_id}",
    response_model=TimelineMilestoneOut,
    summary="Update a milestone (e.g. mark completed)",
)
def update_milestone(
    milestone_id: UUID,
    body: UpdateMilestoneRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TimelineMilestoneOut:
    milestone = db.query(TimelineMilestone).filter(TimelineMilestone.id == milestone_id).first()
    if not milestone:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Milestone not found")

    # Verify ownership through stage → draft_timeline → user
    stage = db.query(TimelineStage).filter(TimelineStage.id == milestone.timeline_stage_id).first()
    if not stage:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent stage not found")

    draft = None
    if stage.draft_timeline_id:
        draft = db.query(DraftTimeline).filter(DraftTimeline.id == stage.draft_timeline_id).first()

    if not draft or draft.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your milestone")

    milestone.is_completed = body.is_completed
    if body.is_completed:
        milestone.state = "completed"
        from datetime import date as _date
        milestone.actual_completion_date = _date.today()
    else:
        milestone.state = "active"
        milestone.actual_completion_date = None

    db.commit()
    db.refresh(milestone)

    return _milestone_to_schema(milestone)
