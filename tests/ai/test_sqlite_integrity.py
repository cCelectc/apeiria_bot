from __future__ import annotations

import asyncio
import sqlite3
from typing import TYPE_CHECKING

from pytest import raises

from apeiria.ai.memory.service import AIMemoryCreateInput
from apeiria.app.ai.wiring import ai_wiring
from apeiria.db.runtime import database_runtime

if TYPE_CHECKING:
    from pathlib import Path

    from pytest import MonkeyPatch


def test_source_model_requires_existing_source(
    tmp_path: Path,
    monkeypatch: "MonkeyPatch",
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    with database_runtime.connect_sync() as connection, raises(
        sqlite3.IntegrityError
    ):
        _insert_source_model_raw(
            connection,
            model_id="model_orphan",
            source_id="missing-source",
            model_identifier="gpt-orphan",
            display_name="GPT Orphan",
            enabled=True,
            is_default=False,
        )


def test_duplicate_effective_tool_policy_binding_is_rejected(
    tmp_path: Path,
    monkeypatch: "MonkeyPatch",
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    with database_runtime.connect_sync() as connection:
        connection.execute(
            """
            INSERT INTO ai_tool_policy (
                binding_id,
                scope_type,
                scope_id,
                allowed_level,
                updated_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            ("policy-1", "group", "group-1", "read", "2026-04-25T00:00:00"),
        )
        with raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO ai_tool_policy (
                    binding_id,
                    scope_type,
                    scope_id,
                    allowed_level,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    "policy-2",
                    "group",
                    "group-1",
                    "host",
                    "2026-04-25T00:00:00",
                ),
            )


def test_memory_source_message_reference_is_enforced(
    tmp_path: Path,
    monkeypatch: "MonkeyPatch",
) -> None:
    from sqlalchemy.exc import IntegrityError as SAIntegrityError

    from tests.db_helpers import async_db

    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    async def scenario() -> None:
        async with async_db(database_runtime.database_path(), create_tables=False):
            with raises((sqlite3.IntegrityError, SAIntegrityError)):
                await ai_wiring.memory_service.create_memory_if_absent(
                    AIMemoryCreateInput(
                        anchor_type="user",
                        anchor_id="user-1",
                        memory_layer="long_term",
                        memory_kind="note",
                        content="orphan memory",
                        source_message_id="missing-message",
                    ),
                )

    asyncio.run(scenario())


def test_default_source_model_insert_rolls_back_on_constraint_failure(
    tmp_path: Path,
    monkeypatch: "MonkeyPatch",
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()
    _seed_source()

    with database_runtime.connect_sync() as connection:
        _insert_source_model_raw(
            connection,
            model_id="model_primary",
            source_id="source-1",
            model_identifier="gpt-primary",
            display_name="GPT Primary",
            enabled=True,
            is_default=True,
        )

    with database_runtime.connect_sync() as connection, raises(
        sqlite3.IntegrityError
    ):
        _insert_source_model_raw(
            connection,
            model_id="model_duplicate_identifier",
            source_id="source-1",
            model_identifier="gpt-primary",
            display_name="GPT Duplicate",
            enabled=True,
            is_default=True,
        )

    with database_runtime.connect_sync() as connection:
        row = connection.execute(
            """
            SELECT model_id, is_default
            FROM ai_chat_model
            WHERE source_id = ?
            """,
            ("source-1",),
        ).fetchone()

    assert row == ("model_primary", 1)


def test_default_source_model_can_be_replaced_atomically(
    tmp_path: Path,
    monkeypatch: "MonkeyPatch",
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()
    _seed_source()

    from apeiria.ai.model.catalog.storage import create_source_model
    from apeiria.db.models.ai_source import AIChatModel
    from tests.db_helpers import async_db

    async def scenario() -> None:
        async with async_db(database_runtime.database_path(), create_tables=False):
            await create_source_model(
                AIChatModel,
                model_id="model_primary",
                source_id="source-1",
                model_identifier="gpt-primary",
                display_name="GPT Primary",
                enabled=True,
                is_default=True,
                extra_params={},
            )
            await create_source_model(
                AIChatModel,
                model_id="model_secondary",
                source_id="source-1",
                model_identifier="gpt-secondary",
                display_name="GPT Secondary",
                enabled=True,
                is_default=True,
                extra_params={},
            )

    asyncio.run(scenario())

    with database_runtime.connect_sync() as connection:
        rows = connection.execute(
            """
            SELECT model_id, is_default
            FROM ai_chat_model
            WHERE source_id = ?
            ORDER BY model_id
            """,
            ("source-1",),
        ).fetchall()

    assert rows == [("model_primary", 0), ("model_secondary", 1)]


def test_ai_source_accepts_native_protocol_values(
    tmp_path: Path,
    monkeypatch: "MonkeyPatch",
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    with database_runtime.connect_sync() as connection:
        connection.execute(
            """
            INSERT OR IGNORE INTO ai_source (
                source_id,
                name,
                capability_type,
                client_type,
                adapter_kind,
                preset_type,
                api_base,
                enabled,
                custom_headers_json,
                extra_config_json,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "source-gemini",
                "Gemini",
                "chat_completion",
                "gemini",
                "gemini_native",
                "gemini_native",
                "https://generativelanguage.googleapis.com/v1beta",
                1,
                "{}",
                "{}",
                "2026-05-09T00:00:00",
            ),
        )
        connection.execute(
            """
            INSERT INTO ai_source (
                source_id,
                name,
                capability_type,
                client_type,
                adapter_kind,
                preset_type,
                api_base,
                enabled,
                custom_headers_json,
                extra_config_json,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "source-ollama",
                "Ollama",
                "embedding",
                "ollama",
                "ollama_native",
                "ollama_native_embedding",
                "http://127.0.0.1:11434",
                1,
                "{}",
                "{}",
                "2026-05-09T00:00:00",
            ),
        )

        rows = connection.execute(
            """
            SELECT source_id, client_type, adapter_kind, preset_type
            FROM ai_source
            WHERE source_id IN ('source-gemini', 'source-ollama')
            ORDER BY source_id
            """
        ).fetchall()

    assert rows == [
        ("source-gemini", "gemini", "gemini_native", "gemini_native"),
        ("source-ollama", "ollama", "ollama_native", "ollama_native_embedding"),
    ]


def test_model_route_members_require_existing_route_and_profile(
    tmp_path: Path,
    monkeypatch: "MonkeyPatch",
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    with database_runtime.connect_sync() as connection, raises(sqlite3.IntegrityError):
        connection.execute(
            """
            INSERT INTO ai_model_route_member (
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
                "route-member-orphan",
                "missing-route",
                "missing-profile",
                0,
                1,
                1,
                "2026-05-21T00:00:00",
            ),
        )


def test_model_route_binding_is_unique_per_scope_and_task(
    tmp_path: Path,
    monkeypatch: "MonkeyPatch",
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()
    _seed_model_profile("profile-primary")

    with database_runtime.connect_sync() as connection:
        connection.execute(
            """
            INSERT INTO ai_model_route (
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
                "route-1",
                "Default reply",
                "reply_default",
                "primary_fallback",
                "ordered",
                1,
                1,
                "2026-05-21T00:00:00",
            ),
        )
        connection.execute(
            """
            INSERT INTO ai_model_route_binding (
                binding_id,
                scope_type,
                scope_id,
                task_class,
                route_id,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "binding-1",
                "global",
                "__global__",
                "reply_default",
                "route-1",
                "2026-05-21T00:00:00",
            ),
        )
        with raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO ai_model_route_binding (
                    binding_id,
                    scope_type,
                    scope_id,
                    task_class,
                    route_id,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "binding-2",
                    "global",
                    "__global__",
                    "reply_default",
                    "route-1",
                    "2026-05-21T00:00:00",
                ),
            )


def test_model_route_backfill_preserves_profile_fallback_chain(
    tmp_path: Path,
    monkeypatch: "MonkeyPatch",
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()
    _seed_model_profile("profile-fallback")
    _seed_model_profile("profile-primary", fallback_profile_id="profile-fallback")

    database_runtime.ensure_ready()

    with database_runtime.connect_sync() as connection:
        rows = connection.execute(
            """
            SELECT member.profile_id
            FROM ai_model_route_member AS member
            JOIN ai_model_route AS route ON route.route_id = member.route_id
            WHERE route.task_class = 'reply_default'
            ORDER BY member.position ASC
            """
        ).fetchall()

    assert rows == [("profile-primary",), ("profile-fallback",)]


def test_model_route_backfill_breaks_legacy_fallback_cycles(
    tmp_path: Path,
    monkeypatch: "MonkeyPatch",
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()
    _seed_model_profile("profile-a")
    _seed_model_profile("profile-b")
    with database_runtime.connect_sync() as connection:
        connection.execute(
            """
            UPDATE ai_model_profile
            SET fallback_profile_id = ?
            WHERE profile_id = ?
            """,
            ("profile-b", "profile-a"),
        )
        connection.execute(
            """
            UPDATE ai_model_profile
            SET fallback_profile_id = ?
            WHERE profile_id = ?
            """,
            ("profile-a", "profile-b"),
        )

    database_runtime.ensure_ready()

    with database_runtime.connect_sync() as connection:
        rows = connection.execute(
            """
            SELECT member.profile_id
            FROM ai_model_route_member AS member
            JOIN ai_model_route AS route ON route.route_id = member.route_id
            WHERE route.task_class = 'reply_default'
            ORDER BY member.position ASC
            """
        ).fetchall()

    assert rows == [("profile-a",), ("profile-b",)]


def _seed_source() -> None:
    with database_runtime.connect_sync() as connection:
        connection.execute(
            """
            INSERT OR IGNORE INTO ai_source (
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
                "source-1",
                "Primary",
                "chat_completion",
                "openai",
                "openai_compatible",
                1,
                "{}",
                "{}",
                "2026-04-25T00:00:00",
            ),
        )


def _seed_model_profile(
    profile_id: str,
    *,
    fallback_profile_id: str | None = None,
) -> None:
    _seed_source()
    with database_runtime.connect_sync() as connection:
        _insert_source_model_raw(
            connection,
            model_id=f"model-{profile_id}",
            source_id="source-1",
            model_identifier=f"gpt-{profile_id}",
            display_name=f"GPT {profile_id}",
            enabled=True,
            is_default=False,
        )
    with database_runtime.connect_sync() as connection:
        connection.execute(
            """
            INSERT INTO ai_model_profile (
                profile_id,
                name,
                model_id,
                task_class,
                priority,
                enabled,
                fallback_profile_id,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                profile_id,
                profile_id,
                f"model-{profile_id}",
                "reply_default",
                (
                    10
                    if profile_id.endswith("primary") or profile_id == "profile-a"
                    else 20
                ),
                1,
                fallback_profile_id,
                "2026-05-21T00:00:00",
            ),
        )


def _insert_source_model_raw(
    connection: sqlite3.Connection,
    *,
    model_id: str,
    source_id: str,
    model_identifier: str,
    display_name: str,
    enabled: bool,
    is_default: bool,
) -> None:
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
            capability_metadata_json,
            default_options_json,
            capability_provenance_json,
            updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            model_id,
            source_id,
            model_identifier,
            display_name,
            1 if enabled else 0,
            1 if is_default else 0,
            "{}",
            "{}",
            "{}",
            "{}",
            "2026-05-21T00:00:00",
        ),
    )
