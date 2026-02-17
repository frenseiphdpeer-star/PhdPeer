"""longitudinal_events append-only event store

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-02-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "longitudinal_events",
        sa.Column("event_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=True),
        sa.Column("entity_id", sa.UUID(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_module", sa.String(length=128), nullable=False),
        sa.PrimaryKeyConstraint("event_id"),
        sa.Comment("Append-only event log; do not update or delete rows."),
    )
    op.create_index(op.f("ix_longitudinal_events_entity_id"), "longitudinal_events", ["entity_id"], unique=False)
    op.create_index(op.f("ix_longitudinal_events_entity_type"), "longitudinal_events", ["entity_type"], unique=False)
    op.create_index(op.f("ix_longitudinal_events_event_type"), "longitudinal_events", ["event_type"], unique=False)
    op.create_index(op.f("ix_longitudinal_events_role"), "longitudinal_events", ["role"], unique=False)
    op.create_index(op.f("ix_longitudinal_events_source_module"), "longitudinal_events", ["source_module"], unique=False)
    op.create_index(op.f("ix_longitudinal_events_timestamp"), "longitudinal_events", ["timestamp"], unique=False)
    op.create_index(op.f("ix_longitudinal_events_user_id"), "longitudinal_events", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_longitudinal_events_user_id"), table_name="longitudinal_events")
    op.drop_index(op.f("ix_longitudinal_events_timestamp"), table_name="longitudinal_events")
    op.drop_index(op.f("ix_longitudinal_events_source_module"), table_name="longitudinal_events")
    op.drop_index(op.f("ix_longitudinal_events_role"), table_name="longitudinal_events")
    op.drop_index(op.f("ix_longitudinal_events_event_type"), table_name="longitudinal_events")
    op.drop_index(op.f("ix_longitudinal_events_entity_type"), table_name="longitudinal_events")
    op.drop_index(op.f("ix_longitudinal_events_entity_id"), table_name="longitudinal_events")
    op.drop_table("longitudinal_events")
