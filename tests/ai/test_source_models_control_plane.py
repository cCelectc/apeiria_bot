from __future__ import annotations

import asyncio
import importlib
import sys
from types import ModuleType, SimpleNamespace
from typing import TYPE_CHECKING

from apeiria.db.runtime import database_runtime

if TYPE_CHECKING:
    from pathlib import Path

    from pytest import MonkeyPatch


ORM_SESSION_UNEXPECTED = "source model CRUD should not use ORM sessions"


def test_import_ai_chat_model_service_does_not_require_nonebot_runtime() -> None:
    sys.modules.pop("apeiria.ai.model.chat_model", None)

    module = importlib.import_module("apeiria.ai.model.chat_model")

    assert module.__name__ == "apeiria.ai.model.chat_model"


def test_source_model_admin_methods_use_new_database(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    from apeiria.ai.admin.sources import SourcesAdminMixin

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

    sys.modules.pop("apeiria.ai.admin.models", None)
    sys.modules.pop("nonebot_plugin_orm", None)

    stub_nonebot_plugin_orm = ModuleType("nonebot_plugin_orm")

    def unexpected_get_session() -> None:
        raise AssertionError(ORM_SESSION_UNEXPECTED)

    stub_nonebot_plugin_orm.get_session = unexpected_get_session  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "nonebot_plugin_orm", stub_nonebot_plugin_orm)

    admin_models = importlib.import_module("apeiria.ai.admin.models")

    class TestAdmin(admin_models.ModelsAdminMixin):
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

        updated = await admin.update_source_model(
            model_id=created.model_id,
            source_id=source_id,
            model_identifier="gpt-4.1-mini",
            display_name="GPT 4.1 Mini",
            enabled=False,
            is_default=False,
            extra_params={"temperature": 0.3},
        )
        assert updated is not None
        assert updated.model_identifier == "gpt-4.1-mini"
        assert updated.enabled is False
        assert updated.extra_params == {"temperature": 0.3}

        deleted = await admin.delete_source_model(
            model_id=created.model_id,
            source_id=source_id,
        )
        assert deleted is True
        assert await admin.list_source_models(source_id=source_id) == []

    asyncio.run(run())


def test_fetch_and_test_source_model_do_not_use_orm_session(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    from apeiria.ai.admin.sources import SourcesAdminMixin

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

    sys.modules.pop("apeiria.ai.admin.models", None)
    sys.modules.pop("nonebot_plugin_orm", None)

    stub_nonebot_plugin_orm = ModuleType("nonebot_plugin_orm")

    def unexpected_get_session() -> None:
        raise AssertionError(ORM_SESSION_UNEXPECTED)

    stub_nonebot_plugin_orm.get_session = unexpected_get_session  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "nonebot_plugin_orm", stub_nonebot_plugin_orm)

    admin_models = importlib.import_module("apeiria.ai.admin.models")
    model_service = importlib.import_module("apeiria.ai.model.service")
    admin = admin_models.ModelsAdminMixin()

    catalog_item = SimpleNamespace(id="catalog-model")

    async def fake_list_source_models(*, source: object, api_key: str) -> list[object]:
        del source
        assert api_key == "test-key"
        return [catalog_item]

    async def fake_generate_text_for_source(**_: object) -> SimpleNamespace:
        return SimpleNamespace(content="OK", tool_calls=())

    monkeypatch.setattr(
        model_service,
        "ai_model_facade",
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
        assert fetched == [catalog_item]

        tested = await admin.test_source_model(
            source_id=source_id,
            api_key="test-key",
            model_identifier="gpt-4o-mini",
        )
        assert tested == ("gpt-4o-mini", "OK", 0)

    asyncio.run(run())
