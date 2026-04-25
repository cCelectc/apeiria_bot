"""Bootstrap and migrate the Apeiria SQLite control-plane schema."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from apeiria.db.runtime import ApeiriaDatabase

CURRENT_SCHEMA_LINE = "apeiria_v1"
CURRENT_SCHEMA_VERSION = 5
SCHEMA_VERSION_WITH_GOVERNANCE = 2
SCHEMA_VERSION_WITH_AI_CONTROL_PLANE = 3
SCHEMA_VERSION_WITH_MODEL_ROUTING = 4
SCHEMA_VERSION_WITH_SOURCE_MODELS = 5


class DatabaseSchemaError(RuntimeError):
    """Base error for Apeiria SQLite schema handling."""

    @classmethod
    def no_migration_path(
        cls,
        *,
        from_version: int,
        to_version: int,
    ) -> "DatabaseSchemaError":
        return cls(
            f"no migration path from apeiria_v1/{from_version} to {to_version}"
        )


class IncompatibleDatabaseError(DatabaseSchemaError):
    """Raised when the on-disk database is not compatible with apeiria_v1."""

    @classmethod
    def missing_schema_meta(cls) -> "IncompatibleDatabaseError":
        return cls("database exists without apeiria_v1 schema metadata")

    @classmethod
    def wrong_schema_line(cls) -> "IncompatibleDatabaseError":
        return cls("database schema line is not compatible with apeiria_v1")


class NewerDatabaseError(DatabaseSchemaError):
    """Raised when the on-disk database is newer than the current build."""

    @classmethod
    def current_build_too_old(cls) -> "NewerDatabaseError":
        return cls("database schema version is newer than this Apeiria build")


@dataclass(frozen=True)
class SchemaMetaRecord:
    """Observed metadata from ``apeiria_schema_meta``."""

    schema_line: str
    schema_version: int


def ensure_database_ready_sync(database: "ApeiriaDatabase | None" = None) -> None:
    """Synchronously initialize or validate the Apeiria SQLite database."""

    runtime = _coerce_database(database)
    path = runtime.database_path()
    runtime.ensure_parent_dir()

    with runtime.connect_sync() as connection:
        existing_tables = _table_names(connection)
        if not existing_tables:
            _create_schema_v1(connection)
            return

        if "apeiria_schema_meta" not in existing_tables:
            raise IncompatibleDatabaseError.missing_schema_meta()

        meta = _read_schema_meta(connection)
        if meta is None or meta.schema_line != CURRENT_SCHEMA_LINE:
            raise IncompatibleDatabaseError.wrong_schema_line()
        if meta.schema_version > CURRENT_SCHEMA_VERSION:
            raise NewerDatabaseError.current_build_too_old()
        if meta.schema_version < CURRENT_SCHEMA_VERSION:
            _backup_database(connection, path)
            _migrate(connection, from_version=meta.schema_version)


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


def _create_schema_v1(connection: sqlite3.Connection) -> None:
    timestamp = _utcnow_text()
    connection.execute(
        """
        CREATE TABLE apeiria_schema_meta (
            id INTEGER PRIMARY KEY,
            schema_line TEXT NOT NULL,
            schema_version INTEGER NOT NULL,
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
    _create_model_routing_tables(connection)
    _create_source_model_tables(connection)


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


def _backup_database(connection: sqlite3.Connection, database_path: Path) -> None:
    backup_dir = database_path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"{database_path.stem}.pre-migrate.sqlite3"
    backup_connection = sqlite3.connect(backup_path)
    try:
        connection.backup(backup_connection)
    finally:
        backup_connection.close()


def _migrate(connection: sqlite3.Connection, *, from_version: int) -> None:
    current_version = from_version
    while current_version < CURRENT_SCHEMA_VERSION:
        next_version = current_version + 1
        if current_version == 1 and next_version == SCHEMA_VERSION_WITH_GOVERNANCE:
            _create_governance_tables(connection)
            connection.execute(
                """
                UPDATE apeiria_schema_meta
                SET schema_version = ?, updated_at = ?
                WHERE id = 1
                """,
                (SCHEMA_VERSION_WITH_GOVERNANCE, _utcnow_text()),
            )
            current_version = next_version
            continue
        if (
            current_version == SCHEMA_VERSION_WITH_GOVERNANCE
            and next_version == SCHEMA_VERSION_WITH_AI_CONTROL_PLANE
        ):
            _create_ai_control_plane_tables(connection)
            connection.execute(
                """
                UPDATE apeiria_schema_meta
                SET schema_version = ?, updated_at = ?
                WHERE id = 1
                """,
                (SCHEMA_VERSION_WITH_AI_CONTROL_PLANE, _utcnow_text()),
            )
            current_version = next_version
            continue
        if (
            current_version == SCHEMA_VERSION_WITH_AI_CONTROL_PLANE
            and next_version == SCHEMA_VERSION_WITH_MODEL_ROUTING
        ):
            _create_model_routing_tables(connection)
            connection.execute(
                """
                UPDATE apeiria_schema_meta
                SET schema_version = ?, updated_at = ?
                WHERE id = 1
                """,
                (SCHEMA_VERSION_WITH_MODEL_ROUTING, _utcnow_text()),
            )
            current_version = next_version
            continue
        if (
            current_version == SCHEMA_VERSION_WITH_MODEL_ROUTING
            and next_version == SCHEMA_VERSION_WITH_SOURCE_MODELS
        ):
            _create_source_model_tables(connection)
            connection.execute(
                """
                UPDATE apeiria_schema_meta
                SET schema_version = ?, updated_at = ?
                WHERE id = 1
                """,
                (SCHEMA_VERSION_WITH_SOURCE_MODELS, _utcnow_text()),
            )
            current_version = next_version
            continue
        raise DatabaseSchemaError.no_migration_path(
            from_version=current_version,
            to_version=next_version,
        )


def _create_governance_tables(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS plugin_state (
            plugin_id TEXT PRIMARY KEY,
            enabled INTEGER NOT NULL DEFAULT 1,
            access_mode TEXT NOT NULL DEFAULT 'default_allow',
            required_level INTEGER NOT NULL DEFAULT 0,
            protection_mode TEXT NOT NULL DEFAULT 'normal',
            ui_hidden_override INTEGER,
            updated_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS access_rule (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_type TEXT NOT NULL,
            subject_id TEXT NOT NULL,
            plugin_id TEXT NOT NULL,
            effect TEXT NOT NULL,
            note TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(subject_type, subject_id, plugin_id)
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS group_state (
            group_id TEXT PRIMARY KEY,
            group_name TEXT,
            bot_enabled INTEGER NOT NULL DEFAULT 1,
            disabled_plugins_json TEXT NOT NULL DEFAULT '[]',
            updated_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS user_level (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            group_id TEXT NOT NULL,
            level INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL,
            UNIQUE(user_id, group_id)
        )
        """
    )


def _create_ai_control_plane_tables(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_source (
            source_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            capability_type TEXT NOT NULL,
            client_type TEXT NOT NULL,
            preset_type TEXT NOT NULL,
            api_base TEXT,
            api_key_env_name TEXT,
            enabled INTEGER NOT NULL DEFAULT 1,
            timeout_seconds INTEGER,
            custom_headers_json TEXT NOT NULL DEFAULT '{}',
            extra_config_json TEXT NOT NULL DEFAULT '{}',
            updated_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_persona (
            persona_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            system_prompt TEXT NOT NULL,
            style_prompt TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            updated_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_persona_binding (
            binding_id TEXT PRIMARY KEY,
            scope_type TEXT NOT NULL,
            scope_id TEXT NOT NULL,
            persona_id TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_tool_policy (
            binding_id TEXT PRIMARY KEY,
            scope_type TEXT NOT NULL,
            scope_id TEXT NOT NULL,
            allow_read_only_tools INTEGER NOT NULL DEFAULT 1,
            capability_mode TEXT NOT NULL DEFAULT 'off',
            updated_at TEXT NOT NULL
        )
        """
    )


def _create_model_routing_tables(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_model_profile (
            profile_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            model_id TEXT NOT NULL,
            task_class TEXT NOT NULL,
            priority INTEGER NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            fallback_profile_id TEXT,
            updated_at TEXT NOT NULL
        )
        """
    )


def _create_source_model_tables(connection: sqlite3.Connection) -> None:
    for table_name in (
        "ai_chat_model",
        "ai_embedding_model",
        "ai_stt_model",
        "ai_tts_model",
        "ai_rerank_model",
    ):
        connection.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                model_id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                model_identifier TEXT NOT NULL,
                display_name TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                is_default INTEGER NOT NULL DEFAULT 0,
                extra_params_json TEXT NOT NULL DEFAULT '{{}}',
                updated_at TEXT NOT NULL
            )
            """
        )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_model_binding (
            binding_id TEXT PRIMARY KEY,
            scope_type TEXT NOT NULL,
            scope_id TEXT NOT NULL,
            profile_id TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(scope_type, scope_id)
        )
        """
    )
