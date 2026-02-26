"""recreate longitudinal_events

Revision ID: 825a6e002e17
Revises: 2a353962963c
Create Date: 2026-02-26 23:12:11.389563

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '825a6e002e17'
down_revision: Union[str, None] = '2a353962963c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'longitudinal_events',
        sa.Column('event_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('role', sa.String(length=32), nullable=False),
        sa.Column('event_type', sa.String(length=64), nullable=False),
        sa.Column('entity_type', sa.String(length=64), nullable=True),
        sa.Column('entity_id', sa.UUID(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('timestamp', postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('source_module', sa.String(length=128), nullable=False),
        sa.PrimaryKeyConstraint('event_id', name='longitudinal_events_pkey'),
        comment='Append-only event log; do not update or delete rows.',
    )
    op.create_index('ix_longitudinal_events_user_id', 'longitudinal_events', ['user_id'])
    op.create_index('ix_longitudinal_events_role', 'longitudinal_events', ['role'])
    op.create_index('ix_longitudinal_events_event_type', 'longitudinal_events', ['event_type'])
    op.create_index('ix_longitudinal_events_entity_type', 'longitudinal_events', ['entity_type'])
    op.create_index('ix_longitudinal_events_entity_id', 'longitudinal_events', ['entity_id'])
    op.create_index('ix_longitudinal_events_source_module', 'longitudinal_events', ['source_module'])
    op.create_index('ix_longitudinal_events_timestamp', 'longitudinal_events', ['timestamp'])


def downgrade() -> None:
    op.drop_index('ix_longitudinal_events_timestamp', table_name='longitudinal_events')
    op.drop_index('ix_longitudinal_events_source_module', table_name='longitudinal_events')
    op.drop_index('ix_longitudinal_events_entity_id', table_name='longitudinal_events')
    op.drop_index('ix_longitudinal_events_entity_type', table_name='longitudinal_events')
    op.drop_index('ix_longitudinal_events_event_type', table_name='longitudinal_events')
    op.drop_index('ix_longitudinal_events_role', table_name='longitudinal_events')
    op.drop_index('ix_longitudinal_events_user_id', table_name='longitudinal_events')
    op.drop_table('longitudinal_events')
