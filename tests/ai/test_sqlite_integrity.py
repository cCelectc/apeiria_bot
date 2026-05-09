from __future__ import annotations

import asyncio
import sqlite3
from typing import TYPE_CHECKING

from pytest import raises

from apeiria.ai.memory.service import AIMemoryCreateInput, ai_memory_service
from apeiria.ai.model.catalog.storage import create_source_model
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

    with raises(sqlite3.IntegrityError):
        create_source_model(
            "ai_chat_model",
            model_id="model_orphan",
            source_id="missing-source",
            model_identifier="gpt-orphan",
            display_name="GPT Orphan",
            enabled=True,
            is_default=False,
            extra_params={},
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
                allow_read_only_tools,
                capability_mode,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("policy-1", "group", "group-1", 1, "off", "2026-04-25T00:00:00"),
        )
        with raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO ai_tool_policy (
                    binding_id,
                    scope_type,
                    scope_id,
                    allow_read_only_tools,
                    capability_mode,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "policy-2",
                    "group",
                    "group-1",
                    0,
                    "private_only",
                    "2026-04-25T00:00:00",
                ),
            )


def test_memory_source_message_reference_is_enforced(
    tmp_path: Path,
    monkeypatch: "MonkeyPatch",
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    async def scenario() -> None:
        with raises(sqlite3.IntegrityError):
            await ai_memory_service.create_memory_if_absent(
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

    create_source_model(
        "ai_chat_model",
        model_id="model_primary",
        source_id="source-1",
        model_identifier="gpt-primary",
        display_name="GPT Primary",
        enabled=True,
        is_default=True,
        extra_params={},
    )

    with raises(sqlite3.IntegrityError):
        create_source_model(
            "ai_chat_model",
            model_id="model_duplicate_identifier",
            source_id="source-1",
            model_identifier="gpt-primary",
            display_name="GPT Duplicate",
            enabled=True,
            is_default=True,
            extra_params={},
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

    create_source_model(
        "ai_chat_model",
        model_id="model_primary",
        source_id="source-1",
        model_identifier="gpt-primary",
        display_name="GPT Primary",
        enabled=True,
        is_default=True,
        extra_params={},
    )
    create_source_model(
        "ai_chat_model",
        model_id="model_secondary",
        source_id="source-1",
        model_identifier="gpt-secondary",
        display_name="GPT Secondary",
        enabled=True,
        is_default=True,
        extra_params={},
    )

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


def _seed_source() -> None:
    with database_runtime.connect_sync() as connection:
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
