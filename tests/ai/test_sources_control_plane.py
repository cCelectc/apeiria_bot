from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from pytest import raises

from apeiria.db.runtime import database_runtime

if TYPE_CHECKING:
    from pathlib import Path

    from pytest import MonkeyPatch


UPDATED_TIMEOUT_SECONDS = 45


def test_sources_operations_crud_uses_new_database(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    from apeiria.app.ai.operations.sources import SourcesAdminMixin

    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()
    operations = SourcesAdminMixin()

    async def run() -> None:
        created = await operations.create_source(
            name="Primary",
            capability_type="chat_completion",
            preset_type="openai_compatible",
            api_base="https://api.example.test/v1",
            enabled=True,
            timeout_seconds=30,
            custom_headers={"X-Test": "1"},
            extra_config={"api_keys": ["test-key"], "temperature": 0.2},
        )
        sources = await operations.list_sources()
        assert len(sources) == 1
        assert sources[0].source_id == created.source_id
        assert sources[0].custom_headers == {"X-Test": "1"}

        updated = await operations.update_source(
            source_id=created.source_id,
            name="Primary Updated",
            capability_type="chat_completion",
            preset_type="openai_compatible",
            api_base="https://api.example.test/v2",
            enabled=False,
            timeout_seconds=45,
            custom_headers={"X-Test": "2"},
            extra_config={"api_keys": ["updated-key"], "temperature": 0.3},
        )
        assert updated is not None
        assert updated.name == "Primary Updated"
        assert updated.enabled is False
        assert updated.timeout_seconds == UPDATED_TIMEOUT_SECONDS
        assert updated.custom_headers == {"X-Test": "2"}
        assert updated.extra_config == {
            "api_keys": ["updated-key"],
            "temperature": 0.3,
        }

        deleted = await operations.delete_source(source_id=created.source_id)
        assert deleted is True
        assert await operations.list_sources() == []

    asyncio.run(run())


def test_source_presets_are_protocol_level_only(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    from apeiria.ai.model import UnsupportedAISourcePresetError
    from apeiria.app.ai.operations.sources import (
        SourcesAdminMixin,
        coerce_source_preset_type,
    )

    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()
    operations = SourcesAdminMixin()

    presets = operations.list_source_presets()
    preset_types = {item.preset_type for item in presets}

    assert preset_types == {
        "openai_compatible",
        "openai_compatible_embedding",
        "openai_compatible_stt",
        "openai_compatible_tts",
        "generic_rerank_api",
        "anthropic_compatible",
        "gemini_native",
        "gemini_native_embedding",
        "ollama_native",
        "ollama_native_embedding",
    }
    compatible_presets = [item for item in presets if "compatible" in item.preset_type]
    assert compatible_presets
    assert all(item.default_api_base is None for item in compatible_presets)
    assert {
        (item.preset_type, item.client_type, item.adapter_kind)
        for item in presets
        if item.preset_type
        in {
            "gemini_native",
            "gemini_native_embedding",
            "ollama_native",
            "ollama_native_embedding",
        }
    } == {
        ("gemini_native", "gemini", "gemini_native"),
        ("gemini_native_embedding", "gemini", "gemini_native"),
        ("ollama_native", "ollama", "ollama_native"),
        ("ollama_native_embedding", "ollama", "ollama_native"),
    }
    assert all(item.display_name != "OpenRouter" for item in presets)
    with raises(UnsupportedAISourcePresetError):
        coerce_source_preset_type("openrouter")


def test_source_delete_is_blocked_when_source_models_exist(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    from apeiria.app.ai.operations.errors import AISourceDeleteBlockedError
    from apeiria.app.ai.operations.models import ModelsAdminMixin
    from apeiria.app.ai.operations.sources import SourcesAdminMixin

    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()
    sources = SourcesAdminMixin()
    models = ModelsAdminMixin()

    async def run() -> None:
        source = await sources.create_source(
            name="Primary",
            capability_type="chat_completion",
            preset_type="openai_compatible",
            api_base="https://api.example.test/v1",
            enabled=True,
            timeout_seconds=30,
            custom_headers={},
            extra_config={"api_keys": ["test-key"]},
        )
        await models.create_source_model(
            source_id=source.source_id,
            model_identifier="gpt-test",
            display_name="GPT Test",
            enabled=True,
            is_default=True,
            extra_params={},
        )

        with raises(AISourceDeleteBlockedError):
            await sources.delete_source(source_id=source.source_id)

        assert [item.source_id for item in await sources.list_sources()] == [
            source.source_id
        ]

    asyncio.run(run())


def test_source_operations_rejects_openrouter_brand_preset(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    from apeiria.ai.model import UnsupportedAISourcePresetError
    from apeiria.app.ai.operations.sources import SourcesAdminMixin

    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()
    operations = SourcesAdminMixin()

    async def run() -> None:
        with raises(UnsupportedAISourcePresetError):
            await operations.create_source(
                name="OpenRouter",
                capability_type="chat_completion",
                preset_type="openrouter",
                api_base="https://openrouter.ai/api/v1",
                enabled=True,
                timeout_seconds=30,
                custom_headers={},
                extra_config={"api_keys": ["test-key"]},
            )

    asyncio.run(run())


def test_source_operations_normalizes_capability_type_from_preset(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    from apeiria.app.ai.operations.sources import SourcesAdminMixin

    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()
    operations = SourcesAdminMixin()

    async def run() -> None:
        created = await operations.create_source(
            name="Embedding Source",
            capability_type="chat_completion",
            preset_type="openai_compatible_embedding",
            api_base="https://api.example.test/v1",
            enabled=True,
            timeout_seconds=30,
            custom_headers={},
            extra_config={"api_keys": ["test-key"]},
        )
        assert created.capability_type == "embedding"
        assert created.client_type == "openai"

        updated = await operations.update_source(
            source_id=created.source_id,
            name="Rerank Source",
            capability_type="text_to_speech",
            preset_type="generic_rerank_api",
            api_base="https://api.example.test/rerank",
            enabled=True,
            timeout_seconds=15,
            custom_headers={},
            extra_config={"api_keys": ["rerank-key"]},
        )
        assert updated is not None
        assert updated.capability_type == "rerank"
        assert updated.client_type == "generic_rerank"

    asyncio.run(run())
