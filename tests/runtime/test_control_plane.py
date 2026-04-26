import asyncio
import importlib
from pathlib import Path
from types import SimpleNamespace

import nonebot
import pytest
from fastapi import HTTPException

import apeiria.plugins as plugins_module
from apeiria.db.runtime import database_runtime
from apeiria.runtime import ApeiriaRuntime
from apeiria.runtime.control_plane import ApeiriaControlPlane
from apeiria.webui.routes import dashboard

RUNTIME_UNAVAILABLE_STATUS = 503
RUNTIME_UNAVAILABLE_DETAIL = "Apeiria runtime control plane is unavailable."
EXPECTED_PLUGIN_COUNT = 2


def _build_runtime(
    *,
    conversation: object | None = None,
    plugins: object | None = None,
    control_plane: ApeiriaControlPlane | None = None,
) -> ApeiriaRuntime:
    return ApeiriaRuntime(
        project_root=Path("/tmp/runtime"),
        config=object(),
        environment=object(),
        database=object(),
        conversation=conversation if conversation is not None else object(),
        chat=object(),
        plugins=plugins if plugins is not None else object(),
        access=object(),
        ai=object(),
        control_plane=control_plane,
    )


def _load_plugin_catalog(monkeypatch: pytest.MonkeyPatch):
    def get_plugin_config(*_args: object) -> SimpleNamespace:
        return SimpleNamespace()

    monkeypatch.setattr(
        nonebot,
        "get_plugin_config",
        get_plugin_config,
    )
    for name, value in {
        "config_mutation_service": object(),
        "config_query_service": object(),
        "plugin_governance_service": object(),
        "AdapterConfigState": type("AdapterConfigState", (), {}),
        "ConfigTextView": type("ConfigTextView", (), {}),
        "ConfigValidationReport": type("ConfigValidationReport", (), {}),
        "ConfigView": type("ConfigView", (), {}),
        "DriverConfigState": type("DriverConfigState", (), {}),
        "PluginConfigConflictError": type(
            "PluginConfigConflictError",
            (Exception,),
            {},
        ),
        "PluginConfigState": type("PluginConfigState", (), {}),
        "PluginReadme": type("PluginReadme", (), {}),
        "PluginSettingsNotConfigurableError": type(
            "PluginSettingsNotConfigurableError",
            (Exception,),
            {},
        ),
        "OrphanPluginConfigItem": type("OrphanPluginConfigItem", (), {}),
    }.items():
        monkeypatch.setitem(plugins_module.__dict__, name, value)
    return importlib.import_module("apeiria.webui.routes.plugin_catalog")


def test_list_plugins_delegates_to_runtime_plugin_governance() -> None:
    expected_plugins = [object(), object()]

    async def list_plugins() -> list[object]:
        return expected_plugins

    runtime = _build_runtime(
        plugins=SimpleNamespace(
            list_plugins=list_plugins,
        ),
    )

    control_plane = ApeiriaControlPlane(runtime)

    plugins = asyncio.run(control_plane.list_plugins())

    assert plugins == expected_plugins


def test_get_dashboard_status_uses_current_dashboard_service_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apeiria.app.system.management import system_management_service

    expected_snapshot = object()
    runtime = _build_runtime()
    control_plane = ApeiriaControlPlane(runtime)

    async def get_status_snapshot() -> object:
        return expected_snapshot

    monkeypatch.setattr(
        system_management_service,
        "get_status_snapshot",
        get_status_snapshot,
    )

    snapshot = asyncio.run(control_plane.get_dashboard_status())

    assert snapshot is expected_snapshot


def test_dashboard_status_snapshot_reads_governance_state_from_new_database(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from apeiria.access.groups_repository import GroupStateRow, group_repository
    from apeiria.access.repository import access_repository
    from apeiria.app.system.management import system_management_service
    from apeiria.plugins.repository import plugin_catalog_repository

    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()
    monkeypatch.setattr(nonebot, "get_adapters", lambda: {"onebot": object()})
    monkeypatch.setattr(nonebot, "get_loaded_plugins", lambda: {object(), object()})

    async def seed() -> None:
        await plugin_catalog_repository.ensure_plugin_record_by_module_name(
            "plugins.alpha"
        )
        await plugin_catalog_repository.ensure_plugin_record_by_module_name(
            "plugins.beta"
        )
        await plugin_catalog_repository.set_plugin_enabled(
            "plugins.beta",
            enabled=False,
        )
        await group_repository.save_group(
            GroupStateRow(
                group_id="group-1",
                group_name="Group One",
                bot_status=False,
            )
        )
        await access_repository.upsert_access_rule(
            subject_type="group",
            subject_id="group-1",
            plugin_module="plugins.beta",
            effect="deny",
        )

    asyncio.run(seed())

    snapshot = asyncio.run(system_management_service.get_status_snapshot())

    assert snapshot.plugins_count == EXPECTED_PLUGIN_COUNT
    assert snapshot.disabled_plugins_count == 1
    assert snapshot.groups_count == 1
    assert snapshot.disabled_groups_count == 1
    assert snapshot.access_rules_count == 1
    assert snapshot.adapters == ["onebot"]


def test_dashboard_status_route_reads_through_control_plane(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot = SimpleNamespace(
        status="running",
        uptime=12.5,
        plugins_count=3,
        disabled_plugins_count=1,
        groups_count=4,
        disabled_groups_count=2,
        access_rules_count=5,
        adapters=["onebot"],
    )

    async def get_dashboard_status() -> object:
        return snapshot

    runtime = _build_runtime()
    control_plane = ApeiriaControlPlane(runtime)
    monkeypatch.setattr(control_plane, "get_dashboard_status", get_dashboard_status)
    runtime.control_plane = control_plane
    monkeypatch.setattr(dashboard, "get_current_runtime", lambda: runtime)

    response = asyncio.run(dashboard.get_status(None))

    assert response.status == snapshot.status
    assert response.uptime == snapshot.uptime
    assert response.plugins_count == snapshot.plugins_count
    assert response.disabled_plugins_count == snapshot.disabled_plugins_count
    assert response.groups_count == snapshot.groups_count
    assert response.disabled_groups_count == snapshot.disabled_groups_count
    assert response.access_rules_count == snapshot.access_rules_count
    assert response.adapters == snapshot.adapters


def test_plugin_list_route_reads_through_plugin_management_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plugin_catalog = _load_plugin_catalog(monkeypatch)
    plugin = SimpleNamespace(
        governance_state=SimpleNamespace(can_uninstall=True),
        package_binding=SimpleNamespace(installed_package=object()),
    )

    async def list_plugins() -> list[object]:
        return [plugin]

    monkeypatch.setattr(
        plugin_catalog.plugin_management_service,
        "list_plugins",
        list_plugins,
    )
    monkeypatch.setattr(
        plugin_catalog.plugin_management_service,
        "can_package_update",
        lambda candidate: candidate is plugin,
    )
    monkeypatch.setattr(
        plugin_catalog,
        "to_plugin_item_response",
        lambda item, can_package_update: {
            "plugin": item,
            "can_package_update": can_package_update,
        },
    )

    response = asyncio.run(plugin_catalog.list_plugins(None))

    assert response == [{"plugin": plugin, "can_package_update": True}]


@pytest.mark.parametrize(
    ("route_name", "module_name", "runtime"),
    [
        (
            "get_status",
            "dashboard",
            None,
        ),
        (
            "get_status",
            "dashboard",
            _build_runtime(),
        ),
    ],
)
def test_migrated_routes_raise_controlled_http_exception_when_runtime_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    route_name: str,
    module_name: str,
    runtime: ApeiriaRuntime | None,
) -> None:
    module = (
        dashboard if module_name == "dashboard" else _load_plugin_catalog(monkeypatch)
    )
    route_func = getattr(module, route_name)
    monkeypatch.setattr(module, "get_current_runtime", lambda: runtime)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(route_func(None))

    assert exc_info.value.status_code == RUNTIME_UNAVAILABLE_STATUS
    assert exc_info.value.detail == RUNTIME_UNAVAILABLE_DETAIL
