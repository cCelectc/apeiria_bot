"""Bootstrap and validate the Apeiria SQLite schema."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apeiria.db.runtime import ApeiriaDatabase

CURRENT_SCHEMA_LINE = "apeiria_v1"
CURRENT_SCHEMA_VERSION = 1

SOURCE_MODEL_TABLE_NAMES: tuple[str, ...] = (
    "ai_chat_model",
    "ai_embedding_model",
    "ai_stt_model",
    "ai_tts_model",
    "ai_rerank_model",
)

TURN_DISPOSITION_VALUES: tuple[str, ...] = (
    "active",
    "observed",
    "generated",
    "tool",
    "system",
)
TURN_DISPOSITION_CHECK = (
    "turn_disposition IN ('active', 'observed', 'generated', 'tool', 'system')"
)


class DatabaseSchemaError(RuntimeError):
    """Base error for Apeiria SQLite schema handling."""


class IncompatibleDatabaseError(DatabaseSchemaError):
    """Raised when the on-disk database is not compatible with apeiria_v1."""

    @classmethod
    def missing_schema_meta(cls) -> "IncompatibleDatabaseError":
        return cls("database exists without apeiria_v1 schema metadata")

    @classmethod
    def wrong_schema_line(cls) -> "IncompatibleDatabaseError":
        return cls("database schema line is not compatible with apeiria_v1")


class UnsupportedDatabaseVersionError(DatabaseSchemaError):
    """Raised when an old in-development SQLite schema is encountered."""

    @classmethod
    def unsupported_schema_version(
        cls,
        *,
        observed: int,
        expected: int,
    ) -> "UnsupportedDatabaseVersionError":
        return cls(
            "database schema version "
            f"{observed} is not supported by this Apeiria build; "
            f"recreate the local database at apeiria_v1/{expected}"
        )


@dataclass(frozen=True)
class SchemaMetaRecord:
    """Observed metadata from ``apeiria_schema_meta``."""

    schema_line: str
    schema_version: int


def ensure_database_ready_sync(database: "ApeiriaDatabase | None" = None) -> None:
    """Synchronously initialize or validate the Apeiria SQLite database."""

    runtime = _coerce_database(database)
    runtime.ensure_parent_dir()

    with runtime.connect_sync() as connection:
        existing_tables = _table_names(connection)
        if not existing_tables:
            _create_current_schema(connection)
            return

        if "apeiria_schema_meta" not in existing_tables:
            raise IncompatibleDatabaseError.missing_schema_meta()

        meta = _read_schema_meta(connection)
        if meta is None or meta.schema_line != CURRENT_SCHEMA_LINE:
            raise IncompatibleDatabaseError.wrong_schema_line()
        if meta.schema_version != CURRENT_SCHEMA_VERSION:
            raise UnsupportedDatabaseVersionError.unsupported_schema_version(
                observed=meta.schema_version,
                expected=CURRENT_SCHEMA_VERSION,
            )
        _ensure_current_schema_shape(connection)


async def ensure_database_ready(database: "ApeiriaDatabase | None" = None) -> None:
    """Async wrapper for SQLite schema initialization and validation."""

    ensure_database_ready_sync(database)


def _coerce_database(database: "ApeiriaDatabase | None") -> "ApeiriaDatabase":
    if database is not None:
        return database

    from apeiria.db.runtime import database_runtime

    return database_runtime


def _utcnow_text() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _table_names(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    ).fetchall()
    return {str(row[0]) for row in rows}


def _read_schema_meta(connection: sqlite3.Connection) -> SchemaMetaRecord | None:
    row = connection.execute(
        """
        SELECT schema_line, schema_version
        FROM apeiria_schema_meta
        WHERE id = 1
        """
    ).fetchone()
    if row is None:
        return None
    return SchemaMetaRecord(schema_line=str(row[0]), schema_version=int(row[1]))


def _column_names(connection: sqlite3.Connection, table_name: str) -> set[str]:
    return {
        str(row[1]) for row in connection.execute(f"PRAGMA table_info({table_name})")
    }


def _ensure_current_schema_shape(  # noqa: C901, PLR0912
    connection: sqlite3.Connection,
) -> None:
    """Apply additive JSON metadata columns for in-development v1 databases."""

    existing_tables = _table_names(connection)
    if "ai_future_task" not in existing_tables:
        _create_future_task_tables(connection)
    if "ai_delivery_attempt" not in existing_tables:
        _create_delivery_attempt_tables(connection)
    if "ai_turn_trace" not in existing_tables:
        _create_turn_trace_tables(connection)
    if "ai_knowledge_document" not in existing_tables:
        _create_knowledge_tables(connection)

    if "ai_source" in existing_tables:
        source_columns = _column_names(connection, "ai_source")
        if "adapter_kind" not in source_columns:
            connection.execute(
                """
                ALTER TABLE ai_source
                ADD COLUMN adapter_kind TEXT NOT NULL DEFAULT 'openai_compatible'
                """
            )
        if "capability_metadata_json" not in source_columns:
            connection.execute(
                """
                ALTER TABLE ai_source
                ADD COLUMN capability_metadata_json TEXT NOT NULL DEFAULT '{}'
                """
            )
        if "default_options_json" not in source_columns:
            connection.execute(
                """
                ALTER TABLE ai_source
                ADD COLUMN default_options_json TEXT NOT NULL DEFAULT '{}'
                """
            )
        if "capability_provenance_json" not in source_columns:
            connection.execute(
                """
                ALTER TABLE ai_source
                ADD COLUMN capability_provenance_json TEXT NOT NULL DEFAULT '{}'
                """
            )
        if "preset_type" in source_columns:
            connection.execute(
                """
                UPDATE ai_source
                SET preset_type = 'openai_compatible'
                WHERE preset_type = 'openrouter'
                """
            )
        connection.execute(
            """
            UPDATE ai_source
            SET adapter_kind = CASE client_type
                WHEN 'anthropic' THEN 'anthropic_compatible'
                WHEN 'generic_rerank' THEN 'generic_rerank'
                ELSE 'openai_compatible'
            END
            WHERE adapter_kind IS NULL
                OR adapter_kind = ''
                OR (
                    adapter_kind = 'openai_compatible'
                    AND client_type IN ('anthropic', 'generic_rerank')
                )
            """
        )

    for table_name in SOURCE_MODEL_TABLE_NAMES:
        if table_name not in existing_tables:
            continue
        columns = _column_names(connection, table_name)
        if "capability_metadata_json" not in columns:
            connection.execute(
                f"""
                ALTER TABLE {table_name}
                ADD COLUMN capability_metadata_json TEXT NOT NULL DEFAULT '{{}}'
                """
            )
        if "default_options_json" not in columns:
            connection.execute(
                f"""
                ALTER TABLE {table_name}
                ADD COLUMN default_options_json TEXT NOT NULL DEFAULT '{{}}'
                """
            )
        if "capability_provenance_json" not in columns:
            connection.execute(
                f"""
                ALTER TABLE {table_name}
                ADD COLUMN capability_provenance_json TEXT NOT NULL DEFAULT '{{}}'
                """
            )

    if "chat_message" in existing_tables:
        chat_message_columns = _column_names(connection, "chat_message")
        if "turn_disposition" not in chat_message_columns:
            connection.execute(
                """
                ALTER TABLE chat_message
                ADD COLUMN turn_disposition TEXT NOT NULL DEFAULT 'active'
                    CHECK(turn_disposition IN (
                        'active',
                        'observed',
                        'generated',
                        'tool',
                        'system'
                    ))
                """
            )


def _sqlite_supports_json_valid(connection: sqlite3.Connection) -> bool:
    try:
        row = connection.execute("SELECT json_valid(?)", ("{}",)).fetchone()
    except sqlite3.DatabaseError:
        return False
    return bool(row and row[0] == 1)


def _json_check(connection: sqlite3.Connection, column_name: str) -> str:
    if _sqlite_supports_json_valid(connection):
        return f"json_valid({column_name})"
    return "1"


def _optional_json_check(connection: sqlite3.Connection, column_name: str) -> str:
    if _sqlite_supports_json_valid(connection):
        return f"{column_name} IS NULL OR json_valid({column_name})"
    return "1"


def _create_current_schema(connection: sqlite3.Connection) -> None:
    timestamp = _utcnow_text()
    connection.execute(
        """
        CREATE TABLE apeiria_schema_meta (
            id INTEGER PRIMARY KEY,
            schema_line TEXT NOT NULL CHECK(length(schema_line) > 0),
            schema_version INTEGER NOT NULL CHECK(schema_version > 0),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        INSERT INTO apeiria_schema_meta (
            id,
            schema_line,
            schema_version,
            created_at,
            updated_at
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (1, CURRENT_SCHEMA_LINE, CURRENT_SCHEMA_VERSION, timestamp, timestamp),
    )
    _create_governance_tables(connection)
    _create_ai_control_plane_tables(connection)
    _create_source_model_tables(connection)
    _create_model_routing_tables(connection)
    _create_command_statistics_tables(connection)
    _create_conversation_tables(connection)
    _create_tool_execution_tables(connection)
    _create_relationship_person_tables(connection)
    _create_memory_item_tables(connection)
    _create_knowledge_tables(connection)
    _create_future_task_tables(connection)
    _create_delivery_attempt_tables(connection)
    _create_turn_trace_tables(connection)


def _create_governance_tables(connection: sqlite3.Connection) -> None:
    disabled_plugins_check = _json_check(connection, "disabled_plugins_json")
    connection.execute(
        """
        CREATE TABLE plugin_state (
            plugin_id TEXT PRIMARY KEY,
            enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0, 1)),
            access_mode TEXT NOT NULL DEFAULT 'default_allow'
                CHECK(access_mode IN ('default_allow', 'default_deny')),
            required_level INTEGER NOT NULL DEFAULT 0 CHECK(required_level >= 0),
            protection_mode TEXT NOT NULL DEFAULT 'normal'
                CHECK(protection_mode IN ('normal', 'required')),
            ui_hidden_override INTEGER CHECK(
                ui_hidden_override IS NULL OR ui_hidden_override IN (0, 1)
            ),
            updated_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE access_rule (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_type TEXT NOT NULL CHECK(subject_type IN ('user', 'group')),
            subject_id TEXT NOT NULL,
            plugin_id TEXT NOT NULL,
            effect TEXT NOT NULL CHECK(effect IN ('allow', 'deny')),
            note TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(subject_type, subject_id, plugin_id)
        )
        """
    )
    connection.execute(
        f"""
        CREATE TABLE group_state (
            group_id TEXT PRIMARY KEY,
            group_name TEXT,
            bot_enabled INTEGER NOT NULL DEFAULT 1 CHECK(bot_enabled IN (0, 1)),
            disabled_plugins_json TEXT NOT NULL DEFAULT '[]'
                CHECK({disabled_plugins_check}),
            updated_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE user_level (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            group_id TEXT NOT NULL,
            level INTEGER NOT NULL DEFAULT 0 CHECK(level >= 0),
            updated_at TEXT NOT NULL,
            UNIQUE(user_id, group_id)
        )
        """
    )


def _create_ai_control_plane_tables(connection: sqlite3.Connection) -> None:
    custom_headers_check = _json_check(connection, "custom_headers_json")
    extra_config_check = _json_check(connection, "extra_config_json")
    capability_metadata_check = _json_check(connection, "capability_metadata_json")
    default_options_check = _json_check(connection, "default_options_json")
    capability_provenance_check = _json_check(
        connection,
        "capability_provenance_json",
    )
    connection.execute(
        f"""
        CREATE TABLE ai_source (
            source_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            capability_type TEXT NOT NULL CHECK(
                capability_type IN (
                    'chat_completion',
                    'embedding',
                    'speech_to_text',
                    'text_to_speech',
                    'rerank'
                )
            ),
            client_type TEXT NOT NULL CHECK(
                client_type IN ('openai', 'anthropic', 'generic_rerank')
            ),
            adapter_kind TEXT NOT NULL DEFAULT 'openai_compatible' CHECK(
                adapter_kind IN (
                    'openai_compatible',
                    'anthropic_compatible',
                    'generic_rerank'
                )
            ),
            preset_type TEXT NOT NULL CHECK(
                preset_type IN (
                    'openai_compatible',
                    'openai_compatible_embedding',
                    'openai_compatible_stt',
                    'openai_compatible_tts',
                    'generic_rerank_api',
                    'anthropic_compatible'
                )
            ),
            api_base TEXT,
            enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0, 1)),
            timeout_seconds INTEGER CHECK(
                timeout_seconds IS NULL OR timeout_seconds > 0
            ),
            custom_headers_json TEXT NOT NULL DEFAULT '{{}}'
                CHECK({custom_headers_check}),
            extra_config_json TEXT NOT NULL DEFAULT '{{}}'
                CHECK({extra_config_check}),
            capability_metadata_json TEXT NOT NULL DEFAULT '{{}}'
                CHECK({capability_metadata_check}),
            default_options_json TEXT NOT NULL DEFAULT '{{}}'
                CHECK({default_options_check}),
            capability_provenance_json TEXT NOT NULL DEFAULT '{{}}'
                CHECK({capability_provenance_check}),
            updated_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE ai_persona (
            persona_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            system_prompt TEXT NOT NULL,
            style_prompt TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0, 1)),
            updated_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE ai_persona_binding (
            binding_id TEXT PRIMARY KEY,
            scope_type TEXT NOT NULL CHECK(
                scope_type IN ('global', 'group', 'user', 'conversation')
            ),
            scope_id TEXT NOT NULL CHECK(length(scope_id) > 0),
            persona_id TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            CHECK(scope_type != 'global' OR scope_id = '__global__'),
            UNIQUE(scope_type, scope_id),
            FOREIGN KEY(persona_id)
                REFERENCES ai_persona(persona_id)
                ON DELETE CASCADE
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE ai_tool_policy (
            binding_id TEXT PRIMARY KEY,
            scope_type TEXT NOT NULL CHECK(
                scope_type IN ('global', 'group', 'user', 'conversation')
            ),
            scope_id TEXT NOT NULL CHECK(length(scope_id) > 0),
            allow_read_only_tools INTEGER NOT NULL DEFAULT 1
                CHECK(allow_read_only_tools IN (0, 1)),
            capability_mode TEXT NOT NULL DEFAULT 'off'
                CHECK(
                    capability_mode IN (
                        'off',
                        'private_only',
                        'direct_only'
                    )
            ),
            updated_at TEXT NOT NULL,
            CHECK(scope_type != 'global' OR scope_id = '__global__'),
            UNIQUE(scope_type, scope_id)
        )
        """
    )


def _create_source_model_tables(connection: sqlite3.Connection) -> None:
    extra_params_check = _json_check(connection, "extra_params_json")
    capability_metadata_check = _json_check(connection, "capability_metadata_json")
    default_options_check = _json_check(connection, "default_options_json")
    capability_provenance_check = _json_check(
        connection,
        "capability_provenance_json",
    )
    for table_name in SOURCE_MODEL_TABLE_NAMES:
        connection.execute(
            f"""
            CREATE TABLE {table_name} (
                model_id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                model_identifier TEXT NOT NULL,
                display_name TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0, 1)),
                is_default INTEGER NOT NULL DEFAULT 0 CHECK(is_default IN (0, 1)),
                extra_params_json TEXT NOT NULL DEFAULT '{{}}'
                    CHECK({extra_params_check}),
                capability_metadata_json TEXT NOT NULL DEFAULT '{{}}'
                    CHECK({capability_metadata_check}),
                default_options_json TEXT NOT NULL DEFAULT '{{}}'
                    CHECK({default_options_check}),
                capability_provenance_json TEXT NOT NULL DEFAULT '{{}}'
                    CHECK({capability_provenance_check}),
                updated_at TEXT NOT NULL,
                UNIQUE(source_id, model_identifier),
                FOREIGN KEY(source_id)
                    REFERENCES ai_source(source_id)
                    ON DELETE RESTRICT
            )
            """
        )
        connection.execute(
            f"""
            CREATE UNIQUE INDEX idx_{table_name}_one_default_per_source
            ON {table_name}(source_id)
            WHERE is_default = 1
            """
        )


def _create_model_routing_tables(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE ai_model_profile (
            profile_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            model_id TEXT NOT NULL,
            task_class TEXT NOT NULL CHECK(
                task_class IN (
                    'planner_light',
                    'reply_default',
                    'reply_roleplay',
                    'reasoning_heavy',
                    'memory_extraction',
                    'tool_orchestration'
                )
            ),
            priority INTEGER NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0, 1)),
            fallback_profile_id TEXT,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(model_id)
                REFERENCES ai_chat_model(model_id)
                ON DELETE RESTRICT,
            FOREIGN KEY(fallback_profile_id)
                REFERENCES ai_model_profile(profile_id)
                ON DELETE SET NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE ai_model_binding (
            binding_id TEXT PRIMARY KEY,
            scope_type TEXT NOT NULL CHECK(
                scope_type IN ('global', 'group', 'user', 'conversation')
            ),
            scope_id TEXT NOT NULL CHECK(length(scope_id) > 0),
            profile_id TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            CHECK(scope_type != 'global' OR scope_id = '__global__'),
            UNIQUE(scope_type, scope_id),
            FOREIGN KEY(profile_id)
                REFERENCES ai_model_profile(profile_id)
                ON DELETE CASCADE
        )
        """
    )


def _create_command_statistics_tables(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE command_statistics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plugin_name TEXT NOT NULL,
            command TEXT NOT NULL,
            user_id TEXT NOT NULL,
            group_id TEXT,
            called_at TEXT NOT NULL,
            success INTEGER NOT NULL DEFAULT 1 CHECK(success IN (0, 1))
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX idx_command_statistics_plugin
        ON command_statistics(plugin_name)
        """
    )
    connection.execute(
        """
        CREATE INDEX idx_command_statistics_called_at
        ON command_statistics(called_at)
        """
    )


def _create_conversation_tables(connection: sqlite3.Connection) -> None:
    extra_json_check = _optional_json_check(connection, "extra_json")
    content_json_check = _optional_json_check(connection, "content_json")
    meta_json_check = _optional_json_check(connection, "meta_json")
    raw_data_json_check = _optional_json_check(connection, "raw_data_json")
    connection.execute(
        f"""
        CREATE TABLE chat_session (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL UNIQUE,
            platform TEXT NOT NULL,
            bot_id TEXT NOT NULL,
            scene_type TEXT NOT NULL CHECK(scene_type IN ('group', 'private')),
            scene_id TEXT NOT NULL,
            subject_id TEXT,
            title TEXT,
            summary_text TEXT,
            extra_json TEXT CHECK({extra_json_check}),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_message_at TEXT NOT NULL,
            UNIQUE(platform, bot_id, scene_type, scene_id)
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX idx_chat_session_last_message_at
        ON chat_session(last_message_at)
        """
    )
    connection.execute(
        f"""
        CREATE TABLE chat_message (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id TEXT NOT NULL UNIQUE,
            session_pk INTEGER NOT NULL,
            platform_message_id TEXT,
            reply_to_message_id TEXT,
            platform_reply_id TEXT,
            author_role TEXT NOT NULL CHECK(
                author_role IN ('user', 'assistant', 'system', 'tool')
            ),
            author_id TEXT NOT NULL,
            author_name TEXT,
            message_kind TEXT NOT NULL CHECK(
                message_kind IN ('text', 'mixed', 'media', 'system', 'tool')
            ),
            turn_disposition TEXT NOT NULL DEFAULT 'active'
                CHECK({TURN_DISPOSITION_CHECK}),
            directed_to_bot INTEGER NOT NULL DEFAULT 0
                CHECK(directed_to_bot IN (0, 1)),
            mentions_bot INTEGER NOT NULL DEFAULT 0 CHECK(mentions_bot IN (0, 1)),
            has_media INTEGER NOT NULL DEFAULT 0 CHECK(has_media IN (0, 1)),
            text_content TEXT NOT NULL,
            content_json TEXT CHECK({content_json_check}),
            meta_json TEXT CHECK({meta_json_check}),
            raw_data_json TEXT CHECK({raw_data_json_check}),
            created_at TEXT NOT NULL,
            FOREIGN KEY(session_pk)
                REFERENCES chat_session(id)
                ON DELETE CASCADE
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX idx_chat_message_session_pk
        ON chat_message(session_pk)
        """
    )
    connection.execute(
        """
        CREATE INDEX idx_chat_message_author
        ON chat_message(author_role, author_id)
        """
    )
    connection.execute(
        """
        CREATE INDEX idx_chat_message_created_at
        ON chat_message(created_at)
        """
    )


def _create_tool_execution_tables(connection: sqlite3.Connection) -> None:
    input_json_check = _optional_json_check(connection, "input_json")
    output_json_check = _optional_json_check(connection, "output_json")
    connection.execute(
        f"""
        CREATE TABLE ai_tool_execution (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            execution_id TEXT NOT NULL UNIQUE,
            session_id TEXT NOT NULL,
            tool_name TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('success', 'error', 'timeout')),
            input_json TEXT CHECK({input_json_check}),
            output_json TEXT CHECK({output_json_check}),
            created_at TEXT NOT NULL,
            FOREIGN KEY(session_id)
                REFERENCES chat_session(session_id)
                ON UPDATE CASCADE
                ON DELETE CASCADE
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX idx_ai_tool_execution_session
        ON ai_tool_execution(session_id)
        """
    )
    connection.execute(
        """
        CREATE INDEX idx_ai_tool_execution_created_at
        ON ai_tool_execution(created_at)
        """
    )


def _create_relationship_person_tables(connection: sqlite3.Connection) -> None:
    memory_points_check = _json_check(connection, "memory_points_json")
    mood_tags_check = _json_check(connection, "mood_tags_json")
    connection.execute(
        f"""
        CREATE TABLE ai_person_profile (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id TEXT NOT NULL UNIQUE,
            platform TEXT NOT NULL,
            user_id TEXT NOT NULL,
            person_name TEXT,
            nickname TEXT,
            name_reason TEXT,
            memory_points_json TEXT NOT NULL DEFAULT '[]'
                CHECK({memory_points_check}),
            is_known INTEGER NOT NULL DEFAULT 0 CHECK(is_known IN (0, 1)),
            know_since TEXT,
            last_interaction TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(platform, user_id)
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX idx_ai_person_profile_last_interaction
        ON ai_person_profile(last_interaction)
        """
    )
    connection.execute(
        f"""
        CREATE TABLE ai_affinity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            affinity_id TEXT NOT NULL UNIQUE,
            platform TEXT NOT NULL,
            group_id TEXT,
            scope_key TEXT NOT NULL,
            user_id TEXT NOT NULL,
            score REAL NOT NULL DEFAULT 0.0 CHECK(score BETWEEN -1.0 AND 1.0),
            mood_tags_json TEXT NOT NULL DEFAULT '[]' CHECK({mood_tags_check}),
            last_event_at TEXT NOT NULL,
            last_decay_at TEXT,
            UNIQUE(platform, scope_key, user_id)
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX idx_ai_affinity_scope
        ON ai_affinity(platform, scope_key, user_id)
        """
    )
    connection.execute(
        """
        CREATE TABLE ai_relationship_event (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL UNIQUE,
            affinity_id TEXT NOT NULL,
            platform TEXT NOT NULL,
            group_id TEXT,
            user_id TEXT NOT NULL,
            event_type TEXT NOT NULL CHECK(
                event_type IN ('message', 'manual', 'absence_decay')
            ),
            score_delta REAL NOT NULL,
            score_after REAL NOT NULL CHECK(score_after BETWEEN -1.0 AND 1.0),
            mood_tag TEXT,
            reason TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(affinity_id)
                REFERENCES ai_affinity(affinity_id)
                ON DELETE CASCADE
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX idx_ai_relationship_event_affinity
        ON ai_relationship_event(affinity_id)
        """
    )
    connection.execute(
        """
        CREATE INDEX idx_ai_relationship_event_created_at
        ON ai_relationship_event(created_at)
        """
    )


def _create_memory_item_tables(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE ai_memory_item (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            memory_id TEXT NOT NULL UNIQUE,
            anchor_type TEXT NOT NULL CHECK(
                anchor_type IN ('scene', 'participant', 'user')
            ),
            anchor_id TEXT NOT NULL,
            memory_layer TEXT NOT NULL CHECK(
                memory_layer IN ('summary', 'long_term', 'knowledge', 'operator')
            ),
            memory_kind TEXT NOT NULL CHECK(
                memory_kind IN (
                    'fact',
                    'preference',
                    'relationship',
                    'note',
                    'impression'
                )
            ),
            content TEXT NOT NULL,
            is_editable INTEGER NOT NULL DEFAULT 1 CHECK(is_editable IN (0, 1)),
            is_ignored INTEGER NOT NULL DEFAULT 0 CHECK(is_ignored IN (0, 1)),
            source_message_id TEXT,
            salience REAL NOT NULL DEFAULT 0.5 CHECK(salience BETWEEN 0.0 AND 1.0),
            confidence REAL NOT NULL DEFAULT 0.5
                CHECK(confidence BETWEEN 0.0 AND 1.0),
            last_recalled_at TEXT,
            created_at TEXT NOT NULL,
            UNIQUE(anchor_type, anchor_id, memory_layer, memory_kind, content),
            FOREIGN KEY(source_message_id)
                REFERENCES chat_message(message_id)
                ON DELETE SET NULL
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX idx_ai_memory_item_anchor_layer_kind
        ON ai_memory_item(anchor_type, anchor_id, memory_layer, memory_kind)
        """
    )
    connection.execute(
        """
        CREATE INDEX idx_ai_memory_item_memory_id
        ON ai_memory_item(memory_id)
        """
    )
    connection.execute(
        """
        CREATE INDEX idx_ai_memory_item_created_at
        ON ai_memory_item(created_at)
        """
    )


def _create_knowledge_tables(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE ai_knowledge_document (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            source_file_name TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            content_text TEXT NOT NULL,
            status TEXT NOT NULL CHECK(
                status IN ('pending', 'embedded', 'degraded', 'failed')
            ),
            chunk_count INTEGER NOT NULL DEFAULT 0 CHECK(chunk_count >= 0),
            last_error TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX idx_ai_knowledge_document_updated_at
        ON ai_knowledge_document(updated_at)
        """
    )
    connection.execute(
        """
        CREATE TABLE ai_knowledge_chunk (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chunk_id TEXT NOT NULL UNIQUE,
            document_id TEXT NOT NULL,
            ordinal INTEGER NOT NULL CHECK(ordinal >= 0),
            chunk_hash TEXT NOT NULL,
            text TEXT NOT NULL,
            char_count INTEGER NOT NULL CHECK(char_count >= 0),
            embedding_model TEXT,
            embedding_status TEXT NOT NULL DEFAULT 'missing' CHECK(
                embedding_status IN ('missing', 'embedded', 'stale', 'failed')
            ),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(document_id, ordinal),
            FOREIGN KEY(document_id)
                REFERENCES ai_knowledge_document(document_id)
                ON DELETE CASCADE
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX idx_ai_knowledge_chunk_document
        ON ai_knowledge_chunk(document_id, ordinal)
        """
    )
    connection.execute(
        """
        CREATE INDEX idx_ai_knowledge_chunk_embedding_status
        ON ai_knowledge_chunk(embedding_status)
        """
    )


def _create_future_task_tables(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE ai_future_task (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL UNIQUE,
            session_id TEXT NOT NULL,
            platform TEXT NOT NULL,
            scene_type TEXT NOT NULL CHECK(scene_type IN ('group', 'private')),
            scene_id TEXT NOT NULL,
            user_id TEXT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            trigger_at TEXT NOT NULL,
            status TEXT NOT NULL CHECK(
                status IN ('pending', 'running', 'sent', 'cancelled', 'failed')
            ),
            source_message_id TEXT,
            scheduler_job_id TEXT,
            last_error TEXT,
            claim_count INTEGER NOT NULL DEFAULT 0 CHECK(claim_count >= 0),
            claimed_at TEXT,
            completed_at TEXT,
            recovery_reason TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX idx_ai_future_task_session
        ON ai_future_task(session_id)
        """
    )
    connection.execute(
        """
        CREATE INDEX idx_ai_future_task_status_trigger
        ON ai_future_task(status, trigger_at)
        """
    )
    connection.execute(
        """
        CREATE INDEX idx_ai_future_task_updated_at
        ON ai_future_task(updated_at)
        """
    )


def _create_delivery_attempt_tables(connection: sqlite3.Connection) -> None:
    diagnostics_check = _json_check(connection, "diagnostics_json")
    connection.execute(
        f"""
        CREATE TABLE ai_delivery_attempt (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            attempt_id TEXT NOT NULL UNIQUE,
            task_id TEXT NOT NULL,
            trace_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            delivery_intent TEXT NOT NULL,
            platform TEXT NOT NULL,
            scene_type TEXT NOT NULL CHECK(scene_type IN ('group', 'private')),
            scene_id TEXT NOT NULL,
            message_preview TEXT NOT NULL,
            message_hash TEXT NOT NULL,
            status TEXT NOT NULL CHECK(
                status IN ('pending', 'delivered', 'failed')
            ),
            reason TEXT,
            diagnostics_json TEXT NOT NULL DEFAULT '{{}}'
                CHECK({diagnostics_check}),
            channel TEXT,
            remote_message_id TEXT,
            attempt_count INTEGER NOT NULL DEFAULT 0 CHECK(attempt_count >= 0),
            delivered_at TEXT,
            failed_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX idx_ai_delivery_attempt_task_intent
        ON ai_delivery_attempt(task_id, delivery_intent, status)
        """
    )
    connection.execute(
        """
        CREATE UNIQUE INDEX idx_ai_delivery_attempt_pending
        ON ai_delivery_attempt(task_id, delivery_intent)
        WHERE status = 'pending'
        """
    )
    connection.execute(
        """
        CREATE UNIQUE INDEX idx_ai_delivery_attempt_delivered
        ON ai_delivery_attempt(task_id, delivery_intent)
        WHERE status = 'delivered'
        """
    )
    connection.execute(
        """
        CREATE INDEX idx_ai_delivery_attempt_updated_at
        ON ai_delivery_attempt(updated_at)
        """
    )


def _create_turn_trace_tables(connection: sqlite3.Connection) -> None:
    reason_codes_check = _json_check(connection, "strategy_reason_codes_json")
    diagnostics_check = _json_check(connection, "diagnostics_json")
    connection.execute(
        f"""
        CREATE TABLE ai_turn_trace (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trace_id TEXT NOT NULL UNIQUE,
            session_id TEXT NOT NULL,
            runtime_mode TEXT NOT NULL,
            terminal_status TEXT NOT NULL,
            strategy_action TEXT NOT NULL,
            strategy_reason_codes_json TEXT NOT NULL DEFAULT '[]'
                CHECK({reason_codes_check}),
            model_attempt_count INTEGER NOT NULL DEFAULT 0
                CHECK(model_attempt_count >= 0),
            tool_attempt_count INTEGER NOT NULL DEFAULT 0
                CHECK(tool_attempt_count >= 0),
            final_response_source TEXT,
            skip_reason TEXT,
            delivery_status TEXT,
            commit_status TEXT,
            diagnostics_json TEXT NOT NULL DEFAULT '{{}}'
                CHECK({diagnostics_check}),
            created_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX idx_ai_turn_trace_session
        ON ai_turn_trace(session_id, created_at)
        """
    )
    connection.execute(
        """
        CREATE INDEX idx_ai_turn_trace_created_at
        ON ai_turn_trace(created_at)
        """
    )
