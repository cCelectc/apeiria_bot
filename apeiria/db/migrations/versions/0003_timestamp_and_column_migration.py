"""Timestamp and column migration - Phase 8 final

Convert TEXT timestamps to INTEGER epoch_ms, remove deprecated columns
from chat_message (meta_json, raw_data_json, session_pk), and ensure
session_id FK is populated.

Revision ID: 0003_timestamp_and_column_migration
Revises: 0002_schema_improvements
Create Date: 2026-06-13
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0003_timestamp_and_column_migration"
down_revision: str | None = "0002_schema_improvements"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES_COLUMNS: dict[str, list[str]] = {
    "plugin_state": ["updated_at"],
    "access_rule": ["created_at", "updated_at"],
    "group_state": ["updated_at"],
    "webui_auth_secret": ["created_at", "updated_at"],
    "webui_account": [
        "created_at",
        "updated_at",
        "last_login_at",
        "password_changed_at",
    ],
    "chat_session": ["created_at", "updated_at", "last_message_at"],
    "chat_message": ["created_at"],
    "chat_session_context_summary": ["updated_at"],
    "ai_source": ["updated_at"],
    "ai_chat_model": ["updated_at"],
    "ai_embedding_model": ["updated_at"],
    "ai_stt_model": ["updated_at"],
    "ai_tts_model": ["updated_at"],
    "ai_rerank_model": ["updated_at"],
    "ai_model_profile": ["updated_at"],
    "ai_model_binding": ["updated_at"],
    "ai_model_route": ["updated_at"],
    "ai_model_route_member": ["updated_at"],
    "ai_model_route_binding": ["updated_at"],
    "ai_persona": ["created_at", "updated_at"],
    "ai_persona_binding": ["created_at", "updated_at"],
    "ai_managed_session": [
        "created_at",
        "updated_at",
        "last_observed_at",
        "last_user_message_at",
        "last_ai_message_at",
        "context_reset_at",
    ],
    "ai_runtime_settings": ["updated_at"],
    "ai_memory_item": ["last_recalled_at", "created_at"],
    "ai_knowledge_document": ["created_at", "updated_at"],
    "ai_knowledge_chunk": ["created_at", "updated_at"],
    "ai_profile": ["last_interaction_at", "created_at", "updated_at"],
    "ai_affinity": ["last_event_at", "last_decay_at"],
    "ai_relationship_event": ["created_at"],
    "ai_future_task": [
        "trigger_at",
        "claimed_at",
        "completed_at",
        "created_at",
        "updated_at",
    ],
    "ai_delivery_attempt": ["delivered_at", "failed_at", "created_at", "updated_at"],
    "ai_model_usage_event": ["created_at"],
    "ai_tool_policy": ["updated_at"],
}


def _backup_database() -> None:
    bind = op.get_bind()
    url = str(bind.engine.url)
    if url.startswith("sqlite:///"):
        db_path = Path(url.replace("sqlite:///", ""))
        if db_path.exists():
            backup_path = db_path.with_suffix(".sqlite3.pre_0003_backup")
            shutil.copy2(db_path, backup_path)


def _table_exists(connection: sa.engine.Connection, table: str) -> bool:
    result = connection.execute(
        sa.text(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=:name"
        ),
        {"name": table},
    )
    return result.fetchone() is not None


def _column_exists(connection: sa.engine.Connection, table: str, column: str) -> bool:
    rows = connection.execute(sa.text(f"PRAGMA table_info({table})"))
    return any(row[1] == column for row in rows)


def _convert_all_timestamps() -> None:
    connection = op.get_bind()
    for table, columns in TABLES_COLUMNS.items():
        if not _table_exists(connection, table):
            continue
        for col in columns:
            if not _column_exists(connection, table, col):
                continue
            op.execute(
                sa.text(
                    f"UPDATE {table} "
                    f"SET {col} = CAST(strftime('%s', {col}) AS INTEGER) * 1000 "
                    f"WHERE {col} IS NOT NULL AND typeof({col}) = 'text'"
                )
            )


def _migrate_chat_message() -> None:
    connection = op.get_bind()

    if not _table_exists(connection, "chat_message"):
        return

    has_session_pk = _column_exists(connection, "chat_message", "session_pk")
    has_session_id = _column_exists(connection, "chat_message", "session_id")
    has_meta_json = _column_exists(connection, "chat_message", "meta_json")
    has_raw_data_json = _column_exists(connection, "chat_message", "raw_data_json")

    if not has_session_id and has_session_pk:
        op.execute(sa.text("ALTER TABLE chat_message ADD COLUMN session_id TEXT"))
        op.execute(
            sa.text(
                "UPDATE chat_message "
                "SET session_id = ("
                "  SELECT session_id FROM chat_session "
                "  WHERE chat_session.id = chat_message.session_pk"
                ") "
                "WHERE session_id IS NULL AND session_pk IS NOT NULL"
            )
        )
    elif has_session_id and has_session_pk:
        op.execute(
            sa.text(
                "UPDATE chat_message "
                "SET session_id = ("
                "  SELECT session_id FROM chat_session "
                "  WHERE chat_session.id = chat_message.session_pk"
                ") "
                "WHERE session_id IS NULL AND session_pk IS NOT NULL"
            )
        )

    columns_to_drop = []
    if has_meta_json:
        columns_to_drop.append("meta_json")
    if has_raw_data_json:
        columns_to_drop.append("raw_data_json")
    if has_session_pk:
        columns_to_drop.append("session_pk")

    if columns_to_drop:
        op.execute(sa.text("DROP INDEX IF EXISTS idx_chat_message_session_pk"))
        op.execute(sa.text("DROP INDEX IF EXISTS idx_chat_message_session_created"))
        with op.batch_alter_table("chat_message", schema=None) as batch_op:
            for col in columns_to_drop:
                batch_op.drop_column(col)

    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS idx_chat_message_session_created "
        "ON chat_message(session_id, created_at)"
    ))


def upgrade() -> None:
    _backup_database()
    _convert_all_timestamps()
    _migrate_chat_message()


def downgrade() -> None:
    connection = op.get_bind()

    if not _table_exists(connection, "chat_message"):
        return

    missing_meta = not _column_exists(connection, "chat_message", "meta_json")
    missing_raw = not _column_exists(connection, "chat_message", "raw_data_json")
    missing_session_pk = not _column_exists(
        connection, "chat_message", "session_pk"
    )

    columns_to_add = []
    if missing_meta:
        columns_to_add.append("meta_json")
    if missing_raw:
        columns_to_add.append("raw_data_json")
    if missing_session_pk:
        columns_to_add.append("session_pk")

    if columns_to_add:
        with op.batch_alter_table("chat_message", schema=None) as batch_op:
            for col in columns_to_add:
                if col == "session_pk":
                    batch_op.add_column(
                        sa.Column(col, sa.Integer(), nullable=True)
                    )
                else:
                    batch_op.add_column(
                        sa.Column(col, sa.Text(), nullable=True)
                    )

        op.execute(
            sa.text("DROP INDEX IF EXISTS idx_chat_message_session_created")
        )
        if missing_session_pk:
            op.execute(
                sa.text(
                    "CREATE INDEX IF NOT EXISTS idx_chat_message_session_pk "
                    "ON chat_message(session_pk)"
                )
            )
            op.execute(
                sa.text(
                    "CREATE INDEX IF NOT EXISTS idx_chat_message_session_created "
                    "ON chat_message(session_pk, created_at)"
                )
            )
