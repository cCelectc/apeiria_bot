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
        assert "capability_provenance_json" in _table_sql(
            connection,
            "ai_source",
        )
        assert "json_valid(capability_provenance_json)" in _table_sql(
            connection,
            "ai_source",
        )
        for table_name in SOURCE_MODEL_TABLE_NAMES:
            assert "capability_provenance_json" in _table_sql(
                connection,
                table_name,
            )
            assert "json_valid(capability_provenance_json)" in _table_sql(
                connection,
                table_name,
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


def test_database_ensure_ready_adds_provider_metadata_columns_to_v1_shape(
    tmp_path: Path,
) -> None:
    database = ApeiriaDatabase(project_root=tmp_path)
    _create_minimal_legacy_ai_model_tables(database)

    database.ensure_ready()

    with database.connect_sync() as connection:
        source_row = connection.execute(
            """
            SELECT adapter_kind, capability_metadata_json, default_options_json
                , capability_provenance_json
            FROM ai_source
            WHERE source_id = ?
            """,
            ("source-legacy",),
        ).fetchone()
        model_row = connection.execute(
            """
            SELECT capability_metadata_json, default_options_json
                , capability_provenance_json
            FROM ai_chat_model
            WHERE model_id = ?
            """,
            ("model-legacy",),
        ).fetchone()

    assert source_row == ("anthropic_compatible", "{}", "{}", "{}")
    assert model_row == ("{}", "{}", "{}")


def _create_schema_meta(
    database: ApeiriaDatabase,
    *,
    schema_line: str,
    schema_version: int,
) -> None:
    with database.connect_sync() as connection:
        _create_schema_meta_in_connection(
            connection,
            schema_line=schema_line,
            schema_version=schema_version,
        )


def _create_minimal_legacy_ai_model_tables(database: ApeiriaDatabase) -> None:
    with database.connect_sync() as connection:
        _create_schema_meta_in_connection(
            connection,
            schema_line=CURRENT_SCHEMA_LINE,
            schema_version=CURRENT_SCHEMA_VERSION,
        )
        connection.execute(
            """
            CREATE TABLE ai_source (
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
            INSERT INTO ai_source (
                source_id,
                name,
                capability_type,
                client_type,
                preset_type,
                enabled,
                custom_headers_json,
                extra_config_json,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "source-legacy",
                "Legacy",
                "chat_completion",
                "anthropic",
                "anthropic_compatible",
                1,
                "{}",
                "{}",
                "2026-04-25T00:00:00",
            ),
        )
        for table_name in SOURCE_MODEL_TABLE_NAMES:
            connection.execute(
                f"""
                CREATE TABLE {table_name} (
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
            INSERT INTO ai_chat_model (
                model_id,
                source_id,
                model_identifier,
                display_name,
                enabled,
                is_default,
                extra_params_json,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "model-legacy",
                "source-legacy",
                "claude-legacy",
                "Claude Legacy",
                1,
                1,
                "{}",
                "2026-04-25T00:00:00",
            ),
        )


def _create_schema_meta_in_connection(
    connection: "Connection",
    *,
    schema_line: str,
    schema_version: int,
) -> None:
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
