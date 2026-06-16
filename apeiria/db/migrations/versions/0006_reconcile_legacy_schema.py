"""Reconcile legacy schema.py databases with SQLAlchemy model schema.

Adds missing columns, converts TEXT timestamps to INTEGER epoch_ms,
rebuilds access_rule with correct composite PK, cleans up orphan tables
and leftovers from the dual-schema era.

Revision ID: 0006_reconcile_legacy_schema
Revises: 0005_fix_turn_disposition_constraint
Create Date: 2026-06-16
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0006_reconcile_legacy_schema"
down_revision: str | None = "0005_fix_turn_disposition_constraint"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_TIMESTAMP_CONVERSION: dict[str, list[str]] = {
    "plugin_state": ["updated_at"],
    "access_rule": ["created_at", "updated_at"],
    "group_state": ["updated_at"],
    "webui_auth_secret": ["created_at", "updated_at"],
    "webui_account": [
        "created_at", "updated_at", "last_login_at", "password_changed_at",
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
        "created_at", "updated_at",
        "last_observed_at", "last_user_message_at", "last_ai_message_at",
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
        "trigger_at", "claimed_at", "completed_at", "created_at", "updated_at",
    ],
    "ai_delivery_attempt": ["delivered_at", "failed_at", "created_at", "updated_at"],
    "ai_model_usage_event": ["created_at"],
    "ai_tool_policy": ["updated_at"],
    "apeiria_schema_meta": ["created_at", "updated_at"],
}


def _col_exists(conn: sa.engine.Connection, table: str, col: str) -> bool:
    rows = conn.execute(sa.text(f"PRAGMA table_info({table})"))
    return any(row[1] == col for row in rows)


def upgrade() -> None:
    conn: sa.engine.Connection = op.get_bind()

    # ── 1. Clean up orphan / leftover tables ──────────────────────────
    op.execute("DROP TABLE IF EXISTS ai_turn_trace")
    op.execute("DROP TABLE IF EXISTS ai_memory_belief_action")
    op.execute("DROP TABLE IF EXISTS _alembic_tmp_access_rule")

    # ── 2. Add missing columns (model-defined, absent from DB) ────────
    _add_column_if_missing(
        conn,
        "ai_runtime_settings",
        "relationship_event_retention_days",
        "INTEGER CHECK("
        "relationship_event_retention_days IS NULL "
        "OR relationship_event_retention_days >= 1)",
    )
    _add_column_if_missing(
        conn,
        "ai_runtime_settings",
        "future_task_retention_days",
        "INTEGER CHECK("
        "future_task_retention_days IS NULL "
        "OR future_task_retention_days >= 1)",
    )
    _add_column_if_missing(
        conn, "ai_runtime_settings", "trace_enabled",
        "INTEGER CHECK(trace_enabled IS NULL OR trace_enabled IN (0, 1))",
    )
    _add_column_if_missing(conn, "ai_persona", "created_at", "INTEGER")
    _add_column_if_missing(conn, "ai_persona_binding", "created_at", "INTEGER")

    # ── 3. Convert TEXT timestamps → INTEGER epoch_ms ─────────────────
    _convert_all_timestamps(conn)

    # ── 4. Rebuild access_rule with correct composite PK ───────────────
    _rebuild_access_rule(conn)

    # ── 5. Add missing indexes (from migration 0002, idempotent) ──────
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_chat_message_platform_message_id "
        "ON chat_message(platform_message_id)"
    )

    # ── 6. Remove redundant indexes (from migration 0002) ─────────────
    op.execute("DROP INDEX IF EXISTS idx_webui_account_username")


def downgrade() -> None:
    # This migration reconciles differences between two schema systems.
    # Downgrading would reintroduce inconsistencies — not supported.
    pass


def _add_column_if_missing(
    conn: sa.engine.Connection, table: str, column: str, type_suffix: str,
) -> None:
    if not _col_exists(conn, table, column):
        op.execute(sa.text(f"ALTER TABLE {table} ADD COLUMN {column} {type_suffix}"))


def _convert_all_timestamps(conn: sa.engine.Connection) -> None:
    for table, columns in _TIMESTAMP_CONVERSION.items():
        for col in columns:
            if not _col_exists(conn, table, col):
                continue
            conn.execute(
                sa.text(
                    f"UPDATE {table} SET {col} = CAST("
                    f"CASE "
                    f"WHEN {col} GLOB '*[^0-9]*' "
                    f"THEN strftime('%s', {col}) * 1000 "
                    f"WHEN CAST({col} AS INTEGER) >= 1000000000000 "
                    f"THEN {col} "
                    f"ELSE CAST({col} AS INTEGER) * 1000 END "
                    f"AS INTEGER) "
                    f"WHERE {col} IS NOT NULL AND typeof({col}) = 'text'"
                )
            )


def _rebuild_access_rule(conn: sa.engine.Connection) -> None:
    """Rebuild access_rule table from surrogate-id PK to composite PK.

    The legacy schema.py created this table with `id INTEGER PRIMARY KEY
    AUTOINCREMENT` while the SQLAlchemy model uses composite
    (subject_type, subject_id, plugin_id).  Since the table is empty in
    existing databases we simply drop and recreate.
    """
    existing_cols = {
        row[1]
        for row in conn.execute(sa.text("PRAGMA table_info(access_rule)"))
    }
    if "id" not in existing_cols:
        return

    try:
        conn.execute(sa.text("SAVEPOINT rebuild_access_rule"))

        conn.execute(sa.text("DROP TABLE IF EXISTS access_rule"))
        conn.execute(
            sa.text(
                "CREATE TABLE access_rule ("
                "subject_type TEXT NOT NULL CHECK(subject_type IN ('user', 'group')), "
                "subject_id TEXT NOT NULL, "
                "plugin_id TEXT NOT NULL, "
                "effect TEXT NOT NULL CHECK(effect IN ('allow', 'deny')), "
                "note TEXT, "
                "created_at INTEGER NOT NULL, "
                "updated_at INTEGER NOT NULL, "
                "PRIMARY KEY (subject_type, subject_id, plugin_id))"
            )
        )
    except Exception:
        conn.execute(sa.text("ROLLBACK TO SAVEPOINT rebuild_access_rule"))
        raise
    finally:
        conn.execute(sa.text("RELEASE SAVEPOINT rebuild_access_rule"))
