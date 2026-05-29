"""Bootstrap and validate the Apeiria SQLite schema."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apeiria.db.runtime import ApeiriaDatabase

CURRENT_SCHEMA_LINE = "apeiria_v1"
CURRENT_SCHEMA_VERSION = 3
WEBUI_AUTH_SIMPLIFIED_SCHEMA_VERSION = 2
SUPPORTED_MIGRATION_SOURCE_VERSIONS = frozenset({1, 2})

TOOL_LEVEL_VALUES: tuple[str, ...] = ("none", "read", "write", "host", "admin")
TOOL_LEVEL_CHECK = "allowed_level IN ('none', 'read', 'write', 'host', 'admin')"
TOOL_OBSERVATION_STATUS_VALUES: tuple[str, ...] = (
    "success",
    "error",
    "timeout",
    "denied",
    "not_ready",
)
TOOL_OBSERVATION_STATUS_CHECK = (
    "status IN ('success', 'error', 'timeout', 'denied', 'not_ready')"
)

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
MEMORY_ANCHOR_VALUES: tuple[str, ...] = (
    "operator",
    "scene",
    "participant",
    "user",
    "project",
)
MEMORY_LIFECYCLE_VALUES: tuple[str, ...] = (
    "candidate",
    "active",
    "suppressed",
    "archived",
)
MEMORY_USE_MODE_VALUES: tuple[str, ...] = (
    "ignore",
    "silent",
    "context",
    "explicit",
)
MEMORY_ACTION_VALUES: tuple[str, ...] = (
    "accept",
    "reject",
    "reinforce",
    "revise",
    "rescope",
    "suppress",
    "activate",
    "archive",
    "supersede",
    "delete",
)
PROFILE_NAME_SOURCE_VALUES: tuple[str, ...] = (
    "manual",
    "self_introduced",
    "platform",
    "inferred",
)
PROFILE_NAME_VISIBILITY_VALUES: tuple[str, ...] = (
    "private_only",
    "public_allowed",
    "disabled",
)
RELATIONSHIP_EVENT_TYPE_VALUES: tuple[str, ...] = (
    "message",
    "manual",
    "decay",
)
AI_MODEL_TASK_CLASS_VALUES: tuple[str, ...] = (
    "planner_light",
    "reply_default",
    "reply_roleplay",
    "reasoning_heavy",
    "memory_extraction",
    "tool_orchestration",
)
AI_MODEL_ROUTE_MODE_VALUES: tuple[str, ...] = (
    "primary_fallback",
    "load_balance",
)
AI_MODEL_ROUTE_ALGORITHM_VALUES: tuple[str, ...] = (
    "ordered",
    "weighted_random",
)
AI_MODEL_ROUTE_SCOPE_VALUES: tuple[str, ...] = (
    "global",
    "group",
    "user",
    "conversation",
)


class DatabaseSchemaError(RuntimeError):
    """Base error for Apeiria SQLite schema handling."""


class IncompatibleDatabaseError(DatabaseSchemaError):
    """Raised when the on-disk database is not compatible with Apeiria SQLite."""

    @classmethod
    def missing_schema_meta(cls) -> "IncompatibleDatabaseError":
        return cls("database exists without apeiria_v1 schema metadata")

    @classmethod
    def wrong_schema_line(cls) -> "IncompatibleDatabaseError":
        return cls("database schema line is not compatible with apeiria_v1")


class UnsupportedDatabaseVersionError(DatabaseSchemaError):
    """Raised when an unsupported SQLite schema version is encountered."""

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
            f"expected {CURRENT_SCHEMA_LINE}/{expected}"
        )

    @classmethod
    def future_schema_version(
        cls,
        *,
        observed: int,
        expected: int,
    ) -> "UnsupportedDatabaseVersionError":
        return cls(
            "database schema version "
            f"{observed} is newer than this Apeiria build supports; "
            f"use a newer build or restore a {CURRENT_SCHEMA_LINE}/{expected} backup"
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
        if meta.schema_version == CURRENT_SCHEMA_VERSION:
            _ensure_current_schema_shape(connection)
            return
        if meta.schema_version in SUPPORTED_MIGRATION_SOURCE_VERSIONS:
            _migrate_schema_to_current(connection, meta)
            return
        if meta.schema_version > CURRENT_SCHEMA_VERSION:
            raise UnsupportedDatabaseVersionError.future_schema_version(
                observed=meta.schema_version,
                expected=CURRENT_SCHEMA_VERSION,
            )
        raise UnsupportedDatabaseVersionError.unsupported_schema_version(
            observed=meta.schema_version,
            expected=CURRENT_SCHEMA_VERSION,
        )


def _migrate_schema_to_current(
    connection: sqlite3.Connection,
    meta: SchemaMetaRecord,
) -> None:
    if meta.schema_version == 1:
        _migrate_v1_to_v2(connection)
        _migrate_v2_to_v3(connection)
        return
    if meta.schema_version == WEBUI_AUTH_SIMPLIFIED_SCHEMA_VERSION:
        _migrate_v2_to_v3(connection)
        return
    raise UnsupportedDatabaseVersionError.unsupported_schema_version(
        observed=meta.schema_version,
        expected=CURRENT_SCHEMA_VERSION,
    )


def _migrate_v1_to_v2(connection: sqlite3.Connection) -> None:
    _ensure_current_schema_shape(connection)
    _ensure_webui_auth_tables(connection)
    _set_schema_version(connection, WEBUI_AUTH_SIMPLIFIED_SCHEMA_VERSION)


def _migrate_v2_to_v3(connection: sqlite3.Connection) -> None:
    _replace_webui_auth_tables_v3(connection)
    _set_schema_version(connection, CURRENT_SCHEMA_VERSION)


def _set_schema_version(connection: sqlite3.Connection, schema_version: int) -> None:
    connection.execute(
        """
        UPDATE apeiria_schema_meta
        SET schema_version = ?, updated_at = ?
        WHERE id = 1
        """,
        (schema_version, _utcnow_text()),
    )
    row = connection.execute(
        """
        SELECT changes()
        """
    ).fetchone()
    if row is None or int(row[0]) != 1:
        raise IncompatibleDatabaseError.missing_schema_meta()


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


def _table_sql(connection: sqlite3.Connection, table_name: str) -> str:
    row = connection.execute(
        """
        SELECT sql
        FROM sqlite_master
        WHERE type = 'table' AND name = ?
        """,
        (table_name,),
    ).fetchone()
    return str(row[0]) if row else ""


def _ensure_current_schema_shape(  # noqa: C901, PLR0912, PLR0915
    connection: sqlite3.Connection,
) -> None:
    """Apply additive JSON metadata columns for in-development v1 databases."""

    existing_tables = _table_names(connection)
    _ensure_governance_shape(connection, existing_tables)
    existing_tables = _table_names(connection)
    if "ai_future_task" not in existing_tables:
        _create_future_task_tables(connection)
    if "ai_delivery_attempt" not in existing_tables:
        _create_delivery_attempt_tables(connection)
    if "ai_turn_trace" not in existing_tables:
        _create_turn_trace_tables(connection)
    if "ai_model_usage_event" not in existing_tables:
        _create_model_usage_tables(connection)
    if "ai_knowledge_document" not in existing_tables:
        _create_knowledge_tables(connection)
    if "ai_managed_session" not in existing_tables:
        _create_ai_session_management_tables(connection)
    if "ai_runtime_settings" not in existing_tables:
        _create_ai_runtime_settings_table(connection)
    if "ai_runtime_settings" in existing_tables:
        runtime_setting_columns = _column_names(connection, "ai_runtime_settings")
        if "quiet_hours_enabled" not in runtime_setting_columns:
            connection.execute(
                """
                ALTER TABLE ai_runtime_settings
                ADD COLUMN quiet_hours_enabled INTEGER CHECK(
                    quiet_hours_enabled IS NULL OR quiet_hours_enabled IN (0, 1)
                )
                """
            )
        if "quiet_hours_start_minute" not in runtime_setting_columns:
            connection.execute(
                """
                ALTER TABLE ai_runtime_settings
                ADD COLUMN quiet_hours_start_minute INTEGER CHECK(
                    quiet_hours_start_minute IS NULL
                        OR (
                            quiet_hours_start_minute >= 0
                            AND quiet_hours_start_minute <= 1439
                        )
                )
                """
            )
        if "quiet_hours_end_minute" not in runtime_setting_columns:
            connection.execute(
                """
                ALTER TABLE ai_runtime_settings
                ADD COLUMN quiet_hours_end_minute INTEGER CHECK(
                    quiet_hours_end_minute IS NULL
                        OR (
                            quiet_hours_end_minute >= 0
                            AND quiet_hours_end_minute <= 1439
                        )
                )
                """
            )
        if "night_awake_lease_minutes" not in runtime_setting_columns:
            connection.execute(
                """
                ALTER TABLE ai_runtime_settings
                ADD COLUMN night_awake_lease_minutes INTEGER CHECK(
                    night_awake_lease_minutes IS NULL
                        OR (
                            night_awake_lease_minutes >= 1
                            AND night_awake_lease_minutes <= 120
                        )
                )
                """
            )
    if (
        not {
            "ai_model_route",
            "ai_model_route_member",
            "ai_model_route_binding",
        }
        <= existing_tables
    ):
        _create_model_route_tables(connection)
    _backfill_model_routes_from_profiles(connection)
    _ensure_webui_auth_tables(connection)
    _replace_webui_auth_tables_v3(connection)
    _ensure_context_summary_shape(connection, existing_tables)
    if "ai_tool_policy" in existing_tables:
        _replace_ai_tool_policy_if_legacy(connection)
    if "ai_tool_execution" in existing_tables:
        _replace_ai_tool_execution_if_legacy(connection)

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

    if "ai_memory_item" in existing_tables:
        _ensure_memory_belief_shape(connection)
    if "ai_memory_belief_action" not in existing_tables:
        _create_memory_belief_action_table(connection)
    _ensure_profile_relationship_shape(connection)


def _ensure_governance_shape(
    connection: sqlite3.Connection,
    existing_tables: set[str],
) -> None:
    if "plugin_state" in existing_tables:
        plugin_state_columns = _column_names(connection, "plugin_state")
        if "required_level" in plugin_state_columns:
            _replace_plugin_state_without_required_level(connection)
    if "user_level" in existing_tables:
        connection.execute("DROP TABLE user_level")


def _replace_plugin_state_without_required_level(
    connection: sqlite3.Connection,
) -> None:
    connection.execute("ALTER TABLE plugin_state RENAME TO plugin_state_legacy")
    connection.execute(
        """
        CREATE TABLE plugin_state (
            plugin_id TEXT PRIMARY KEY,
            enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0, 1)),
            access_mode TEXT NOT NULL DEFAULT 'default_allow'
                CHECK(access_mode IN ('default_allow', 'default_deny')),
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
        INSERT INTO plugin_state (
            plugin_id,
            enabled,
            access_mode,
            protection_mode,
            ui_hidden_override,
            updated_at
        )
        SELECT
            plugin_id,
            enabled,
            access_mode,
            protection_mode,
            ui_hidden_override,
            updated_at
        FROM plugin_state_legacy
        """
    )
    connection.execute("DROP TABLE plugin_state_legacy")


def _ensure_context_summary_shape(
    connection: sqlite3.Connection,
    existing_tables: set[str],
) -> None:
    if "chat_session_context_summary" not in existing_tables:
        _create_chat_session_context_summary_table(connection)
    if "chat_session" not in existing_tables:
        return
    chat_session_columns = _column_names(connection, "chat_session")
    if "summary_text" in chat_session_columns:
        connection.execute("UPDATE chat_session SET summary_text = NULL")


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


def _literal_check(column_name: str, values: tuple[str, ...]) -> str:
    rendered = ", ".join(f"'{value}'" for value in values)
    return f"{column_name} IN ({rendered})"


def _ensure_memory_belief_shape(connection: sqlite3.Connection) -> None:
    columns = _column_names(connection, "ai_memory_item")
    if "lifecycle_state" not in columns:
        connection.execute(
            """
            ALTER TABLE ai_memory_item
            ADD COLUMN lifecycle_state TEXT NOT NULL DEFAULT 'active'
                CHECK(lifecycle_state IN (
                    'candidate',
                    'active',
                    'suppressed',
                    'archived'
                ))
            """
        )
        if "is_ignored" in columns:
            connection.execute(
                """
                UPDATE ai_memory_item
                SET lifecycle_state = 'suppressed'
                WHERE is_ignored = 1
                """
            )
    if "default_use_mode" not in columns:
        connection.execute(
            """
            ALTER TABLE ai_memory_item
            ADD COLUMN default_use_mode TEXT NOT NULL DEFAULT 'context'
                CHECK(default_use_mode IN (
                    'ignore',
                    'silent',
                    'context',
                    'explicit'
                ))
            """
        )
    if "governance_reason" not in columns:
        connection.execute(
            """
            ALTER TABLE ai_memory_item
            ADD COLUMN governance_reason TEXT
            """
        )
    connection.execute(
        """
        UPDATE ai_memory_item
        SET default_use_mode = 'ignore'
        WHERE lifecycle_state != 'active'
        """
    )


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
    _create_profile_relationship_tables(connection)
    _create_memory_item_tables(connection)
    _create_memory_belief_action_table(connection)
    _create_knowledge_tables(connection)
    _create_future_task_tables(connection)
    _create_delivery_attempt_tables(connection)
    _create_turn_trace_tables(connection)
    _create_model_usage_tables(connection)
    _create_ai_session_management_tables(connection)
    _create_ai_runtime_settings_table(connection)
    _create_webui_auth_tables(connection)


def _ensure_webui_auth_tables(connection: sqlite3.Connection) -> None:
    _create_webui_auth_tables(connection)


def _create_webui_auth_tables(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS webui_auth_secret (
            id INTEGER PRIMARY KEY CHECK(id = 1),
            token_secret TEXT NOT NULL CHECK(length(token_secret) > 0),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS webui_account (
            user_id TEXT PRIMARY KEY,
            username TEXT NOT NULL UNIQUE CHECK(length(username) > 0),
            password_hash TEXT NOT NULL CHECK(length(password_hash) > 0),
            is_disabled INTEGER NOT NULL DEFAULT 0 CHECK(is_disabled IN (0, 1)),
            last_login_at TEXT,
            password_changed_at TEXT,
            session_version INTEGER NOT NULL DEFAULT 0 CHECK(session_version >= 0),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_webui_account_username
        ON webui_account(username)
        """
    )


def _replace_webui_auth_tables_v3(connection: sqlite3.Connection) -> None:
    connection.execute("DROP TABLE IF EXISTS webui_registration_code")
    connection.execute("DROP TABLE IF EXISTS webui_security_audit_event")
    account_columns = _column_names(connection, "webui_account")
    expected_columns = {
        "user_id",
        "username",
        "password_hash",
        "is_disabled",
        "last_login_at",
        "password_changed_at",
        "session_version",
        "created_at",
        "updated_at",
    }
    if account_columns == expected_columns:
        return
    connection.execute("DROP INDEX IF EXISTS idx_webui_account_username")
    connection.execute("DROP TABLE IF EXISTS webui_account")
    _create_webui_auth_tables(connection)


def _create_governance_tables(connection: sqlite3.Connection) -> None:
    disabled_plugins_check = _json_check(connection, "disabled_plugins_json")
    connection.execute(
        """
        CREATE TABLE plugin_state (
            plugin_id TEXT PRIMARY KEY,
            enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0, 1)),
            access_mode TEXT NOT NULL DEFAULT 'default_allow'
                CHECK(access_mode IN ('default_allow', 'default_deny')),
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
                client_type IN (
                    'openai',
                    'anthropic',
                    'generic_rerank',
                    'gemini',
                    'ollama'
                )
            ),
            adapter_kind TEXT NOT NULL DEFAULT 'openai_compatible' CHECK(
                adapter_kind IN (
                    'openai_compatible',
                    'anthropic_compatible',
                    'generic_rerank',
                    'gemini_native',
                    'ollama_native'
                )
            ),
            preset_type TEXT NOT NULL CHECK(
                preset_type IN (
                    'openai_compatible',
                    'openai_compatible_embedding',
                    'openai_compatible_stt',
                    'openai_compatible_tts',
                    'generic_rerank_api',
                    'anthropic_compatible',
                    'gemini_native',
                    'gemini_native_embedding',
                    'ollama_native',
                    'ollama_native_embedding'
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
    _create_tool_policy_table(connection)


def _create_ai_runtime_settings_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE ai_runtime_settings (
            id INTEGER PRIMARY KEY CHECK(id = 1),
            allow_group_initiative INTEGER CHECK(
                allow_group_initiative IS NULL
                    OR allow_group_initiative IN (0, 1)
            ),
            quiet_hours_enabled INTEGER CHECK(
                quiet_hours_enabled IS NULL OR quiet_hours_enabled IN (0, 1)
            ),
            quiet_hours_start_minute INTEGER CHECK(
                quiet_hours_start_minute IS NULL
                    OR (
                        quiet_hours_start_minute >= 0
                        AND quiet_hours_start_minute <= 1439
                    )
            ),
            quiet_hours_end_minute INTEGER CHECK(
                quiet_hours_end_minute IS NULL
                    OR (
                        quiet_hours_end_minute >= 0
                        AND quiet_hours_end_minute <= 1439
                    )
            ),
            night_awake_lease_minutes INTEGER CHECK(
                night_awake_lease_minutes IS NULL
                    OR (
                        night_awake_lease_minutes >= 1
                        AND night_awake_lease_minutes <= 120
                    )
            ),
            stt_input_enabled INTEGER CHECK(
                stt_input_enabled IS NULL OR stt_input_enabled IN (0, 1)
            ),
            persist_raw_event_payloads INTEGER CHECK(
                persist_raw_event_payloads IS NULL
                    OR persist_raw_event_payloads IN (0, 1)
            ),
            ambient_merge_window_ms INTEGER CHECK(
                ambient_merge_window_ms IS NULL OR ambient_merge_window_ms >= 0
            ),
            max_pending_messages INTEGER CHECK(
                max_pending_messages IS NULL OR max_pending_messages >= 1
            ),
            group_reply_cooldown_seconds INTEGER CHECK(
                group_reply_cooldown_seconds IS NULL
                    OR group_reply_cooldown_seconds >= 0
            ),
            max_consecutive_ambient_replies INTEGER CHECK(
                max_consecutive_ambient_replies IS NULL
                    OR max_consecutive_ambient_replies >= 0
            ),
            direct_bypass_ambient_budget INTEGER CHECK(
                direct_bypass_ambient_budget IS NULL
                    OR direct_bypass_ambient_budget IN (0, 1)
            ),
            duplicate_event_ttl_seconds INTEGER CHECK(
                duplicate_event_ttl_seconds IS NULL
                    OR duplicate_event_ttl_seconds >= 1
            ),
            tool_execution_timeout_seconds REAL CHECK(
                tool_execution_timeout_seconds IS NULL
                    OR tool_execution_timeout_seconds > 0
            ),
            cleanup_interval_minutes INTEGER CHECK(
                cleanup_interval_minutes IS NULL OR cleanup_interval_minutes >= 1
            ),
            conversation_retention_days INTEGER CHECK(
                conversation_retention_days IS NULL
                    OR conversation_retention_days >= 1
            ),
            raw_event_retention_days INTEGER CHECK(
                raw_event_retention_days IS NULL OR raw_event_retention_days >= 1
            ),
            tool_execution_retention_days INTEGER CHECK(
                tool_execution_retention_days IS NULL
                    OR tool_execution_retention_days >= 1
            ),
            suppressed_memory_retention_days INTEGER CHECK(
                suppressed_memory_retention_days IS NULL
                    OR suppressed_memory_retention_days >= 1
            ),
            updated_at TEXT NOT NULL
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
        f"""
        CREATE TABLE ai_model_profile (
            profile_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            model_id TEXT NOT NULL,
            task_class TEXT NOT NULL CHECK(
                {_literal_check("task_class", AI_MODEL_TASK_CLASS_VALUES)}
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
        f"""
        CREATE TABLE ai_model_binding (
            binding_id TEXT PRIMARY KEY,
            scope_type TEXT NOT NULL CHECK(
                {_literal_check("scope_type", AI_MODEL_ROUTE_SCOPE_VALUES)}
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
    _create_model_route_tables(connection)


def _create_model_route_tables(connection: sqlite3.Connection) -> None:
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS ai_model_route (
            route_id TEXT PRIMARY KEY,
            name TEXT NOT NULL CHECK(length(name) > 0),
            task_class TEXT NOT NULL CHECK(
                {_literal_check("task_class", AI_MODEL_TASK_CLASS_VALUES)}
            ),
            mode TEXT NOT NULL CHECK(
                {_literal_check("mode", AI_MODEL_ROUTE_MODE_VALUES)}
            ),
            algorithm TEXT NOT NULL CHECK(
                {_literal_check("algorithm", AI_MODEL_ROUTE_ALGORITHM_VALUES)}
            ),
            fallback_on_failure INTEGER NOT NULL DEFAULT 1
                CHECK(fallback_on_failure IN (0, 1)),
            enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0, 1)),
            updated_at TEXT NOT NULL,
            CHECK(mode != 'primary_fallback' OR algorithm = 'ordered'),
            CHECK(mode != 'load_balance' OR algorithm = 'weighted_random')
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_ai_model_route_task_class
        ON ai_model_route(task_class, enabled)
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_model_route_member (
            route_member_id TEXT PRIMARY KEY,
            route_id TEXT NOT NULL,
            profile_id TEXT NOT NULL,
            position INTEGER NOT NULL CHECK(position >= 0),
            weight INTEGER NOT NULL DEFAULT 1 CHECK(weight > 0),
            enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0, 1)),
            updated_at TEXT NOT NULL,
            UNIQUE(route_id, profile_id),
            UNIQUE(route_id, position),
            FOREIGN KEY(route_id)
                REFERENCES ai_model_route(route_id)
                ON DELETE CASCADE,
            FOREIGN KEY(profile_id)
                REFERENCES ai_model_profile(profile_id)
                ON DELETE CASCADE
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_ai_model_route_member_route
        ON ai_model_route_member(route_id, enabled, position)
        """
    )
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS ai_model_route_binding (
            binding_id TEXT PRIMARY KEY,
            scope_type TEXT NOT NULL CHECK(
                {_literal_check("scope_type", AI_MODEL_ROUTE_SCOPE_VALUES)}
            ),
            scope_id TEXT NOT NULL CHECK(length(scope_id) > 0),
            task_class TEXT NOT NULL CHECK(
                {_literal_check("task_class", AI_MODEL_TASK_CLASS_VALUES)}
            ),
            route_id TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            CHECK(scope_type != 'global' OR scope_id = '__global__'),
            UNIQUE(scope_type, scope_id, task_class),
            FOREIGN KEY(route_id)
                REFERENCES ai_model_route(route_id)
                ON DELETE CASCADE
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_ai_model_route_binding_route
        ON ai_model_route_binding(route_id)
        """
    )


def _backfill_model_routes_from_profiles(connection: sqlite3.Connection) -> None:
    existing_tables = _table_names(connection)
    if (
        not {
            "ai_model_profile",
            "ai_model_route",
            "ai_model_route_member",
            "ai_model_route_binding",
        }
        <= existing_tables
    ):
        return

    existing_route = connection.execute(
        """
        SELECT route_id
        FROM ai_model_route
        LIMIT 1
        """
    ).fetchone()
    if existing_route is not None:
        return

    rows = connection.execute(
        """
        SELECT profile_id, task_class, priority, fallback_profile_id
        FROM ai_model_profile
        WHERE enabled = 1
        ORDER BY task_class ASC, priority ASC, profile_id ASC
        """
    ).fetchall()
    if not rows:
        return

    profiles_by_id = {str(row[0]): row for row in rows}
    profiles_by_task: dict[str, list[tuple[object, ...]]] = {}
    for row in rows:
        profiles_by_task.setdefault(str(row[1]), []).append(row)

    timestamp = _utcnow_text()
    for task_class, task_profiles in profiles_by_task.items():
        route_id = f"route_default_{task_class}"
        connection.execute(
            """
            INSERT OR IGNORE INTO ai_model_route (
                route_id,
                name,
                task_class,
                mode,
                algorithm,
                fallback_on_failure,
                enabled,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                route_id,
                f"Default {task_class}",
                task_class,
                "primary_fallback",
                "ordered",
                1,
                1,
                timestamp,
            ),
        )
        connection.execute(
            """
            INSERT OR IGNORE INTO ai_model_route_binding (
                binding_id,
                scope_type,
                scope_id,
                task_class,
                route_id,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                f"route_binding_default_{task_class}",
                "global",
                "__global__",
                task_class,
                route_id,
                timestamp,
            ),
        )
        ordered_profile_ids: list[str] = []
        for row in task_profiles:
            for profile_id in _legacy_profile_chain(
                start_profile_id=str(row[0]),
                profiles_by_id=profiles_by_id,
            ):
                if profile_id not in ordered_profile_ids:
                    ordered_profile_ids.append(profile_id)

        for position, profile_id in enumerate(ordered_profile_ids):
            connection.execute(
                """
                INSERT OR IGNORE INTO ai_model_route_member (
                    route_member_id,
                    route_id,
                    profile_id,
                    position,
                    weight,
                    enabled,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"route_member_default_{task_class}_{position}",
                    route_id,
                    profile_id,
                    position,
                    1,
                    1,
                    timestamp,
                ),
            )


def _legacy_profile_chain(
    *,
    start_profile_id: str,
    profiles_by_id: dict[str, tuple[object, ...]],
) -> list[str]:
    chain: list[str] = []
    visited: set[str] = set()
    current_profile_id: str | None = start_profile_id
    while current_profile_id and current_profile_id not in visited:
        row = profiles_by_id.get(current_profile_id)
        if row is None:
            break
        visited.add(current_profile_id)
        chain.append(current_profile_id)
        fallback_profile_id = row[3]
        current_profile_id = (
            str(fallback_profile_id) if fallback_profile_id is not None else None
        )
    return chain


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
    _create_chat_session_context_summary_table(connection)
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


def _create_chat_session_context_summary_table(
    connection: sqlite3.Connection,
) -> None:
    connection.execute(
        """
        CREATE TABLE chat_session_context_summary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            summary_text TEXT NOT NULL CHECK(length(summary_text) > 0),
            source_until_message_id TEXT NOT NULL,
            source_until_created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(session_id),
            FOREIGN KEY(session_id)
                REFERENCES chat_session(session_id)
                ON DELETE CASCADE
                ON UPDATE CASCADE
        )
        """
    )


def _create_ai_session_management_tables(connection: sqlite3.Connection) -> None:
    source_labels_check = _json_check(connection, "source_labels_json")
    diagnostic_raw_ids_check = _json_check(connection, "diagnostic_raw_ids_json")
    connection.execute(
        f"""
        CREATE TABLE ai_managed_session (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL UNIQUE,
            platform_id TEXT NOT NULL,
            platform_type TEXT NOT NULL,
            message_type TEXT NOT NULL CHECK(
                message_type IN ('group', 'private', 'web_chat')
            ),
            subject_id TEXT NOT NULL,
            source_labels_json TEXT NOT NULL DEFAULT '{{}}'
                CHECK({source_labels_check}),
            diagnostic_raw_ids_json TEXT NOT NULL DEFAULT '{{}}'
                CHECK({diagnostic_raw_ids_check}),
            ai_enabled INTEGER NOT NULL DEFAULT 1 CHECK(ai_enabled IN (0, 1)),
            persona_id TEXT,
            context_reset_at TEXT,
            context_reset_by TEXT,
            last_observed_at TEXT,
            last_user_message_at TEXT,
            last_ai_message_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            audit_created_by TEXT,
            audit_updated_by TEXT,
            UNIQUE(platform_id, platform_type, message_type, subject_id),
            FOREIGN KEY(persona_id)
                REFERENCES ai_persona(persona_id)
                ON DELETE SET NULL
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX idx_ai_managed_session_source
        ON ai_managed_session(platform_id, platform_type, message_type, subject_id)
        """
    )
    connection.execute(
        """
        CREATE INDEX idx_ai_managed_session_recent
        ON ai_managed_session(last_observed_at, updated_at)
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
            status TEXT NOT NULL CHECK({TOOL_OBSERVATION_STATUS_CHECK}),
            trace_id TEXT,
            call_id TEXT,
            reason TEXT,
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


def _create_tool_policy_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        f"""
        CREATE TABLE ai_tool_policy (
            binding_id TEXT PRIMARY KEY,
            scope_type TEXT NOT NULL CHECK(
                scope_type IN ('global', 'group', 'user', 'conversation')
            ),
            scope_id TEXT NOT NULL CHECK(length(scope_id) > 0),
            allowed_level TEXT NOT NULL DEFAULT 'none'
                CHECK({TOOL_LEVEL_CHECK}),
            updated_at TEXT NOT NULL,
            CHECK(scope_type != 'global' OR scope_id = '__global__'),
            UNIQUE(scope_type, scope_id)
        )
        """
    )


def _replace_ai_tool_policy_if_legacy(connection: sqlite3.Connection) -> None:
    columns = _column_names(connection, "ai_tool_policy")
    if "allowed_level" in columns and "capability_mode" not in columns:
        return
    connection.execute("DROP TABLE ai_tool_policy")
    _create_tool_policy_table(connection)


def _replace_ai_tool_execution_if_legacy(connection: sqlite3.Connection) -> None:
    columns = _column_names(connection, "ai_tool_execution")
    if {"trace_id", "call_id", "reason"} <= columns:
        return
    connection.execute("DROP TABLE ai_tool_execution")
    _create_tool_execution_tables(connection)


def _create_profile_relationship_tables(connection: sqlite3.Connection) -> None:
    _create_profile_table(connection)
    _create_affinity_table(connection)
    _create_relationship_event_table(connection)


def _ensure_profile_relationship_shape(connection: sqlite3.Connection) -> None:
    existing_tables = _table_names(connection)
    if "ai_profile" not in existing_tables:
        _create_profile_table(connection)
    if "ai_person_profile" in _table_names(connection):
        _migrate_person_profile_to_profile(connection)
        connection.execute("DROP TABLE ai_person_profile")

    existing_tables = _table_names(connection)
    if "ai_affinity" not in existing_tables:
        _create_affinity_table(connection)
    elif _relationship_affinity_needs_replacement(connection):
        _replace_legacy_affinity_tables(connection)

    if "ai_relationship_event" not in _table_names(connection):
        _create_relationship_event_table(connection)
    elif _relationship_event_needs_replacement(connection):
        _replace_legacy_relationship_event_table(connection)


def _migrate_person_profile_to_profile(connection: sqlite3.Connection) -> None:
    timestamp = _utcnow_text()
    connection.execute(
        """
        INSERT INTO ai_profile (
            profile_id,
            platform,
            user_id,
            display_name,
            preferred_name,
            name_source,
            name_visibility,
            profile_enabled,
            last_interaction_at,
            created_at,
            updated_at
        )
        SELECT
            'profile_' || lower(hex(randomblob(16))),
            platform,
            user_id,
            person_name,
            COALESCE(nickname, person_name),
            CASE
                WHEN nickname IS NOT NULL OR person_name IS NOT NULL
                    THEN 'self_introduced'
                ELSE NULL
            END,
            'public_allowed',
            1,
            COALESCE(last_interaction, ?),
            created_at,
            updated_at
        FROM ai_person_profile
        WHERE 1
        ON CONFLICT(platform, user_id) DO UPDATE SET
            display_name = COALESCE(ai_profile.display_name, excluded.display_name),
            preferred_name = COALESCE(
                ai_profile.preferred_name,
                excluded.preferred_name
            ),
            name_source = COALESCE(ai_profile.name_source, excluded.name_source),
            last_interaction_at = CASE
                WHEN excluded.last_interaction_at > ai_profile.last_interaction_at
                    THEN excluded.last_interaction_at
                ELSE ai_profile.last_interaction_at
            END,
            updated_at = CASE
                WHEN excluded.updated_at > ai_profile.updated_at
                    THEN excluded.updated_at
                ELSE ai_profile.updated_at
            END
        """,
        (timestamp,),
    )


def _relationship_affinity_needs_replacement(
    connection: sqlite3.Connection,
) -> bool:
    columns = _column_names(connection, "ai_affinity")
    if "group_id" in columns or "scope_key" in columns:
        return True
    table_sql = _table_sql(connection, "ai_affinity")
    return "BETWEEN -1.0 AND 1.0" in table_sql or "REAL" in table_sql


def _relationship_event_needs_replacement(
    connection: sqlite3.Connection,
) -> bool:
    columns = _column_names(connection, "ai_relationship_event")
    if "group_id" in columns or "scene_id" not in columns:
        return True
    table_sql = _table_sql(connection, "ai_relationship_event")
    return "absence_decay" in table_sql or "BETWEEN -1.0 AND 1.0" in table_sql


def _replace_legacy_affinity_tables(connection: sqlite3.Connection) -> None:
    if "ai_relationship_event" in _table_names(connection):
        connection.execute("DROP TABLE ai_relationship_event")
    connection.execute("ALTER TABLE ai_affinity RENAME TO ai_affinity_legacy")
    _create_affinity_table(connection)
    connection.execute(
        """
        INSERT OR IGNORE INTO ai_affinity (
            affinity_id,
            platform,
            user_id,
            score,
            mood_tags_json,
            last_event_at,
            last_decay_at
        )
        SELECT
            affinity_id,
            platform,
            user_id,
            CAST(max(-100, min(100, round(score * 100))) AS INTEGER),
            mood_tags_json,
            last_event_at,
            last_decay_at
        FROM ai_affinity_legacy
        ORDER BY last_event_at DESC, id DESC
        """,
    )
    connection.execute("DROP TABLE ai_affinity_legacy")


def _replace_legacy_relationship_event_table(connection: sqlite3.Connection) -> None:
    connection.execute("DROP TABLE ai_relationship_event")
    _create_relationship_event_table(connection)


def _create_profile_table(connection: sqlite3.Connection) -> None:
    name_visibility_check = _literal_check(
        "name_visibility",
        PROFILE_NAME_VISIBILITY_VALUES,
    )
    connection.execute(
        f"""
        CREATE TABLE ai_profile (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_id TEXT NOT NULL UNIQUE,
            platform TEXT NOT NULL,
            user_id TEXT NOT NULL,
            display_name TEXT,
            preferred_name TEXT,
            name_source TEXT CHECK(
                name_source IS NULL
                OR {_literal_check("name_source", PROFILE_NAME_SOURCE_VALUES)}
            ),
            name_visibility TEXT NOT NULL DEFAULT 'public_allowed'
                CHECK({name_visibility_check}),
            profile_enabled INTEGER NOT NULL DEFAULT 1
                CHECK(profile_enabled IN (0, 1)),
            last_interaction_at TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(platform, user_id)
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX idx_ai_profile_last_interaction
        ON ai_profile(last_interaction_at)
        """
    )


def _create_affinity_table(connection: sqlite3.Connection) -> None:
    mood_tags_check = _json_check(connection, "mood_tags_json")
    connection.execute(
        f"""
        CREATE TABLE ai_affinity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            affinity_id TEXT NOT NULL UNIQUE,
            platform TEXT NOT NULL,
            user_id TEXT NOT NULL,
            score INTEGER NOT NULL DEFAULT 0 CHECK(score BETWEEN -100 AND 100),
            mood_tags_json TEXT NOT NULL DEFAULT '[]' CHECK({mood_tags_check}),
            last_event_at TEXT NOT NULL,
            last_decay_at TEXT,
            UNIQUE(platform, user_id)
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX idx_ai_affinity_user
        ON ai_affinity(platform, user_id)
        """
    )


def _create_relationship_event_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        f"""
        CREATE TABLE ai_relationship_event (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL UNIQUE,
            affinity_id TEXT NOT NULL,
            platform TEXT NOT NULL,
            user_id TEXT NOT NULL,
            scene_id TEXT,
            event_type TEXT NOT NULL
                CHECK({_literal_check("event_type", RELATIONSHIP_EVENT_TYPE_VALUES)}),
            score_delta INTEGER NOT NULL,
            score_after INTEGER NOT NULL CHECK(score_after BETWEEN -100 AND 100),
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
                anchor_type IN ('operator', 'scene', 'participant', 'user', 'project')
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
            lifecycle_state TEXT NOT NULL DEFAULT 'active' CHECK(
                lifecycle_state IN ('candidate', 'active', 'suppressed', 'archived')
            ),
            default_use_mode TEXT NOT NULL DEFAULT 'context' CHECK(
                default_use_mode IN ('ignore', 'silent', 'context', 'explicit')
            ),
            governance_reason TEXT,
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


def _create_memory_belief_action_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE ai_memory_belief_action (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action_id TEXT NOT NULL UNIQUE,
            memory_id TEXT,
            action TEXT NOT NULL CHECK(
                action IN (
                    'accept',
                    'reject',
                    'reinforce',
                    'revise',
                    'rescope',
                    'suppress',
                    'activate',
                    'archive',
                    'supersede',
                    'delete'
                )
            ),
            actor_type TEXT NOT NULL CHECK(
                actor_type IN ('system', 'user', 'operator', 'tool')
            ),
            reason TEXT,
            source_message_id TEXT,
            previous_state TEXT,
            next_state TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(memory_id)
                REFERENCES ai_memory_item(memory_id)
                ON DELETE SET NULL,
            FOREIGN KEY(source_message_id)
                REFERENCES chat_message(message_id)
                ON DELETE SET NULL
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX idx_ai_memory_belief_action_memory_id
        ON ai_memory_belief_action(memory_id)
        """
    )
    connection.execute(
        """
        CREATE INDEX idx_ai_memory_belief_action_created_at
        ON ai_memory_belief_action(created_at)
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


def _create_model_usage_tables(connection: sqlite3.Connection) -> None:
    provider_usage_check = _optional_json_check(connection, "provider_usage_json")
    connection.execute(
        f"""
        CREATE TABLE ai_model_usage_event (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usage_event_id TEXT NOT NULL UNIQUE,
            trace_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            runtime_mode TEXT NOT NULL,
            response_source TEXT NOT NULL,
            source_id TEXT NOT NULL,
            model_name TEXT NOT NULL,
            operation TEXT NOT NULL,
            attempt_index INTEGER NOT NULL CHECK(attempt_index >= 1),
            status TEXT NOT NULL,
            usage_available INTEGER NOT NULL CHECK(usage_available IN (0, 1)),
            measurement_source TEXT NOT NULL CHECK(
                measurement_source IN ('provider', 'missing')
            ),
            input_tokens INTEGER CHECK(input_tokens IS NULL OR input_tokens >= 0),
            output_tokens INTEGER CHECK(output_tokens IS NULL OR output_tokens >= 0),
            total_tokens INTEGER CHECK(total_tokens IS NULL OR total_tokens >= 0),
            cached_input_tokens INTEGER
                CHECK(cached_input_tokens IS NULL OR cached_input_tokens >= 0),
            reasoning_tokens INTEGER
                CHECK(reasoning_tokens IS NULL OR reasoning_tokens >= 0),
            audio_input_tokens INTEGER
                CHECK(audio_input_tokens IS NULL OR audio_input_tokens >= 0),
            audio_output_tokens INTEGER
                CHECK(audio_output_tokens IS NULL OR audio_output_tokens >= 0),
            provider_usage_json TEXT CHECK({provider_usage_check}),
            provider_response_id TEXT,
            finish_reason TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX idx_ai_model_usage_event_trace
        ON ai_model_usage_event(trace_id, created_at)
        """
    )
    connection.execute(
        """
        CREATE INDEX idx_ai_model_usage_event_session
        ON ai_model_usage_event(session_id, created_at)
        """
    )
    connection.execute(
        """
        CREATE INDEX idx_ai_model_usage_event_source_model
        ON ai_model_usage_event(source_id, model_name, created_at)
        """
    )
    connection.execute(
        """
        CREATE INDEX idx_ai_model_usage_event_response_source
        ON ai_model_usage_event(response_source, created_at)
        """
    )
    connection.execute(
        """
        CREATE INDEX idx_ai_model_usage_event_operation
        ON ai_model_usage_event(operation, created_at)
        """
    )
    connection.execute(
        """
        CREATE INDEX idx_ai_model_usage_event_created_at
        ON ai_model_usage_event(created_at)
        """
    )
