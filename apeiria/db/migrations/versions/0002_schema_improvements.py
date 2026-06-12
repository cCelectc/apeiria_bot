"""Schema improvements - Phase 8

Drop unused tables, add missing indexes, remove redundant indexes,
add new junction/summary tables.

Revision ID: 0002_schema_improvements
Revises: 0907ade3a5d7
Create Date: 2026-06-13
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0002_schema_improvements"
down_revision: str | None = "0907ade3a5d7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Drop 4 removed tables
    op.execute("DROP TABLE IF EXISTS ai_turn_trace")
    op.execute("DROP TABLE IF EXISTS ai_tool_execution")
    op.execute("DROP TABLE IF EXISTS command_statistics")
    op.execute("DROP TABLE IF EXISTS ai_memory_belief_action")

    # 2. Add missing indexes (idempotent via IF NOT EXISTS)
    # NOTE: idx_chat_message_session_created deferred to 0003 (session_id column added there)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_chat_message_platform_message_id "
        "ON chat_message(platform_message_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_ai_memory_item_lifecycle_created "
        "ON ai_memory_item(lifecycle_state, created_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_ai_chat_model_source_id "
        "ON ai_chat_model(source_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_ai_embedding_model_source_id "
        "ON ai_embedding_model(source_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_ai_stt_model_source_id "
        "ON ai_stt_model(source_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_ai_tts_model_source_id "
        "ON ai_tts_model(source_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_ai_rerank_model_source_id "
        "ON ai_rerank_model(source_id)"
    )

    # 3. Remove redundant indexes (duplicates of UNIQUE constraints)
    op.execute("DROP INDEX IF EXISTS idx_ai_memory_item_memory_id")
    op.execute("DROP INDEX IF EXISTS idx_ai_managed_session_source")
    op.execute("DROP INDEX IF EXISTS idx_webui_account_username")
    op.execute("DROP INDEX IF EXISTS idx_ai_affinity_user")

    # 4. Add group_disabled_plugin junction table
    op.execute(
        "CREATE TABLE IF NOT EXISTS group_disabled_plugin ("
        "group_id TEXT NOT NULL REFERENCES group_state(group_id) ON DELETE CASCADE, "
        "plugin_id TEXT NOT NULL, "
        "PRIMARY KEY (group_id, plugin_id))"
    )

    # 5. Migrate data from disabled_plugins_json to junction table
    op.execute(
        "INSERT OR IGNORE INTO group_disabled_plugin (group_id, plugin_id) "
        "SELECT g.group_id, json_each.value "
        "FROM group_state g, json_each(g.disabled_plugins_json) "
        "WHERE g.disabled_plugins_json IS NOT NULL "
        "AND g.disabled_plugins_json != '[]'"
    )

    # 6. Add ai_model_usage_hourly table
    op.execute(
        "CREATE TABLE IF NOT EXISTS ai_model_usage_hourly ("
        "hour_bucket INTEGER NOT NULL, "
        "source_id TEXT NOT NULL, "
        "model_name TEXT NOT NULL, "
        "operation TEXT NOT NULL, "
        "call_count INTEGER NOT NULL DEFAULT 0, "
        "measured_call_count INTEGER NOT NULL DEFAULT 0, "
        "input_tokens INTEGER NOT NULL DEFAULT 0, "
        "output_tokens INTEGER NOT NULL DEFAULT 0, "
        "total_tokens INTEGER NOT NULL DEFAULT 0, "
        "cached_input_tokens INTEGER NOT NULL DEFAULT 0, "
        "reasoning_tokens INTEGER NOT NULL DEFAULT 0, "
        "audio_input_tokens INTEGER NOT NULL DEFAULT 0, "
        "audio_output_tokens INTEGER NOT NULL DEFAULT 0, "
        "PRIMARY KEY (hour_bucket, source_id, model_name, operation))"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS ai_model_usage_hourly")
    op.execute("DROP TABLE IF EXISTS group_disabled_plugin")

    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_ai_memory_item_memory_id "
        "ON ai_memory_item(memory_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_ai_managed_session_source "
        "ON ai_managed_session(platform_id, platform_type, message_type, subject_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_webui_account_username "
        "ON webui_account(username)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_ai_affinity_user "
        "ON ai_affinity(platform, user_id)"
    )
