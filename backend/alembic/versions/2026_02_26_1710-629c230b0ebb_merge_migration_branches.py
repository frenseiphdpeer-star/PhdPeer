"""merge migration branches

Revision ID: 629c230b0ebb
Revises: 20260219_0006, f6a7b8c9d0e1
Create Date: 2026-02-26 17:10:08.227222

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '629c230b0ebb'
down_revision: Union[str, None] = ('20260219_0006', 'f6a7b8c9d0e1')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
