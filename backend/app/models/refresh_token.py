"""Refresh token model for JWT token rotation."""
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.base import BaseModel


class RefreshToken(Base, BaseModel):
    __tablename__ = "refresh_tokens"

    token = Column(String, unique=True, index=True, nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    revoked = Column(Boolean, default=False, nullable=False)
    replaced_by = Column(String, nullable=True)

    user = relationship("User", backref="refresh_tokens", lazy="selectin")

    @property
    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at

    @property
    def is_usable(self) -> bool:
        return not self.revoked and not self.is_expired
