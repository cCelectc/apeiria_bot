"""baseline: create all tables

Revision ID: 0001
Revises:
Create Date: 2026-06-19 00:00:00.000000
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sessions",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("platform", sa.Text, nullable=False),
        sa.Column("scene_type", sa.Text, nullable=False),
        sa.Column("scene_id", sa.Text, nullable=False),
        sa.Column("model_override", sa.Text, nullable=True),
        sa.Column("created_at", sa.Text, nullable=False),
        sa.Column("last_active_at", sa.Text, nullable=False),
        sa.Column("last_compacted_message_id", sa.Integer, nullable=True),
    )

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "session_id",
            sa.Text,
            sa.ForeignKey("sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.Text, nullable=False),
        sa.Column(
            "type", sa.Text, nullable=False, server_default="message"
        ),
        sa.Column("user_id", sa.Text, nullable=True),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("message_id", sa.Text, nullable=True),
        sa.Column("meta_json", sa.Text, nullable=True),
        sa.Column("created_at", sa.Integer, nullable=False),
        sa.CheckConstraint(
            "role IN ('user', 'assistant', 'system')",
            name="ck_messages_role",
        ),
        sa.CheckConstraint(
            "type IN ('message', 'message_sent', 'system')",
            name="ck_messages_type",
        ),
    )
    op.create_index(
        "ix_messages_session_id_created_at",
        "messages",
        ["session_id", "created_at"],
    )

    op.create_table(
        "facts",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Text, nullable=False),
        sa.Column("session_id", sa.Text, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column(
            "importance", sa.Float, nullable=False, server_default=sa.text("0.5")
        ),
        sa.Column(
            "embedding_status", sa.Text, nullable=False, server_default="pending"
        ),
        sa.Column("last_reinforced_at", sa.Text, nullable=False),
        sa.Column("created_at", sa.Text, nullable=False),
        sa.CheckConstraint(
            "embedding_status IN ('pending', 'embedded', 'failed')",
            name="ck_facts_embedding_status",
        ),
        sa.CheckConstraint(
            "importance >= 0 AND importance <= 1",
            name="ck_facts_importance",
        ),
    )
    op.create_index("ix_facts_user_id", "facts", ["user_id"])
    op.create_index("ix_facts_session_id", "facts", ["session_id"])

    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("source_file_name", sa.Text, nullable=False),
        sa.Column("content_hash", sa.Text, nullable=False),
        sa.Column("content_text", sa.Text, nullable=False),
        sa.Column("status", sa.Text, nullable=False, server_default="pending"),
        sa.Column(
            "chunk_count", sa.Integer, nullable=False, server_default=sa.text("0")
        ),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("created_at", sa.Text, nullable=False),
        sa.Column("updated_at", sa.Text, nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'embedded', 'degraded', 'failed')",
            name="ck_knowledge_documents_status",
        ),
        sa.CheckConstraint(
            "chunk_count >= 0",
            name="ck_knowledge_documents_chunk_count",
        ),
    )

    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "document_id",
            sa.Integer,
            sa.ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("embedding_model", sa.Text, nullable=True),
        sa.Column(
            "embedding_status", sa.Text, nullable=False, server_default="pending"
        ),
        sa.Column("created_at", sa.Text, nullable=False),
        sa.CheckConstraint("chunk_index >= 0", name="ck_knowledge_chunks_chunk_index"),
        sa.CheckConstraint(
            "embedding_status IN ('pending', 'embedded', 'failed')",
            name="ck_knowledge_chunks_embedding_status",
        ),
        sa.UniqueConstraint(
            "document_id", "chunk_index", name="uq_knowledge_chunks_doc_index"
        ),
    )
    op.create_index(
        "ix_knowledge_chunks_document_id",
        "knowledge_chunks",
        ["document_id"],
    )

    op.create_table(
        "relationship_scores",
        sa.Column("user_id", sa.Text, nullable=False),
        sa.Column("session_id", sa.Text, nullable=False),
        sa.Column("score", sa.Float, nullable=False, server_default=sa.text("50")),
        sa.Column("last_updated_at", sa.Text, nullable=False),
        sa.PrimaryKeyConstraint("user_id", "session_id"),
        sa.CheckConstraint(
            "score >= 0 AND score <= 100",
            name="ck_relationship_scores_score",
        ),
    )
    op.create_index(
        "ix_relationship_scores_session_id",
        "relationship_scores",
        ["session_id"],
    )

    op.create_table(
        "personas",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("prompt", sa.Text, nullable=False),
        sa.Column("enabled", sa.Integer, nullable=False, server_default=sa.text("1")),
        sa.Column(
            "is_default", sa.Integer, nullable=False, server_default=sa.text("0")
        ),
        sa.Column("created_at", sa.Text, nullable=False),
        sa.Column("updated_at", sa.Text, nullable=False),
        sa.CheckConstraint("enabled IN (0, 1)", name="ck_personas_enabled"),
        sa.CheckConstraint("is_default IN (0, 1)", name="ck_personas_is_default"),
    )
    op.create_index(
        "ix_personas_one_default",
        "personas",
        ["is_default"],
        unique=True,
        sqlite_where=sa.text("is_default = 1"),
    )

    op.create_table(
        "persona_bindings",
        sa.Column("session_id", sa.Text, primary_key=True),
        sa.Column(
            "persona_id",
            sa.Integer,
            sa.ForeignKey("personas.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.Text, nullable=False),
    )

    op.create_table(
        "ai_sources",
        sa.Column("source_id", sa.Text, primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("adapter", sa.Text, nullable=False),
        sa.Column("api_base", sa.Text, nullable=True),
        sa.Column("api_key_env", sa.Text, nullable=True),
        sa.Column("enabled", sa.Integer, nullable=False, server_default=sa.text("1")),
        sa.Column("timeout_seconds", sa.Integer, nullable=True),
        sa.Column("extra_config_json", sa.Text, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.Text, nullable=False),
        sa.Column("updated_at", sa.Text, nullable=False),
        sa.CheckConstraint(
            "adapter IN ('openai_compatible', 'anthropic_compatible', "
            "'gemini_native', 'fastembed', 'generic_rerank')",
            name="ck_ai_sources_adapter",
        ),
        sa.CheckConstraint("enabled IN (0, 1)", name="ck_ai_sources_enabled"),
        sa.CheckConstraint(
            "timeout_seconds IS NULL OR timeout_seconds > 0",
            name="ck_ai_sources_timeout_seconds",
        ),
    )

    op.create_table(
        "ai_chat_models",
        sa.Column("model_id", sa.Text, primary_key=True),
        sa.Column(
            "source_id",
            sa.Text,
            sa.ForeignKey("ai_sources.source_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("model_identifier", sa.Text, nullable=False),
        sa.Column("display_name", sa.Text, nullable=False),
        sa.Column(
            "context_window",
            sa.Integer,
            nullable=False,
            server_default=sa.text("128000"),
        ),
        sa.Column(
            "supports_reasoning",
            sa.Integer,
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("enabled", sa.Integer, nullable=False, server_default=sa.text("1")),
        sa.Column(
            "is_default", sa.Integer, nullable=False, server_default=sa.text("0")
        ),
        sa.Column("extra_params_json", sa.Text, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.Text, nullable=False),
        sa.Column("updated_at", sa.Text, nullable=False),
        sa.UniqueConstraint("source_id", "model_identifier"),
        sa.CheckConstraint(
            "supports_reasoning IN (0, 1)",
            name="ck_ai_chat_models_supports_reasoning",
        ),
        sa.CheckConstraint("enabled IN (0, 1)", name="ck_ai_chat_models_enabled"),
        sa.CheckConstraint("is_default IN (0, 1)", name="ck_ai_chat_models_is_default"),
    )
    op.create_index(
        "ix_ai_chat_models_one_default",
        "ai_chat_models",
        ["is_default"],
        unique=True,
        sqlite_where=sa.text("is_default = 1"),
    )

    op.create_table(
        "ai_embedding_models",
        sa.Column("model_id", sa.Text, primary_key=True),
        sa.Column(
            "source_id",
            sa.Text,
            sa.ForeignKey("ai_sources.source_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("model_identifier", sa.Text, nullable=False),
        sa.Column("display_name", sa.Text, nullable=False),
        sa.Column("dimensions", sa.Integer, nullable=True),
        sa.Column("enabled", sa.Integer, nullable=False, server_default=sa.text("1")),
        sa.Column(
            "is_default", sa.Integer, nullable=False, server_default=sa.text("0")
        ),
        sa.Column("extra_params_json", sa.Text, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.Text, nullable=False),
        sa.Column("updated_at", sa.Text, nullable=False),
        sa.UniqueConstraint("source_id", "model_identifier"),
        sa.CheckConstraint("enabled IN (0, 1)", name="ck_ai_embedding_models_enabled"),
        sa.CheckConstraint(
            "is_default IN (0, 1)", name="ck_ai_embedding_models_is_default"
        ),
    )
    op.create_index(
        "ix_ai_embedding_models_one_default",
        "ai_embedding_models",
        ["is_default"],
        unique=True,
        sqlite_where=sa.text("is_default = 1"),
    )

    op.create_table(
        "ai_rerank_models",
        sa.Column("model_id", sa.Text, primary_key=True),
        sa.Column(
            "source_id",
            sa.Text,
            sa.ForeignKey("ai_sources.source_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("model_identifier", sa.Text, nullable=False),
        sa.Column("display_name", sa.Text, nullable=False),
        sa.Column("enabled", sa.Integer, nullable=False, server_default=sa.text("1")),
        sa.Column(
            "is_default", sa.Integer, nullable=False, server_default=sa.text("0")
        ),
        sa.Column("extra_params_json", sa.Text, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.Text, nullable=False),
        sa.Column("updated_at", sa.Text, nullable=False),
        sa.UniqueConstraint("source_id", "model_identifier"),
        sa.CheckConstraint("enabled IN (0, 1)", name="ck_ai_rerank_models_enabled"),
        sa.CheckConstraint(
            "is_default IN (0, 1)", name="ck_ai_rerank_models_is_default"
        ),
    )
    op.create_index(
        "ix_ai_rerank_models_one_default",
        "ai_rerank_models",
        ["is_default"],
        unique=True,
        sqlite_where=sa.text("is_default = 1"),
    )

    op.create_table(
        "ai_runtime_settings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "talk_value", sa.Float, nullable=False, server_default=sa.text("0.3")
        ),
        sa.Column(
            "cooldown_seconds",
            sa.Integer,
            nullable=False,
            server_default=sa.text("30"),
        ),
        sa.Column(
            "max_replies_per_window",
            sa.Integer,
            nullable=False,
            server_default=sa.text("3"),
        ),
        sa.Column(
            "reply_window_seconds",
            sa.Integer,
            nullable=False,
            server_default=sa.text("300"),
        ),
        sa.Column(
            "no_action_backoff_base_seconds",
            sa.Integer,
            nullable=False,
            server_default=sa.text("60"),
        ),
        sa.Column(
            "no_action_backoff_max_seconds",
            sa.Integer,
            nullable=False,
            server_default=sa.text("600"),
        ),
        sa.Column(
            "compaction_threshold",
            sa.Float,
            nullable=False,
            server_default=sa.text("0.8"),
        ),
        sa.Column(
            "memory_isolate_by_session",
            sa.Integer,
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "memory_half_life_days",
            sa.Float,
            nullable=False,
            server_default=sa.text("30.0"),
        ),
        sa.Column(
            "memory_floor_ratio",
            sa.Float,
            nullable=False,
            server_default=sa.text("0.1"),
        ),
        sa.Column(
            "relationship_isolate_by_session",
            sa.Integer,
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "relationship_half_life_days",
            sa.Float,
            nullable=False,
            server_default=sa.text("30.0"),
        ),
        sa.Column(
            "rerank_enabled",
            sa.Integer,
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "segment_reply_enabled",
            sa.Integer,
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "segment_delay_seconds",
            sa.Float,
            nullable=False,
            server_default=sa.text("1.5"),
        ),
        sa.Column(
            "self_review_enabled",
            sa.Integer,
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("default_chat_model", sa.Text, nullable=True),
        sa.Column(
            "reasoning_effort",
            sa.Text,
            nullable=False,
            server_default="medium",
        ),
        sa.Column(
            "acp_access_mode",
            sa.Text,
            nullable=False,
            server_default="superuser_only",
        ),
        sa.Column("searxng_url", sa.Text, nullable=True),
        sa.Column("updated_at", sa.Text, nullable=False),
        sa.CheckConstraint("id = 1", name="ck_ai_runtime_settings_id"),
        sa.CheckConstraint(
            "talk_value > 0 AND talk_value <= 1.0",
            name="ck_ai_runtime_settings_talk_value",
        ),
        sa.CheckConstraint(
            "compaction_threshold > 0 AND compaction_threshold < 1.0",
            name="ck_ai_runtime_settings_compaction_threshold",
        ),
        sa.CheckConstraint(
            "memory_half_life_days > 0",
            name="ck_ai_runtime_settings_memory_half_life_days",
        ),
        sa.CheckConstraint(
            "memory_floor_ratio >= 0 AND memory_floor_ratio <= 1.0",
            name="ck_ai_runtime_settings_memory_floor_ratio",
        ),
        sa.CheckConstraint(
            "relationship_half_life_days > 0",
            name="ck_ai_runtime_settings_relationship_half_life_days",
        ),
        sa.CheckConstraint(
            "segment_delay_seconds >= 0",
            name="ck_ai_runtime_settings_segment_delay_seconds",
        ),
        sa.CheckConstraint(
            "memory_isolate_by_session IN (0, 1)",
            name="ck_ai_runtime_settings_memory_isolate_by_session",
        ),
        sa.CheckConstraint(
            "relationship_isolate_by_session IN (0, 1)",
            name="ck_ai_runtime_settings_relationship_isolate_by_session",
        ),
        sa.CheckConstraint(
            "rerank_enabled IN (0, 1)",
            name="ck_ai_runtime_settings_rerank_enabled",
        ),
        sa.CheckConstraint(
            "segment_reply_enabled IN (0, 1)",
            name="ck_ai_runtime_settings_segment_reply_enabled",
        ),
        sa.CheckConstraint(
            "self_review_enabled IN (0, 1)",
            name="ck_ai_runtime_settings_self_review_enabled",
        ),
        sa.CheckConstraint(
            "acp_access_mode IN ('superuser_only', 'open')",
            name="ck_ai_runtime_settings_acp_access_mode",
        ),
    )

    op.create_table(
        "ai_model_usage_event",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.Text, nullable=True),
        sa.Column("model_id", sa.Text, nullable=False),
        sa.Column("input_tokens", sa.Integer, nullable=True),
        sa.Column("output_tokens", sa.Integer, nullable=True),
        sa.Column("created_at", sa.Integer, nullable=False),
    )
    op.create_index(
        "ix_ai_model_usage_event_created_at",
        "ai_model_usage_event",
        ["created_at"],
    )

    op.create_table(
        "mcp_servers",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("transport", sa.Text, nullable=False),
        sa.Column("command", sa.Text, nullable=True),
        sa.Column("args_json", sa.Text, nullable=True),
        sa.Column("env_json", sa.Text, nullable=True),
        sa.Column("url", sa.Text, nullable=True),
        sa.Column("headers_json", sa.Text, nullable=True),
        sa.Column("enabled", sa.Integer, nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.Text, nullable=False),
        sa.Column("updated_at", sa.Text, nullable=False),
        sa.CheckConstraint(
            "transport IN ('stdio', 'sse')", name="ck_mcp_servers_transport"
        ),
        sa.CheckConstraint("enabled IN (0, 1)", name="ck_mcp_servers_enabled"),
    )

    op.create_table(
        "acp_agents",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("command", sa.Text, nullable=False),
        sa.Column("args_json", sa.Text, nullable=True),
        sa.Column("env_json", sa.Text, nullable=True),
        sa.Column("workspace", sa.Text, nullable=True),
        sa.Column("enabled", sa.Integer, nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.Text, nullable=False),
        sa.Column("updated_at", sa.Text, nullable=False),
        sa.CheckConstraint("enabled IN (0, 1)", name="ck_acp_agents_enabled"),
    )

    op.create_table(
        "access_rules",
        sa.Column("subject_type", sa.Text, nullable=False),
        sa.Column("subject_id", sa.Text, nullable=False),
        sa.Column("plugin_name", sa.Text, nullable=False),
        sa.Column("effect", sa.Text, nullable=False),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("created_at", sa.Text, nullable=False),
        sa.Column("updated_at", sa.Text, nullable=False),
        sa.PrimaryKeyConstraint("subject_type", "subject_id", "plugin_name"),
        sa.CheckConstraint(
            "subject_type IN ('user', 'group')",
            name="ck_access_rules_subject_type",
        ),
        sa.CheckConstraint(
            "effect IN ('allow', 'deny')", name="ck_access_rules_effect"
        ),
    )

    op.create_table(
        "plugin_state",
        sa.Column("plugin_id", sa.Text, primary_key=True),
        sa.Column("enabled", sa.Integer, nullable=False, server_default=sa.text("1")),
        sa.Column(
            "access_mode",
            sa.Text,
            nullable=False,
            server_default="default_allow",
        ),
        sa.Column(
            "protection_mode",
            sa.Text,
            nullable=False,
            server_default="normal",
        ),
        sa.Column("updated_at", sa.Text, nullable=False),
        sa.CheckConstraint("enabled IN (0, 1)", name="ck_plugin_state_enabled"),
        sa.CheckConstraint(
            "access_mode IN ('default_allow', 'default_deny')",
            name="ck_plugin_state_access_mode",
        ),
        sa.CheckConstraint(
            "protection_mode IN ('normal', 'required')",
            name="ck_plugin_state_protection_mode",
        ),
    )

    op.create_table(
        "ai_profiles",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("platform", sa.Text, nullable=False),
        sa.Column("user_id", sa.Text, nullable=False),
        sa.Column("display_name", sa.Text, nullable=True),
        sa.Column("created_at", sa.Text, nullable=False),
        sa.Column("updated_at", sa.Text, nullable=False),
        sa.UniqueConstraint("platform", "user_id"),
    )


def downgrade() -> None:
    op.drop_table("ai_profiles")
    op.drop_table("plugin_state")
    op.drop_table("access_rules")
    op.drop_table("acp_agents")
    op.drop_table("mcp_servers")
    op.drop_index(
        "ix_ai_model_usage_event_created_at",
        table_name="ai_model_usage_event",
    )
    op.drop_table("ai_model_usage_event")
    op.drop_table("ai_runtime_settings")
    op.drop_table("ai_rerank_models")
    op.drop_table("ai_embedding_models")
    op.drop_table("ai_chat_models")
    op.drop_table("ai_sources")
    op.drop_table("persona_bindings")
    op.drop_table("personas")
    op.drop_index("ix_relationship_scores_session_id", table_name="relationship_scores")
    op.drop_table("relationship_scores")
    op.drop_index("ix_knowledge_chunks_document_id", table_name="knowledge_chunks")
    op.drop_table("knowledge_chunks")
    op.drop_table("knowledge_documents")
    op.drop_index("ix_facts_session_id", table_name="facts")
    op.drop_index("ix_facts_user_id", table_name="facts")
    op.drop_table("facts")
    op.drop_index("ix_messages_session_id_created_at", table_name="messages")
    op.drop_table("messages")
    op.drop_table("sessions")
