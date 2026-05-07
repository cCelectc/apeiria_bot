from __future__ import annotations

import asyncio
import importlib
from types import SimpleNamespace
from typing import TYPE_CHECKING

from apeiria.db.runtime import database_runtime

if TYPE_CHECKING:
    from pathlib import Path

    from pytest import MonkeyPatch


def test_source_model_admin_methods_use_new_database(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    from apeiria.app.ai.operations.sources import SourcesAdminMixin

    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    source_admin = SourcesAdminMixin()

    async def seed_source() -> str:
        created = await source_admin.create_source(
            name="Primary",
            capability_type="chat_completion",
            preset_type="openai_compatible",
            api_base="https://api.example.test/v1",
            api_key_env_name="OPENAI_API_KEY",
            enabled=True,
            timeout_seconds=30,
            custom_headers={},
            extra_config={},
        )
        return created.source_id

    source_id = asyncio.run(seed_source())

    from apeiria.app.ai.operations.models import ModelsAdminMixin

    class TestAdmin(ModelsAdminMixin):
        pass

    admin = TestAdmin()

    async def run() -> None:
        created = await admin.create_source_model(
            source_id=source_id,
            model_identifier="gpt-4o-mini",
            display_name="GPT 4o Mini",
            enabled=True,
            is_default=True,
            extra_params={"temperature": 0.2},
        )
        listed = await admin.list_source_models(source_id=source_id)
        assert [item.model_id for item in listed] == [created.model_id]
        assert created.capability_metadata["tool_calling"] is True
        assert created.capability_provenance["capability.tool_calling"]["source"] == (
            "model_template"
        )

        updated = await admin.update_source_model(
            model_id=created.model_id,
            source_id=source_id,
            model_identifier="gpt-4.1-mini",
            display_name="GPT 4.1 Mini",
            enabled=False,
            is_default=False,
            extra_params={"temperature": 0.3},
            capability_metadata={"tool_calling": False},
        )
        assert updated is not None
        assert updated.model_identifier == "gpt-4.1-mini"
        assert updated.enabled is False
        assert updated.extra_params == {"temperature": 0.3}
        assert updated.capability_metadata["tool_calling"] is False
        assert updated.capability_provenance["capability.tool_calling"]["source"] == (
            "owner_override"
        )

        deleted = await admin.delete_source_model(
            model_id=created.model_id,
            source_id=source_id,
        )
        assert deleted is True
        assert await admin.list_source_models(source_id=source_id) == []

    asyncio.run(run())


def test_fetch_and_test_source_model_uses_model_invoker(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    from apeiria.app.ai.operations.sources import SourcesAdminMixin

    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    source_admin = SourcesAdminMixin()

    async def seed_source() -> str:
        created = await source_admin.create_source(
            name="Primary",
            capability_type="chat_completion",
            preset_type="openai_compatible",
            api_base="https://api.example.test/v1",
            api_key_env_name="OPENAI_API_KEY",
            enabled=True,
            timeout_seconds=30,
            custom_headers={},
            extra_config={},
        )
        return created.source_id

    source_id = asyncio.run(seed_source())

    connectivity_module = importlib.import_module(
        "apeiria.app.ai.diagnostics.model_connectivity"
    )
    from apeiria.app.ai.operations.models import ModelsAdminMixin

    admin = ModelsAdminMixin()

    from apeiria.ai.model.runtime.adapter import AIModelCatalogItem

    catalog_item = AIModelCatalogItem(id="gpt-4o-mini", name="GPT 4o Mini")

    async def fake_list_source_models(*, source: object, api_key: str) -> list[object]:
        del source
        assert api_key == "test-key"
        return [catalog_item]

    async def fake_generate_text_for_source(**_: object) -> SimpleNamespace:
        return SimpleNamespace(content="OK", tool_calls=())

    monkeypatch.setattr(
        connectivity_module,
        "model_invoker",
        SimpleNamespace(
            list_source_models=fake_list_source_models,
            generate_text_for_source=fake_generate_text_for_source,
        ),
    )

    async def run() -> None:
        fetched = await admin.fetch_source_models(
            source_id=source_id,
            api_key="test-key",
        )
        assert fetched[0].id == "gpt-4o-mini"
        assert fetched[0].capability_metadata["tool_calling"] is True
        assert (
            fetched[0].capability_provenance["capability.tool_calling"]["source"]
            == "model_template"
        )

        tested = await admin.test_source_model(
            source_id=source_id,
            api_key="test-key",
            model_identifier="gpt-4o-mini",
        )
        assert tested == ("gpt-4o-mini", "OK", 0)

    asyncio.run(run())


def test_manual_unknown_source_model_uses_conservative_enrichment(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    from apeiria.app.ai.operations.models import ModelsAdminMixin
    from apeiria.app.ai.operations.sources import SourcesAdminMixin

    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    source_admin = SourcesAdminMixin()
    model_admin = ModelsAdminMixin()

    async def run() -> None:
        source = await source_admin.create_source(
            name="Primary",
            capability_type="chat_completion",
            preset_type="openai_compatible",
            api_base="https://api.example.test/v1",
            api_key_env_name="OPENAI_API_KEY",
            enabled=True,
            timeout_seconds=30,
            custom_headers={},
            extra_config={},
        )
        created = await model_admin.create_source_model(
            source_id=source.source_id,
            model_identifier="unknown-compatible-model",
            display_name="Unknown Compatible Model",
            enabled=True,
            is_default=True,
            extra_params={},
        )

        assert created.capability_metadata["tool_calling"] is False
        assert created.capability_provenance["capability.tool_calling"] == {
            "source": "preset_template",
            "confidence": "default",
            "detail": "conservative source-model default",
        }

    asyncio.run(run())
