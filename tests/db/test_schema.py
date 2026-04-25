from __future__ import annotations

from typing import TYPE_CHECKING

from pytest import raises

from apeiria.db.runtime import ApeiriaDatabase
from apeiria.db.schema import (
    CURRENT_SCHEMA_LINE,
    CURRENT_SCHEMA_VERSION,
    SOURCE_MODEL_TABLE_NAMES,
    IncompatibleDatabaseError,
    UnsupportedDatabaseVersionError,
)

if TYPE_CHECKING:
    from pathlib import Path
    from sqlite3 import Connection


def test_database_ensure_ready_initializes_empty_sqlite_db(tmp_path: Path) -> None:
    database = ApeiriaDatabase(project_root=tmp_path)

    database.ensure_ready()

    assert database.database_path() == tmp_path / "data" / "db" / "apeiria.sqlite3"
    assert database.database_path().is_file()
    with database.connect_sync() as connection:
        row = connection.execute(
            "SELECT schema_line, schema_version FROM apeiria_schema_meta WHERE id = 1"
        ).fetchone()
        tables = _table_names(connection)
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
        "command_statistics",
        "ai_tool_execution",
        "ai_person_profile",
        "ai_affinity",
        "ai_relationship_event",
        "ai_memory_item",
        "chat_session",
        "chat_message",
    } <= tables


def test_database_ensure_ready_rejects_non_apeiria_v1_database(tmp_path: Path) -> None:
    database = ApeiriaDatabase(project_root=tmp_path)
    _create_schema_meta(database, schema_line="legacy_line", schema_version=99)

    with raises(IncompatibleDatabaseError):
        database.ensure_ready()


def test_database_ensure_ready_rejects_unsupported_schema_version(
    tmp_path: Path,
) -> None:
    database = ApeiriaDatabase(project_root=tmp_path)
    _create_schema_meta(
        database,
        schema_line=CURRENT_SCHEMA_LINE,
        schema_version=CURRENT_SCHEMA_VERSION + 1,
    )

    with raises(UnsupportedDatabaseVersionError):
        database.ensure_ready()


def test_database_schema_declares_foreign_keys_and_delete_rules(
    tmp_path: Path,
) -> None:
    database = ApeiriaDatabase(project_root=tmp_path)
    database.ensure_ready()

    with database.connect_sync() as connection:
        assert (
            "ai_source",
            "source_id",
            "source_id",
            "RESTRICT",
        ) in _foreign_keys(connection, "ai_chat_model")
        assert (
            "ai_chat_model",
            "model_id",
            "model_id",
            "RESTRICT",
        ) in _foreign_keys(connection, "ai_model_profile")
        assert (
            "ai_model_profile",
            "profile_id",
            "profile_id",
            "CASCADE",
        ) in _foreign_keys(connection, "ai_model_binding")
        assert (
            "ai_persona",
            "persona_id",
            "persona_id",
            "CASCADE",
        ) in _foreign_keys(connection, "ai_persona_binding")
        assert (
            "chat_session",
            "session_id",
            "session_id",
            "CASCADE",
        ) in _foreign_key_update_actions(connection, "ai_tool_execution")
        assert (
            "chat_session",
            "session_id",
            "session_id",
            "CASCADE",
        ) in _foreign_keys(connection, "ai_tool_execution")
        assert (
            "chat_session",
            "session_pk",
            "id",
            "CASCADE",
        ) in _foreign_keys(connection, "chat_message")
        assert (
            "ai_affinity",
            "affinity_id",
            "affinity_id",
            "CASCADE",
        ) in _foreign_keys(connection, "ai_relationship_event")
        assert (
            "chat_message",
            "source_message_id",
            "message_id",
            "SET NULL",
        ) in _foreign_keys(connection, "ai_memory_item")


def test_database_schema_declares_unique_bindings_and_default_indexes(
    tmp_path: Path,
) -> None:
    database = ApeiriaDatabase(project_root=tmp_path)
    database.ensure_ready()

    with database.connect_sync() as connection:
        assert "UNIQUE(scope_type, scope_id)" in _table_sql(
            connection,
            "ai_model_binding",
        )
        assert "UNIQUE(scope_type, scope_id)" in _table_sql(
            connection,
            "ai_persona_binding",
        )
        assert "UNIQUE(scope_type, scope_id)" in _table_sql(
            connection,
            "ai_tool_policy",
        )
        for table_name in SOURCE_MODEL_TABLE_NAMES:
            index_sql = _index_sql(
                connection,
                f"idx_{table_name}_one_default_per_source",
            )
            assert f"ON {table_name}(source_id)" in index_sql
            assert "WHERE is_default = 1" in index_sql


def test_database_schema_declares_value_checks(tmp_path: Path) -> None:
    database = ApeiriaDatabase(project_root=tmp_path)
    database.ensure_ready()

    with database.connect_sync() as connection:
        assert "CHECK(enabled IN (0, 1))" in _table_sql(connection, "ai_source")
        assert "json_valid(custom_headers_json)" in _table_sql(
            connection,
            "ai_source",
        )
        assert "scope_type IN" in _table_sql(connection, "ai_tool_policy")
        assert "'private_and_tome'" not in _table_sql(connection, "ai_tool_policy")
        assert "CHECK(status IN ('success', 'error', 'timeout'))" in _table_sql(
            connection,
            "ai_tool_execution",
        )
        assert "CHECK(score BETWEEN -1.0 AND 1.0)" in _table_sql(
            connection,
            "ai_affinity",
        )
        assert "CHECK(salience BETWEEN 0.0 AND 1.0)" in _table_sql(
            connection,
            "ai_memory_item",
        )
        assert "CHECK(directed_to_bot IN (0, 1))" in _table_sql(
            connection,
            "chat_message",
        )


def _create_schema_meta(
    database: ApeiriaDatabase,
    *,
    schema_line: str,
    schema_version: int,
) -> None:
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
            (
                1,
                schema_line,
                schema_version,
                "2026-04-25T00:00:00",
                "2026-04-25T00:00:00",
            ),
        )


def _table_names(connection: "Connection") -> set[str]:
    return {
        str(item[0])
        for item in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }


def _foreign_keys(
    connection: "Connection",
    table_name: str,
) -> set[tuple[str, str, str, str]]:
    return {
        (str(row[2]), str(row[3]), str(row[4]), str(row[6]))
        for row in connection.execute(f"PRAGMA foreign_key_list({table_name})")
    }


def _foreign_key_update_actions(
    connection: "Connection",
    table_name: str,
) -> set[tuple[str, str, str, str]]:
    return {
        (str(row[2]), str(row[3]), str(row[4]), str(row[5]))
        for row in connection.execute(f"PRAGMA foreign_key_list({table_name})")
    }


def _table_sql(connection: "Connection", table_name: str) -> str:
    row = connection.execute(
        """
        SELECT sql
        FROM sqlite_master
        WHERE type = 'table' AND name = ?
        """,
        (table_name,),
    ).fetchone()
    assert row is not None
    return str(row[0])


def _index_sql(connection: "Connection", index_name: str) -> str:
    row = connection.execute(
        """
        SELECT sql
        FROM sqlite_master
        WHERE type = 'index' AND name = ?
        """,
        (index_name,),
    ).fetchone()
    assert row is not None
    return str(row[0])
