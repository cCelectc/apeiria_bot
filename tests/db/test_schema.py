from __future__ import annotations

from typing import TYPE_CHECKING

from pytest import raises

from apeiria.db.runtime import ApeiriaDatabase
from apeiria.db.schema import (
    CURRENT_SCHEMA_LINE,
    CURRENT_SCHEMA_VERSION,
    IncompatibleDatabaseError,
)

if TYPE_CHECKING:
    from pathlib import Path


def test_database_ensure_ready_initializes_empty_sqlite_db(tmp_path: Path) -> None:
    database = ApeiriaDatabase(project_root=tmp_path)

    database.ensure_ready()

    assert database.database_path() == tmp_path / "data" / "db" / "apeiria.sqlite3"
    assert database.database_path().is_file()
    with database.connect_sync() as connection:
        row = connection.execute(
            "SELECT schema_line, schema_version FROM apeiria_schema_meta WHERE id = 1"
        ).fetchone()
        tables = {
            item[0]
            for item in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
    assert row == (CURRENT_SCHEMA_LINE, CURRENT_SCHEMA_VERSION)
    assert {
        "apeiria_schema_meta",
        "plugin_state",
        "access_rule",
        "group_state",
        "user_level",
        "ai_source",
        "ai_chat_model",
        "ai_embedding_model",
        "ai_stt_model",
        "ai_tts_model",
        "ai_rerank_model",
        "ai_model_profile",
        "ai_model_binding",
        "ai_persona",
        "ai_persona_binding",
        "ai_tool_policy",
    } <= tables


def test_database_ensure_ready_rejects_non_apeiria_v1_database(tmp_path: Path) -> None:
    database = ApeiriaDatabase(project_root=tmp_path)
    db_path = database.database_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with database.connect_sync() as connection:
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
            """
            ,
            (1, "legacy_line", 99, "2026-04-25T00:00:00", "2026-04-25T00:00:00"),
        )

    with raises(IncompatibleDatabaseError):
        database.ensure_ready()


def test_database_ensure_ready_migrates_v1_database_to_current_version(
    tmp_path: Path,
) -> None:
    database = ApeiriaDatabase(project_root=tmp_path)
    with database.connect_sync() as connection:
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
            (1, CURRENT_SCHEMA_LINE, 1, "2026-04-25T00:00:00", "2026-04-25T00:00:00"),
        )

    database.ensure_ready()

    with database.connect_sync() as connection:
        row = connection.execute(
            "SELECT schema_version FROM apeiria_schema_meta WHERE id = 1"
        ).fetchone()
        tables = {
            item[0]
            for item in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
    assert row == (CURRENT_SCHEMA_VERSION,)
    assert "plugin_state" in tables
    assert "ai_source" in tables
    assert "ai_chat_model" in tables
    assert "ai_model_profile" in tables


def test_database_ensure_ready_migrates_v2_database_to_current_version(
    tmp_path: Path,
) -> None:
    database = ApeiriaDatabase(project_root=tmp_path)
    with database.connect_sync() as connection:
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
            CREATE TABLE plugin_state (
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
            CREATE TABLE access_rule (
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
            CREATE TABLE group_state (
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
            CREATE TABLE user_level (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                group_id TEXT NOT NULL,
                level INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL,
                UNIQUE(user_id, group_id)
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
            (1, CURRENT_SCHEMA_LINE, 2, "2026-04-25T00:00:00", "2026-04-25T00:00:00"),
        )

    database.ensure_ready()

    with database.connect_sync() as connection:
        row = connection.execute(
            "SELECT schema_version FROM apeiria_schema_meta WHERE id = 1"
        ).fetchone()
        tables = {
            item[0]
            for item in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
    assert row == (CURRENT_SCHEMA_VERSION,)
    assert {
        "ai_source",
        "ai_chat_model",
        "ai_embedding_model",
        "ai_stt_model",
        "ai_tts_model",
        "ai_rerank_model",
        "ai_model_profile",
        "ai_model_binding",
        "ai_persona",
        "ai_persona_binding",
        "ai_tool_policy",
    } <= tables
