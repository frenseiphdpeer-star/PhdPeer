"""timeline_adjustment_suggestions bidirectional feedback

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-02-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "timeline_adjustment_suggestions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("committed_timeline_id", sa.UUID(), nullable=False),
        sa.Column("reason", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("suggestion_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["committed_timeline_id"], ["committed_timelines.id"], ondelete="CASCADE"),
    )
    op.create_index(op.f("ix_timeline_adjustment_suggestions_committed_timeline_id"), "timeline_adjustment_suggestions", ["committed_timeline_id"], unique=False)
    op.create_index(op.f("ix_timeline_adjustment_suggestions_reason"), "timeline_adjustment_suggestions", ["reason"], unique=False)
    op.create_index(op.f("ix_timeline_adjustment_suggestions_status"), "timeline_adjustment_suggestions", ["status"], unique=False)
    op.create_index(op.f("ix_timeline_adjustment_suggestions_user_id"), "timeline_adjustment_suggestions", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_timeline_adjustment_suggestions_user_id"), table_name="timeline_adjustment_suggestions")
    op.drop_index(op.f("ix_timeline_adjustment_suggestions_status"), table_name="timeline_adjustment_suggestions")
    op.drop_index(op.f("ix_timeline_adjustment_suggestions_reason"), table_name="timeline_adjustment_suggestions")
    op.drop_index(op.f("ix_timeline_adjustment_suggestions_committed_timeline_id"), table_name="timeline_adjustment_suggestions")
    op.drop_table("timeline_adjustment_suggestions")
