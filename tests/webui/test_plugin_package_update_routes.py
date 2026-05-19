from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest
from fastapi import HTTPException

from apeiria.access.principal import AuthSession, Principal, PrincipalRole
from apeiria.access.principal_roles import CAP_CONTROL_PANEL
from apeiria.plugins.models import (
    PluginCatalogEntry,
    PluginDescriptor,
    PluginGovernanceState,
    PluginPackageBinding,
    PluginRuntimeState,
)

if TYPE_CHECKING:
    from pytest import MonkeyPatch


HTTP_BAD_REQUEST = 400


def test_update_plugin_package_rejects_without_available_update(
    monkeypatch: MonkeyPatch,
) -> None:
    from apeiria.app.plugins.store.update_check import PluginUpdateCheckResult

    _stub_nonebot_config(monkeypatch)
    from apeiria.webui.routes import plugin_management
    from apeiria.webui.schemas.plugin_management import PluginPackageUpdateRequest

    task_calls: list[tuple[str, str]] = []

    async def fake_check_plugin(
        module_name: str,
        package_name: str,
        *,
        force_refresh: bool = False,
        installed_versions: dict[str, str] | None = None,
    ) -> PluginUpdateCheckResult:
        assert force_refresh is True
        assert installed_versions is None
        return PluginUpdateCheckResult(
            module_name=module_name,
            package_name=package_name,
            current_version="1.0.0",
            latest_version="1.0.0",
            has_update=False,
            checked=True,
        )

    async def fake_create_update_task(requirement: str, module_name: str) -> object:
        task_calls.append((requirement, module_name))
        return SimpleNamespace(task_id="task-1")

    monkeypatch.setattr(
        plugin_management.plugin_management_service,
        "get_plugin",
        _async_return(_plugin_entry()),
    )
    monkeypatch.setattr(
        plugin_management.plugin_update_check_service,
        "check_plugin",
        fake_check_plugin,
    )
    monkeypatch.setattr(
        plugin_management.plugin_store_task_service,
        "create_manual_plugin_update_task",
        fake_create_update_task,
    )

    async def scenario() -> None:
        with pytest.raises(HTTPException) as exc_info:
            await plugin_management.update_plugin_package_task(
                "example.plugin",
                PluginPackageUpdateRequest(package_name="example-plugin"),
                _owner_session(),
            )
        assert exc_info.value.status_code == HTTP_BAD_REQUEST

    import asyncio

    asyncio.run(scenario())

    assert task_calls == []


def test_update_plugin_package_creates_task_when_update_available(
    monkeypatch: MonkeyPatch,
) -> None:
    from apeiria.app.plugins.store.update_check import PluginUpdateCheckResult

    _stub_nonebot_config(monkeypatch)
    from apeiria.webui.routes import plugin_management
    from apeiria.webui.schemas.plugin_management import PluginPackageUpdateRequest

    task_calls: list[tuple[str, str]] = []

    async def fake_check_plugin(
        module_name: str,
        package_name: str,
        *,
        force_refresh: bool = False,
        installed_versions: dict[str, str] | None = None,
    ) -> PluginUpdateCheckResult:
        assert force_refresh is True
        assert installed_versions is None
        return PluginUpdateCheckResult(
            module_name=module_name,
            package_name=package_name,
            current_version="1.0.0",
            latest_version="1.1.0",
            has_update=True,
            checked=True,
        )

    async def fake_create_update_task(requirement: str, module_name: str) -> object:
        task_calls.append((requirement, module_name))
        return SimpleNamespace(
            task_id="task-1",
            title="Update example.plugin",
            status="pending",
            logs="",
            error=None,
            result={},
            created_at=None,
            started_at=None,
            finished_at=None,
            operation="update",
            resource_kind="plugin",
            requirement=requirement,
            binding_value=module_name,
            restart_required=True,
            steps=[],
            diagnostics=[],
        )

    monkeypatch.setattr(
        plugin_management.plugin_management_service,
        "get_plugin",
        _async_return(_plugin_entry()),
    )
    monkeypatch.setattr(
        plugin_management.plugin_update_check_service,
        "check_plugin",
        fake_check_plugin,
    )
    monkeypatch.setattr(
        plugin_management.plugin_store_task_service,
        "create_manual_plugin_update_task",
        fake_create_update_task,
    )

    async def scenario() -> None:
        response = await plugin_management.update_plugin_package_task(
            "example.plugin",
            PluginPackageUpdateRequest(package_name="example-plugin"),
            _owner_session(),
        )
        assert response.task_id == "task-1"

    import asyncio

    asyncio.run(scenario())

    assert task_calls == [("example-plugin", "example.plugin")]


def _plugin_entry() -> PluginCatalogEntry:
    return PluginCatalogEntry(
        descriptor=PluginDescriptor(
            module_name="example.plugin",
            name="Example",
            description=None,
            homepage=None,
            source="external",
            plugin_type="normal",
        ),
        runtime_state=PluginRuntimeState(is_loaded=True),
        governance_state=PluginGovernanceState(can_uninstall=True),
        package_binding=PluginPackageBinding(
            installed_package="example-plugin",
            installed_module_names=["example.plugin"],
        ),
    )


def _owner_session() -> AuthSession:
    return AuthSession(
        principal=Principal(
            principal_kind="webui_account",
            principal_id="owner",
            display_name="owner",
            role=PrincipalRole(
                role_id="owner",
                capabilities=(CAP_CONTROL_PANEL,),
            ),
        ),
        auth_method="password",
        session_version=1,
        token_subject="owner",
    )


def _stub_nonebot_config(monkeypatch: MonkeyPatch) -> None:
    import nonebot

    monkeypatch.setattr(
        nonebot,
        "get_plugin_config",
        lambda model: model(),
    )


def _async_return(value: object):
    async def inner(*_: object, **__: object) -> object:
        return value

    return inner
