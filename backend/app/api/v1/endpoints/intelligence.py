"""
Intelligence signals API: interpretability layer only.

All signals are returned with evidence (contributing event_ids, time window),
explanation (human-readable), and recommendation. Signals cannot be displayed
without this payload; evidence is traceable back to raw longitudinal events.
"""

from typing import Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.security import get_current_user
from app.core.data_visibility import can_access_user_data
from app.models.user import User
from app.services.intelligence_signals_service import IntelligenceSignalsService
from app.core.interpretability import require_explanation_payload

router = APIRouter()


class EvidenceResponse(BaseModel):
    contributing_event_ids: List[str]
    time_window: dict


class InterpretableSignalResponse(BaseModel):
    signal_type: str
    value: Any  # score, flags, or structured value per signal type
    evidence: EvidenceResponse
    explanation: str
    recommendation: str


@router.get("/signals", response_model=List[InterpretableSignalResponse])
def get_intelligence_signals(
    user_id: Optional[UUID] = Query(None, description="User ID (default: current user; must be visible)"),
    lookback_days: int = Query(90, ge=1, le=365, description="Days of events to consider"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[InterpretableSignalResponse]:
    """
    Get all intelligence signals with full interpretability payload.

    Each signal includes:
    - evidence: contributing_event_ids (traceable to longitudinal_events), time_window
    - explanation: why the signal was generated
    - recommendation: suggested user action

    Signals are never returned without this payload. Target user_id must be visible to current user (RBAC).
    """
    target_id = user_id or current_user.id
    if not can_access_user_data(db, current_user, target_id):
        raise HTTPException(status_code=403, detail="Not allowed to view this user's signals")
    svc = IntelligenceSignalsService(db)
    # get_all_signals returns only for_display() dicts (evidence + explanation + recommendation)
    raw = svc.get_all_signals(target_id, lookback_days=lookback_days)
    out = []
    for item in raw:
        # Enforce: every item must have evidence, explanation, recommendation (already guaranteed by service)
        if not item.get("evidence") or not item.get("explanation") or not item.get("recommendation"):
            continue
        out.append(
            InterpretableSignalResponse(
                signal_type=item["signal_type"],
                value=item["value"],
                evidence=EvidenceResponse(
                    contributing_event_ids=item["evidence"]["contributing_event_ids"],
                    time_window=item["evidence"]["time_window"],
                ),
                explanation=item["explanation"],
                recommendation=item["recommendation"],
            )
        )
    return out


@router.get("/signals/{signal_type}", response_model=InterpretableSignalResponse)
def get_single_signal(
    signal_type: str,
    user_id: Optional[UUID] = Query(None),
    lookback_days: int = Query(90, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InterpretableSignalResponse:
    """
    Get one intelligence signal by type with full interpretability payload.
    signal_type: continuity_index | dropout_risk_signal | supervisor_engagement_alert | opportunity_match_score
    """
    from app.core.interpretability import (
        SIGNAL_CONTINUITY_INDEX,
        SIGNAL_DROPOUT_RISK,
        SIGNAL_SUPERVISOR_ENGAGEMENT,
        SIGNAL_OPPORTUNITY_MATCH,
    )
    target_id = user_id or current_user.id
    if not can_access_user_data(db, current_user, target_id):
        raise HTTPException(status_code=403, detail="Not allowed to view this user's signals")
    if signal_type not in (SIGNAL_CONTINUITY_INDEX, SIGNAL_DROPOUT_RISK, SIGNAL_SUPERVISOR_ENGAGEMENT, SIGNAL_OPPORTUNITY_MATCH):
        raise HTTPException(status_code=404, detail="Unknown signal type")
    svc = IntelligenceSignalsService(db)
    lookback = 45 if signal_type == SIGNAL_SUPERVISOR_ENGAGEMENT else lookback_days
    sig = None
    if signal_type == SIGNAL_CONTINUITY_INDEX:
        sig = svc.continuity_index(target_id, lookback_days=lookback)
    elif signal_type == SIGNAL_DROPOUT_RISK:
        sig = svc.dropout_risk_signal(target_id, lookback_days=lookback)
    elif signal_type == SIGNAL_SUPERVISOR_ENGAGEMENT:
        sig = svc.supervisor_engagement_alert(target_id, lookback_days=lookback)
    elif signal_type == SIGNAL_OPPORTUNITY_MATCH:
        sig = svc.opportunity_match_score(target_id, lookback_days=lookback)
    try:
        payload = require_explanation_payload(sig)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    return InterpretableSignalResponse(
        signal_type=payload["signal_type"],
        value=payload["value"],
        evidence=EvidenceResponse(
            contributing_event_ids=payload["evidence"]["contributing_event_ids"],
            time_window=payload["evidence"]["time_window"],
        ),
        explanation=payload["explanation"],
        recommendation=payload["recommendation"],
    )
