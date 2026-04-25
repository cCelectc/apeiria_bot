from __future__ import annotations

import asyncio
import builtins
import importlib
import sys
from typing import TYPE_CHECKING

from apeiria.db.runtime import database_runtime

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def _ensure_tool_policy_binding_table() -> None:
    database_runtime.ensure_ready()
    with database_runtime.connect_sync() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS ai_tool_policy (
                binding_id TEXT NOT NULL UNIQUE,
                scope_type TEXT NOT NULL,
                scope_id TEXT NOT NULL,
                allow_read_only_tools INTEGER NOT NULL DEFAULT 1,
                capability_mode TEXT NOT NULL DEFAULT 'off',
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(scope_type, scope_id)
            )
            """
        )


def test_tool_policy_admin_import_is_safe_without_nonebot_plugin_orm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_import = builtins.__import__

    def guarded_import(
        name: str,
        globalns: dict[str, object] | None = None,
        localns: dict[str, object] | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> object:
        if name == "nonebot_plugin_orm":
            raise AssertionError
        return original_import(name, globalns, localns, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    sys.modules.pop("apeiria.ai.admin.tools", None)
    sys.modules.pop("apeiria.ai.tools.policy", None)

    module = importlib.import_module("apeiria.ai.admin.tools")

    assert module.__name__ == "apeiria.ai.admin.tools"


def test_tool_policy_bindings_use_control_plane_sqlite(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    _ensure_tool_policy_binding_table()

    from apeiria.ai.admin import tools as admin_tools
    from apeiria.ai.tools.policy import (
        AIToolPolicyBindingTarget,
        AIToolSceneContext,
        ai_tool_policy_binding_service,
    )

    audit_events: list[tuple[str, str | None, str | None]] = []
    monkeypatch.setattr(
        admin_tools,
        "record_ai_admin_audit",
        lambda event_type, *, actor_username=None, detail=None: audit_events.append(
            (event_type, actor_username, detail)
        ),
    )

    class _Admin(admin_tools.ToolsAdminMixin):
        pass

    admin = _Admin()

    async def scenario() -> None:
        global_binding = await admin.create_tool_policy_binding(
            scope_type="global",
            scope_id="__global__",
            allow_read_only_tools=True,
            capability_mode="off",
            actor_username="alice",
        )
        group_binding = await admin.create_tool_policy_binding(
            scope_type="group",
            scope_id="group-1",
            allow_read_only_tools=False,
            capability_mode="off",
            actor_username="alice",
        )
        user_binding = await admin.create_tool_policy_binding(
            scope_type="user",
            scope_id="user-1",
            allow_read_only_tools=False,
            capability_mode="private_only",
            actor_username="alice",
        )

        listed = await admin.list_tool_policy_bindings()

        assert [item.binding_id for item in listed] == [
            global_binding.binding_id,
            group_binding.binding_id,
            user_binding.binding_id,
        ]

        updated_global = await admin.update_tool_policy_binding(
            binding_id=global_binding.binding_id,
            allow_read_only_tools=True,
            capability_mode="private_and_tome",
            actor_username="alice",
        )

        assert updated_global is not None
        assert updated_global.capability_mode == "private_and_tome"

        user_policy = await ai_tool_policy_binding_service.resolve_scene_policy(
            None,
            scene_context=AIToolSceneContext(scope_type="private", is_tome=False),
            target=AIToolPolicyBindingTarget(
                conversation_id="conv-1",
                group_id="group-1",
                user_id="user-1",
            ),
        )

        assert user_policy.execution_enabled is True
        assert user_policy.allowed_tool_names == {"plugin.capability"}
        assert user_policy.allow_capability_bridge is True

        deleted = await admin.delete_tool_policy_binding(
            binding_id=user_binding.binding_id,
            actor_username="alice",
        )

        assert deleted is True

        group_policy = await ai_tool_policy_binding_service.resolve_scene_policy(
            None,
            scene_context=AIToolSceneContext(scope_type="private", is_tome=False),
            target=AIToolPolicyBindingTarget(
                conversation_id="conv-1",
                group_id="group-1",
                user_id="user-1",
            ),
        )

        assert group_policy.execution_enabled is False
        assert group_policy.allowed_tool_names is None
        assert await admin.delete_tool_policy_binding(binding_id="missing") is False

    asyncio.run(scenario())

    assert [event[0] for event in audit_events] == [
        "ai_tool_policy_binding_created",
        "ai_tool_policy_binding_created",
        "ai_tool_policy_binding_created",
        "ai_tool_policy_binding_updated",
        "ai_tool_policy_binding_deleted",
    ]
