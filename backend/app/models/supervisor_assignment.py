"""Supervisor–student assignment for data visibility (Supervisor sees only assigned students)."""
from sqlalchemy import Column, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.base import BaseModel


class SupervisorAssignment(Base, BaseModel):
    """
    Assignment of a PhD researcher (student) to a supervisor.
    Used for RBAC: supervisors see only assigned students' risk/analytics.
    """

    __tablename__ = "supervisor_assignments"
    __table_args__ = (
        UniqueConstraint("supervisor_id", "student_id", name="uq_supervisor_student"),
    )

    supervisor_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    supervisor = relationship("User", foreign_keys=[supervisor_id])
    student = relationship("User", foreign_keys=[student_id])
