"""rbac role and supervisor_assignments

Revision ID: a1b2c3d4e5f6
Revises: 3164506c2c1c
Create Date: 2026-02-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "3164506c2c1c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("role", sa.String(), nullable=False, server_default="researcher"),
    )
    op.create_index(op.f("ix_users_role"), "users", ["role"], unique=False)

    op.create_table(
        "supervisor_assignments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("supervisor_id", sa.UUID(), nullable=False),
        sa.Column("student_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["supervisor_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "supervisor_id",
            "student_id",
            name="uq_supervisor_student",
        ),
    )
    op.create_index(
        op.f("ix_supervisor_assignments_supervisor_id"),
        "supervisor_assignments",
        ["supervisor_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_supervisor_assignments_student_id"),
        "supervisor_assignments",
        ["student_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_supervisor_assignments_student_id"), table_name="supervisor_assignments")
    op.drop_index(op.f("ix_supervisor_assignments_supervisor_id"), table_name="supervisor_assignments")
    op.drop_table("supervisor_assignments")
    op.drop_index(op.f("ix_users_role"), table_name="users")
    op.drop_column("users", "role")
