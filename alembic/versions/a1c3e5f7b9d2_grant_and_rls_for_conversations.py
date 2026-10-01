"""Grant app role access and enable RLS on conversations, messages, citations

Revision ID: a1c3e5f7b9d2
Revises: 73c219c83178
Create Date: 2026-09-29 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'a1c3e5f7b9d2'
down_revision: Union[str, Sequence[str], None] = '73c219c83178'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

APP_ROLE = 'loremaster_app'
CURRENT_USER = "current_setting('app.current_user_id', true)::uuid"
TABLES = ('conversations', 'messages', 'message_citations')


def upgrade() -> None:
    """Upgrade schema."""
    for table in TABLES:
        op.execute(f'GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO {APP_ROLE}')
        op.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY')

    # Same shape as documents_owner / chunks_owner.
    op.execute(f"""
        CREATE POLICY conversations_owner ON conversations
        USING (user_id = {CURRENT_USER})
    """)
    # messages and citations have no user_id; ownership flows from the conversation.
    op.execute(f"""
        CREATE POLICY messages_owner ON messages
        USING (EXISTS (
            SELECT 1 FROM conversations c
            WHERE c.id = messages.conversation_id AND c.user_id = {CURRENT_USER}
        ))
    """)
    op.execute(f"""
        CREATE POLICY message_citations_owner ON message_citations
        USING (EXISTS (
            SELECT 1 FROM messages m
            JOIN conversations c ON c.id = m.conversation_id
            WHERE m.id = message_citations.message_id AND c.user_id = {CURRENT_USER}
        ))
    """)


def downgrade() -> None:
    """Downgrade schema."""
    for table in reversed(TABLES):
        op.execute(f'DROP POLICY IF EXISTS {table}_owner ON {table}')
        op.execute(f'ALTER TABLE {table} DISABLE ROW LEVEL SECURITY')
        op.execute(f'REVOKE ALL ON {table} FROM {APP_ROLE}')
