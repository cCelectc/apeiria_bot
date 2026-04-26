from __future__ import annotations

import asyncio
import importlib
import sys
from types import ModuleType
from typing import TYPE_CHECKING

from apeiria.db.runtime import database_runtime

if TYPE_CHECKING:
    from pathlib import Path

    from pytest import MonkeyPatch


UPDATED_PRIORITY = 5
ORM_SESSION_UNEXPECTED = "profile/binding admin methods should not use ORM sessions"


def test_import_ai_model_profile_service_does_not_require_nonebot_runtime() -> None:
    sys.modules.pop("apeiria.ai.model.profile", None)

    module = importlib.import_module("apeiria.ai.model.profile")

    assert module.__name__ == "apeiria.ai.model.profile"


def test_import_ai_admin_models_does_not_require_nonebot_plugin_orm() -> None:
    sys.modules.pop("apeiria.app.ai.admin.models", None)
    sys.modules.pop("nonebot_plugin_orm", None)

    module = importlib.import_module("apeiria.app.ai.admin.models")

    assert module.__name__ == "apeiria.app.ai.admin.models"


def test_model_profile_service_uses_new_database(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    from apeiria.ai.model.bindings import AIModelBindingTarget
    from apeiria.ai.model.models import AIModelRouteQuery
    from apeiria.ai.model.profile import (
        AIModelProfileCreateInput,
        ai_model_profile_service,
    )

    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()
    _seed_chat_models_for_profiles()

    async def run() -> None:
        created = await ai_model_profile_service.create_profile(
            AIModelProfileCreateInput(
                name="Reply Default",
                model_id="model_chat_primary",
                task_class="reply_default",
                priority=10,
                enabled=True,
            ),
        )
        profiles = await ai_model_profile_service.list_profiles()
        assert created.profile_id in {item.profile_id for item in profiles}

        updated = await ai_model_profile_service.update_profile(
            profile_id=created.profile_id,
            create_input=AIModelProfileCreateInput(
                name="Reply Primary",
                model_id="model_chat_primary",
                task_class="reply_default",
                priority=5,
                enabled=True,
                fallback_profile_id="fallback_profile",
            ),
        )
        assert updated is not None
        assert updated.name == "Reply Primary"
        assert updated.priority == UPDATED_PRIORITY
        assert updated.fallback_profile_id == "fallback_profile"

        with database_runtime.connect_sync() as connection:
            connection.execute(
                """
                INSERT INTO ai_model_binding (
                    binding_id,
                    scope_type,
                    scope_id,
                    profile_id,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    "binding-1",
                    "conversation",
                    "conversation-1",
                    created.profile_id,
                    "2026-04-25T00:00:00",
                ),
            )

        bindings = await ai_model_profile_service.list_bindings()
        assert len(bindings) == 1
        assert bindings[0].binding_id == "binding-1"

        resolved = await ai_model_profile_service.resolve_profile(
            AIModelRouteQuery(task_class="reply_default"),
        )
        assert resolved is not None
        assert resolved.profile_id == created.profile_id

        bound = await ai_model_profile_service.resolve_profile_for_target(
            target=AIModelBindingTarget(
                conversation_id="conversation-1",
                group_id=None,
                user_id=None,
            ),
        )
        assert bound is not None
        assert bound.profile_id == created.profile_id

    asyncio.run(run())


def test_models_admin_profile_and_binding_methods_use_new_database(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    from apeiria.ai.model.bindings import AIModelBindingTarget
    from apeiria.ai.model.models import AIModelRouteQuery
    from apeiria.ai.model.profile import AIModelProfileCreateInput

    sys.modules.pop("apeiria.app.ai.admin.models", None)

    stub_nonebot_plugin_orm = ModuleType("nonebot_plugin_orm")

    def unexpected_get_session() -> None:
        raise AssertionError(ORM_SESSION_UNEXPECTED)

    stub_nonebot_plugin_orm.get_session = unexpected_get_session  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "nonebot_plugin_orm", stub_nonebot_plugin_orm)

    admin_models = importlib.import_module("apeiria.app.ai.admin.models")

    class TestAdmin(admin_models.ModelsAdminMixin):
        pass

    async def fake_build_profile_create_input(
        *args: object,
        **kwargs: object,
    ) -> AIModelProfileCreateInput:
        assert len(args) == 1
        return AIModelProfileCreateInput(
            name=str(kwargs["name"]),
            model_id=str(kwargs["model_id"]),
            task_class=kwargs["task_class"],  # type: ignore[arg-type]
            priority=(
                kwargs["priority"]
                if isinstance(kwargs["priority"], int)
                else int(str(kwargs["priority"]))
            ),
            enabled=bool(kwargs["enabled"]),
            fallback_profile_id=(
                str(kwargs["fallback_profile_id"])
                if kwargs["fallback_profile_id"] is not None
                else None
            ),
        )

    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()
    _seed_chat_models_for_profiles()
    monkeypatch.setattr(
        TestAdmin,
        "_build_profile_create_input",
        fake_build_profile_create_input,
    )

    async def run() -> None:
        admin = TestAdmin()

        created = await admin.create_model_profile(
            name="Reply Default",
            model_id="model_chat_primary",
            task_class="reply_default",
            priority=10,
            enabled=True,
            fallback_profile_id=None,
        )
        assert created.name == "Reply Default"

        listed_profiles = await admin.list_model_profiles()
        assert listed_profiles[0].profile_id == created.profile_id

        updated = await admin.update_model_profile(
            profile_id=created.profile_id,
            name="Reply Primary",
            model_id="model_chat_primary",
            task_class="reply_default",
            priority=UPDATED_PRIORITY,
            enabled=True,
            fallback_profile_id="fallback_profile",
        )
        assert updated is not None
        assert updated.name == "Reply Primary"
        assert updated.priority == UPDATED_PRIORITY
        assert updated.fallback_profile_id == "fallback_profile"

        with database_runtime.connect_sync() as connection:
            connection.execute(
                """
                INSERT INTO ai_model_binding (
                    binding_id,
                    scope_type,
                    scope_id,
                    profile_id,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    "binding-1",
                    "conversation",
                    "conversation-1",
                    created.profile_id,
                    "2026-04-25T00:00:00",
                ),
            )

        bindings = await admin.list_model_bindings()
        assert len(bindings) == 1
        assert bindings[0].binding_id == "binding-1"

        profile_service = admin_models.ai_model_profile_service
        resolved = await profile_service.resolve_profile(
            AIModelRouteQuery(task_class="reply_default"),
        )
        assert resolved is not None
        assert resolved.profile_id == created.profile_id

        bound = await profile_service.resolve_profile_for_target(
            target=AIModelBindingTarget(
                conversation_id="conversation-1",
                group_id=None,
                user_id=None,
            ),
        )
        assert bound is not None
        assert bound.profile_id == created.profile_id

    asyncio.run(run())


def _seed_chat_models_for_profiles() -> None:
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
                "source_profile_tests",
                "Profile Source",
                "chat_completion",
                "openai",
                "openai_compatible",
                1,
                "{}",
                "{}",
                "2026-04-25T00:00:00",
            ),
        )
        for model_id, identifier in (
            ("model_chat_primary", "gpt-primary"),
            ("model_chat_fallback", "gpt-fallback"),
        ):
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
                    model_id,
                    "source_profile_tests",
                    identifier,
                    identifier,
                    1,
                    0,
                    "{}",
                    "2026-04-25T00:00:00",
                ),
            )
        connection.execute(
            """
            INSERT INTO ai_model_profile (
                profile_id,
                name,
                model_id,
                task_class,
                priority,
                enabled,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "fallback_profile",
                "Fallback",
                "model_chat_fallback",
                "reply_default",
                99,
                1,
                "2026-04-25T00:00:00",
            ),
        )
