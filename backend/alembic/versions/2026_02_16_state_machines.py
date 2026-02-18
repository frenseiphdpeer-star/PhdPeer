"""state machines: user_opportunities, supervision_sessions, writing_versions, milestone state

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-02-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_opportunities",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("opportunity_id", sa.UUID(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False, server_default="saved"),
        sa.Column("state_entered_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities_catalog.id"], ondelete="CASCADE"),
    )
    op.create_index(op.f("ix_user_opportunities_opportunity_id"), "user_opportunities", ["opportunity_id"], unique=False)
    op.create_index(op.f("ix_user_opportunities_state"), "user_opportunities", ["state"], unique=False)
    op.create_index(op.f("ix_user_opportunities_user_id"), "user_opportunities", ["user_id"], unique=False)

    op.create_table(
        "supervision_sessions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("supervisor_id", sa.UUID(), nullable=False),
        sa.Column("student_id", sa.UUID(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False, server_default="scheduled"),
        sa.Column("state_entered_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["supervisor_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index(op.f("ix_supervision_sessions_student_id"), "supervision_sessions", ["student_id"], unique=False)
    op.create_index(op.f("ix_supervision_sessions_state"), "supervision_sessions", ["state"], unique=False)
    op.create_index(op.f("ix_supervision_sessions_supervisor_id"), "supervision_sessions", ["supervisor_id"], unique=False)

    op.create_table(
        "writing_versions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("document_artifact_id", sa.UUID(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("version_label", sa.String(length=64), nullable=True),
        sa.Column("state", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("state_entered_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_artifact_id"], ["document_artifacts.id"], ondelete="CASCADE"),
    )
    op.create_index(op.f("ix_writing_versions_state"), "writing_versions", ["state"], unique=False)
    op.create_index(op.f("ix_writing_versions_user_id"), "writing_versions", ["user_id"], unique=False)

    op.add_column("timeline_milestones", sa.Column("state", sa.String(length=32), nullable=True))
    op.add_column("timeline_milestones", sa.Column("state_entered_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE timeline_milestones SET state = 'upcoming' WHERE state IS NULL")
    op.execute("UPDATE timeline_milestones SET state_entered_at = created_at WHERE state_entered_at IS NULL")
    op.alter_column(
        "timeline_milestones",
        "state",
        existing_type=sa.String(32),
        nullable=False,
        server_default="upcoming",
    )
    op.create_index(op.f("ix_timeline_milestones_state"), "timeline_milestones", ["state"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_timeline_milestones_state"), table_name="timeline_milestones")
    op.drop_column("timeline_milestones", "state_entered_at")
    op.drop_column("timeline_milestones", "state")

    op.drop_index(op.f("ix_writing_versions_user_id"), table_name="writing_versions")
    op.drop_index(op.f("ix_writing_versions_state"), table_name="writing_versions")
    op.drop_table("writing_versions")

    op.drop_index(op.f("ix_supervision_sessions_supervisor_id"), table_name="supervision_sessions")
    op.drop_index(op.f("ix_supervision_sessions_state"), table_name="supervision_sessions")
    op.drop_index(op.f("ix_supervision_sessions_student_id"), table_name="supervision_sessions")
    op.drop_table("supervision_sessions")

    op.drop_index(op.f("ix_user_opportunities_user_id"), table_name="user_opportunities")
    op.drop_index(op.f("ix_user_opportunities_state"), table_name="user_opportunities")
    op.drop_index(op.f("ix_user_opportunities_opportunity_id"), table_name="user_opportunities")
    op.drop_table("user_opportunities")
