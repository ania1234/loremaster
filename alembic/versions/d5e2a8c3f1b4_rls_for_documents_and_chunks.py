"""Grant app role access and enable RLS on documents and chunks

These were set up by hand in Supabase and never written down, so a database
built from migrations had no row-level isolation on the two most private
tables. Every step only adds what is missing: on a database that already has
them (production), this migration changes nothing.

Revision ID: d5e2a8c3f1b4
Revises: c4d9f1a2b7e3
Create Date: 2026-11-12 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'd5e2a8c3f1b4'
down_revision: Union[str, Sequence[str], None] = 'c4d9f1a2b7e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

APP_ROLE = 'loremaster_app'
CURRENT_USER = "current_setting('app.current_user_id', true)::uuid"
TABLES = ('documents', 'chunks')


def upgrade() -> None:
    """Upgrade schema."""
    for table in TABLES:
        op.execute(f'GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO {APP_ROLE}')
        op.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY')
        # Same shape as conversations_owner. Created only when missing, so an
        # existing hand-made policy is left exactly as it is.
        op.execute(f"""
            DO $$ BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_policies
                               WHERE schemaname = 'public'
                                 AND tablename = '{table}'
                                 AND policyname = '{table}_owner') THEN
                    CREATE POLICY {table}_owner ON {table}
                    USING (user_id = {CURRENT_USER});
                END IF;
            END $$
        """)


def downgrade() -> None:
    """Downgrade schema.

    Deliberately empty: production had these policies before this migration
    existed, and dropping them would remove its isolation.
    """
