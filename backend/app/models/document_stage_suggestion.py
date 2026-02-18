"""
DocumentStageSuggestion: stores stage inference per document and accept/override state.

Immutable classification data: suggested_stage, confidence_score, reasoning_tokens
are never overwritten. Override adds override_stage, override_reason and
system_suggested_stage (frozen copy) without removing the original suggestion.
"""

from sqlalchemy import Column, String, Text, Float, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.base import BaseModel


class DocumentStageSuggestion(Base, BaseModel):
    """
    One row per document: engine suggestion + optional accept/override.

    - suggested_stage: from stage classification engine (never overwritten).
    - confidence_score, reasoning_tokens: internal inference output.
    - accepted_stage: set when user accepts (equals suggested_stage).
    - override_stage / override_reason: set when user overrides.
    - system_suggested_stage: copy of suggested_stage at override time (audit).
    """

    __tablename__ = "document_stage_suggestions"

    document_artifact_id = Column(
        UUID(as_uuid=True),
        ForeignKey("document_artifacts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        unique=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Engine output (immutable)
    suggested_stage = Column(String(128), nullable=False)
    confidence_score = Column(Float, nullable=False)
    reasoning_tokens = Column(JSONB, nullable=False, server_default="[]")  # list of strings

    # User action: accept
    accepted_stage = Column(String(128), nullable=True)

    # User action: override (historical data preserved)
    override_stage = Column(String(128), nullable=True)
    override_reason = Column(Text, nullable=True)
    system_suggested_stage = Column(String(128), nullable=True)  # frozen at override time

    # Relationships
    document_artifact = relationship("DocumentArtifact", back_populates="stage_suggestion")
    user = relationship("User", back_populates="document_stage_suggestions")
