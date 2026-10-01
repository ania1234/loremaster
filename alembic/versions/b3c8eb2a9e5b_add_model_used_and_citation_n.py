"""add model_used to messages and n to message_citations

Revision ID: b3c8eb2a9e5b
Revises: a1c3e5f7b9d2
Create Date: 2026-10-01 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3c8eb2a9e5b'
down_revision: Union[str, Sequence[str], None] = 'a1c3e5f7b9d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('messages', sa.Column('model_used', sa.Text(), nullable=True))
    op.add_column('message_citations', sa.Column('n', sa.Integer(), nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('message_citations', 'n')
    op.drop_column('messages', 'model_used')
