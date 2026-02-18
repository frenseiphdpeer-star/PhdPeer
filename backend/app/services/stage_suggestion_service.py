"""
Stage suggestion service: accept/override and timeline regeneration.

- Accept: set accepted_stage = suggested_stage.
- Override: set override_stage, override_reason, system_suggested_stage; emit stage_override; trigger regen.
Historical classification data (suggested_stage, reasoning_tokens) is never deleted.
"""

from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.document_stage_suggestion import DocumentStageSuggestion
from app.models.document_artifact import DocumentArtifact
from app.models.user import User
from app.models.baseline import Baseline
from app.core.event_taxonomy import EventType
from app.services.event_store import emit_event
from app.orchestrators.timeline_orchestrator import TimelineOrchestrator


class StageSuggestionServiceError(Exception):
    pass


class StageSuggestionService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_suggestion(self, document_id: UUID, user_id: UUID) -> Optional[DocumentStageSuggestion]:
        """Get stage suggestion for document; verify ownership."""
        doc = self.db.query(DocumentArtifact).filter(
            DocumentArtifact.id == document_id,
            DocumentArtifact.user_id == user_id,
        ).first()
        if not doc:
            return None
        return self.db.query(DocumentStageSuggestion).filter(
            DocumentStageSuggestion.document_artifact_id == document_id,
        ).first()

    def accept_stage(self, document_id: UUID, user_id: UUID) -> Optional[DocumentStageSuggestion]:
        """
        Accept the suggested stage (accepted_stage = suggested_stage).
        Does not delete historical data.
        """
        suggestion = self.get_suggestion(document_id, user_id)
        if not suggestion:
            return None
        suggestion.accepted_stage = suggestion.suggested_stage
        self.db.add(suggestion)
        self.db.commit()
        self.db.refresh(suggestion)
        return suggestion

    def override_stage(
        self,
        document_id: UUID,
        user_id: UUID,
        override_stage: str,
        override_reason: str,
    ) -> Optional[DocumentStageSuggestion]:
        """
        Override with user-chosen stage. Logs stage_override event, stores
        override_reason and system_suggested_stage, does not delete historical data.
        Triggers timeline regeneration (new draft from user's baseline if any).
        """
        suggestion = self.get_suggestion(document_id, user_id)
        if not suggestion:
            return None
        user = self.db.query(User).filter(User.id == user_id).first()
        suggestion.override_stage = override_stage
        suggestion.override_reason = override_reason
        suggestion.system_suggested_stage = suggestion.suggested_stage
        self.db.add(suggestion)
        self.db.flush()
        emit_event(
            self.db,
            user_id=user_id,
            role=getattr(user, "role", "researcher"),
            event_type=EventType.STAGE_OVERRIDE.value,
            source_module="stage_classification",
            entity_type="document_stage_suggestion",
            entity_id=suggestion.id,
            metadata={
                "document_id": str(document_id),
                "system_suggested_stage": suggestion.suggested_stage,
                "override_stage": override_stage,
                "override_reason": override_reason[:500],
            },
        )
        self.db.commit()
        self.db.refresh(suggestion)
        self._trigger_timeline_regeneration(user_id)
        return suggestion

    def _trigger_timeline_regeneration(self, user_id: UUID) -> None:
        """
        Create a new draft timeline from the user's latest baseline, if any.
        Does not delete existing timelines; adds a new draft for user to commit.
        """
        baseline = (
            self.db.query(Baseline)
            .filter(Baseline.user_id == user_id)
            .order_by(Baseline.created_at.desc())
            .first()
        )
        if not baseline:
            return
        try:
            orch = TimelineOrchestrator(self.db, user_id=user_id)
            orch.create_draft_timeline(
                baseline_id=baseline.id,
                user_id=user_id,
            )
        except Exception:
            # Log but do not fail override
            pass
