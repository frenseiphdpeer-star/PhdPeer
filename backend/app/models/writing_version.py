"""
WritingVersion: version of a writing artifact with state machine.
States: draft → revised → submitted → archived
"""

from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.base import BaseModel
from app.core.state_machines import WRITING_VERSION_INITIAL_STATE


class WritingVersion(Base, BaseModel):
    """
    A version of a writing artifact (e.g. paper, chapter) with explicit state.
    state_entered_at updated on each valid transition.
    """

    __tablename__ = "writing_versions"

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_artifact_id = Column(
        UUID(as_uuid=True),
        ForeignKey("document_artifacts.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    title = Column(String(255), nullable=False)
    version_label = Column(String(64), nullable=True)  # e.g. "v1", "draft-2"
    state = Column(String(32), nullable=False, default=WRITING_VERSION_INITIAL_STATE, index=True)
    state_entered_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    user = relationship("User", back_populates="writing_versions")
    document_artifact = relationship("DocumentArtifact", back_populates="writing_versions")
