"""create user_profiles for the onboarding flag, with grant and RLS

Revision ID: c4d9f1a2b7e3
Revises: b3c8eb2a9e5b
Create Date: 2026-10-06 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4d9f1a2b7e3'
down_revision: Union[str, Sequence[str], None] = 'b3c8eb2a9e5b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

APP_ROLE = 'loremaster_app'
CURRENT_USER = "current_setting('app.current_user_id', true)::uuid"


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('user_profiles',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('onboarded_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('user_id')
    )
    # No backfill on purpose: every existing user sees the greeting once.
    op.execute(f'GRANT SELECT, INSERT, UPDATE ON user_profiles TO {APP_ROLE}')
    op.execute('ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY')
    # Same shape as documents_owner / conversations_owner.
    op.execute(f"""
        CREATE POLICY user_profiles_owner ON user_profiles
        USING (user_id = {CURRENT_USER})
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute('DROP POLICY IF EXISTS user_profiles_owner ON user_profiles')
    op.execute(f'REVOKE ALL ON user_profiles FROM {APP_ROLE}')
    op.drop_table('user_profiles')
