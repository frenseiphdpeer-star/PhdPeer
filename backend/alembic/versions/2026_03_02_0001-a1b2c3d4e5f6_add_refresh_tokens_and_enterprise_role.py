"""add refresh_tokens table, enterprise_client role, convert role to varchar

Revision ID: f7e8d9c0b1a2
Revises: 825a6e002e17
Create Date: 2026-03-02 00:01:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "f7e8d9c0b1a2"
down_revision: Union[str, None] = "825a6e002e17"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    # 1. Convert role column from native enum to VARCHAR so new values work
    #    without DDL for every new role.
    if is_pg:
        op.execute("ALTER TABLE users ALTER COLUMN role DROP DEFAULT")
        op.execute("ALTER TABLE users ALTER COLUMN role TYPE VARCHAR USING role::text")
        op.execute("DROP TYPE IF EXISTS user_role")
        op.execute("ALTER TABLE users ALTER COLUMN role SET DEFAULT 'researcher'")

    # 2. Rename legacy value
    op.execute(
        "UPDATE users SET role = 'institution_admin' WHERE role = 'institutional_admin'"
    )

    # 3. Create refresh_tokens table
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("token", sa.String(), nullable=False),
        sa.Column(
            "user_id",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("replaced_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_refresh_tokens_token", "refresh_tokens", ["token"], unique=True)
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])


def downgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    op.drop_index("ix_refresh_tokens_user_id", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_token", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")

    # Restore old role value
    op.execute(
        "UPDATE users SET role = 'institutional_admin' WHERE role = 'institution_admin'"
    )
    # Remove enterprise_client rows if any
    op.execute(
        "UPDATE users SET role = 'researcher' WHERE role = 'enterprise_client'"
    )

    if is_pg:
        user_role_enum = sa.Enum(
            "RESEARCHER", "SUPERVISOR", "INSTITUTIONAL_ADMIN",
            name="user_role",
        )
        user_role_enum.create(bind, checkfirst=True)
        op.execute(
            "ALTER TABLE users ALTER COLUMN role TYPE user_role USING role::text::user_role"
        )
