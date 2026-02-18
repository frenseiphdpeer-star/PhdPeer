"""document_stage_suggestions stage classification with accept/override

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-02-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "document_stage_suggestions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("document_artifact_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("suggested_stage", sa.String(length=128), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("reasoning_tokens", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("accepted_stage", sa.String(length=128), nullable=True),
        sa.Column("override_stage", sa.String(length=128), nullable=True),
        sa.Column("override_reason", sa.Text(), nullable=True),
        sa.Column("system_suggested_stage", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["document_artifact_id"], ["document_artifacts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index(
        op.f("ix_document_stage_suggestions_document_artifact_id"),
        "document_stage_suggestions",
        ["document_artifact_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_document_stage_suggestions_user_id"),
        "document_stage_suggestions",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_document_stage_suggestions_user_id"), table_name="document_stage_suggestions")
    op.drop_index(op.f("ix_document_stage_suggestions_document_artifact_id"), table_name="document_stage_suggestions")
    op.drop_table("document_stage_suggestions")
