"""Add compound indexes for chat_message

Revision ID: 0004_chat_message_indexes
Revises: 0003_timestamp_and_column_migration
"""

from alembic import op
import sqlalchemy as sa

revision = "0004_chat_message_indexes"
down_revision = "0003_timestamp_and_column_migration"


def upgrade() -> None:
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS idx_chat_message_session_role_created "
        "ON chat_message(session_id, author_role, created_at)"
    ))
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS idx_chat_message_session_platform_msg "
        "ON chat_message(session_id, platform_message_id)"
    ))
    op.execute(sa.text(
        "DROP INDEX IF EXISTS idx_chat_message_platform_message_id"
    ))


def downgrade() -> None:
    op.execute(sa.text(
        "DROP INDEX IF EXISTS idx_chat_message_session_role_created"
    ))
    op.execute(sa.text(
        "DROP INDEX IF EXISTS idx_chat_message_session_platform_msg"
    ))
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS idx_chat_message_platform_message_id "
        "ON chat_message(platform_message_id)"
    ))
