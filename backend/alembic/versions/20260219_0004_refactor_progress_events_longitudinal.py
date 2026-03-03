"""refactor progress events longitudinal schema

Revision ID: 20260219_0004
Revises: 20260219_0003
Create Date: 2026-02-19 00:04:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20260219_0004"
down_revision = "20260219_0003"
branch_labels = None
depends_on = None


EVENT_TYPES = [
    "milestone_completed",
    "milestone_delayed",
    "stage_started",
    "stage_completed",
    "achievement",
    "blocker",
    "update",
]


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        raise RuntimeError("This migration is designed for PostgreSQL")

    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'progress_event_type') THEN
                CREATE TYPE progress_event_type AS ENUM (
                    'milestone_completed',
                    'milestone_delayed',
                    'stage_started',
                    'stage_completed',
                    'achievement',
                    'blocker',
                    'update'
                );
            END IF;
        END $$;
        """
    )

    op.add_column(
        "progress_events",
        sa.Column("event_date_new", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "progress_events",
        sa.Column(
            "event_type_new",
            postgresql.ENUM(name="progress_event_type", create_type=False),
            nullable=True,
        ),
    )
    op.add_column(
        "progress_events",
        sa.Column("tags_new", postgresql.ARRAY(sa.String()), nullable=True),
    )

    op.execute(
        """
        DO $$
        DECLARE
            rows_updated INTEGER := 0;
        BEGIN
            LOOP
                WITH batch AS (
                    SELECT id
                    FROM progress_events
                    WHERE event_date_new IS NULL
                    LIMIT 5000
                )
                UPDATE progress_events pe
                SET
                    event_date_new = (pe.event_date::timestamp AT TIME ZONE 'UTC'),
                    event_type_new = CASE
                        WHEN pe.event_type IN (
                            'milestone_completed',
                            'milestone_delayed',
                            'stage_started',
                            'stage_completed',
                            'achievement',
                            'blocker',
                            'update'
                        )
                        THEN pe.event_type::progress_event_type
                        ELSE 'update'::progress_event_type
                    END,
                    tags_new = CASE
                        WHEN pe.tags IS NULL THEN NULL
                        WHEN pg_typeof(pe.tags)::text LIKE '%%[]' THEN
                            CASE WHEN array_length(pe.tags::varchar[], 1) IS NULL OR array_length(pe.tags::varchar[], 1) = 0 THEN NULL
                            ELSE pe.tags::varchar[] END
                        ELSE CASE WHEN btrim(pe.tags::varchar) = '' THEN NULL
                            ELSE regexp_split_to_array(pe.tags::varchar, '\\s*,\\s*') END
                    END
                FROM batch
                WHERE pe.id = batch.id;

                GET DIAGNOSTICS rows_updated = ROW_COUNT;
                EXIT WHEN rows_updated = 0;
            END LOOP;
        END $$;
        """
    )

    op.alter_column(
        "progress_events",
        "event_date_new",
        nullable=False,
        server_default=sa.text("now()"),
    )
    op.alter_column(
        "progress_events",
        "event_type_new",
        nullable=False,
    )

    op.execute("ALTER TABLE progress_events RENAME COLUMN event_date TO event_date_legacy")
    op.execute("ALTER TABLE progress_events RENAME COLUMN event_type TO event_type_legacy")
    op.execute("ALTER TABLE progress_events RENAME COLUMN tags TO tags_legacy")

    op.execute("ALTER TABLE progress_events RENAME COLUMN event_date_new TO event_date")
    op.execute("ALTER TABLE progress_events RENAME COLUMN event_type_new TO event_type")
    op.execute("ALTER TABLE progress_events RENAME COLUMN tags_new TO tags")

    op.execute("ALTER TABLE progress_events DROP COLUMN event_date_legacy")
    op.execute("ALTER TABLE progress_events DROP COLUMN event_type_legacy")
    op.execute("ALTER TABLE progress_events DROP COLUMN tags_legacy")

    with op.get_context().autocommit_block():
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_progress_events_tags_gin "
            "ON progress_events USING gin (tags)"
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        raise RuntimeError("This migration is designed for PostgreSQL")

    op.add_column(
        "progress_events",
        sa.Column("event_date_old", sa.Date(), nullable=True),
    )
    op.add_column(
        "progress_events",
        sa.Column("event_type_old", sa.String(), nullable=True),
    )
    op.add_column(
        "progress_events",
        sa.Column("tags_old", sa.String(), nullable=True),
    )

    op.execute(
        """
        UPDATE progress_events
        SET
            event_date_old = (event_date AT TIME ZONE 'UTC')::date,
            event_type_old = event_type::text,
            tags_old = CASE
                WHEN tags IS NULL THEN NULL
                ELSE array_to_string(tags, ',')
            END
        """
    )

    op.alter_column("progress_events", "event_date_old", nullable=False)
    op.alter_column("progress_events", "event_type_old", nullable=False)

    op.execute("ALTER TABLE progress_events RENAME COLUMN event_date TO event_date_new")
    op.execute("ALTER TABLE progress_events RENAME COLUMN event_type TO event_type_new")
    op.execute("ALTER TABLE progress_events RENAME COLUMN tags TO tags_new")

    op.execute("ALTER TABLE progress_events RENAME COLUMN event_date_old TO event_date")
    op.execute("ALTER TABLE progress_events RENAME COLUMN event_type_old TO event_type")
    op.execute("ALTER TABLE progress_events RENAME COLUMN tags_old TO tags")

    op.execute("ALTER TABLE progress_events DROP COLUMN event_date_new")
    op.execute("ALTER TABLE progress_events DROP COLUMN event_type_new")
    op.execute("ALTER TABLE progress_events DROP COLUMN tags_new")

    with op.get_context().autocommit_block():
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_progress_events_tags_gin")

    op.execute("DROP TYPE IF EXISTS progress_event_type")
