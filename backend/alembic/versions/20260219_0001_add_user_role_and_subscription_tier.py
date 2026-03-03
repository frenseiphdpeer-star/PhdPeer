"""add user role and subscription tier

Revision ID: 20260219_0001
Revises: 
Create Date: 2026-02-19 00:01:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260219_0001"
down_revision = None
branch_labels = None
depends_on = None


user_role_enum = sa.Enum(
    "researcher",
    "supervisor",
    "institutional_admin",
    name="user_role",
)

subscription_tier_enum = sa.Enum(
    "free",
    "pro",
    "institutional",
    name="subscription_tier",
)


def upgrade() -> None:
    bind = op.get_bind()
    from sqlalchemy import inspect
    insp = inspect(bind)
    user_cols = {c["name"] for c in insp.get_columns("users")}
    user_indexes = {idx["name"] for idx in insp.get_indexes("users")}

    if bind.dialect.name == "postgresql":
        user_role_enum.create(bind, checkfirst=True)
        subscription_tier_enum.create(bind, checkfirst=True)

    if "role" not in user_cols:
        op.add_column(
            "users",
            sa.Column(
                "role",
                user_role_enum,
                nullable=False,
                server_default="researcher",
            ),
        )
    if "subscription_tier" not in user_cols:
        op.add_column(
            "users",
            sa.Column(
                "subscription_tier",
                subscription_tier_enum,
                nullable=False,
                server_default="free",
            ),
        )

    if "ix_users_role" not in user_indexes:
        op.create_index(op.f("ix_users_role"), "users", ["role"], unique=False)
    if "ix_users_subscription_tier" not in user_indexes:
        op.create_index(
            op.f("ix_users_subscription_tier"),
            "users",
            ["subscription_tier"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()

    op.drop_index(op.f("ix_users_subscription_tier"), table_name="users")
    op.drop_index(op.f("ix_users_role"), table_name="users")
    op.drop_column("users", "subscription_tier")
    op.drop_column("users", "role")

    if bind.dialect.name == "postgresql":
        subscription_tier_enum.drop(bind, checkfirst=True)
        user_role_enum.drop(bind, checkfirst=True)
