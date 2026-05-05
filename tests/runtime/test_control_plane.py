import asyncio
import importlib
import sys
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
EXPECTED_USER_LEVEL = 3


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


def _load_access(monkeypatch: pytest.MonkeyPatch):
    for name, value in {
        "plugin_governance_service": object(),
        "plugin_policy_service": object(),
    }.items():
        monkeypatch.setitem(plugins_module.__dict__, name, value)
    return importlib.import_module("apeiria.webui.routes.access")


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


def test_get_dashboard_events_uses_current_system_management_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apeiria.app.system.management import system_management_service

    expected_events = [object()]
    runtime = _build_runtime()
    control_plane = ApeiriaControlPlane(runtime)

    monkeypatch.setattr(
        system_management_service,
        "get_recent_events",
        lambda: expected_events,
    )

    events = control_plane.get_dashboard_events()

    assert events == expected_events


def test_get_web_ui_build_status_uses_current_system_management_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apeiria.app.system.management import system_management_service

    expected_status = object()
    runtime = _build_runtime()
    control_plane = ApeiriaControlPlane(runtime)

    monkeypatch.setattr(
        system_management_service,
        "get_web_ui_build_status",
        lambda: expected_status,
    )

    status = control_plane.get_web_ui_build_status()

    assert status is expected_status


def test_plugin_catalog_reads_delegate_to_plugin_management_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected_plugins = [object()]
    runtime = _build_runtime()
    control_plane = ApeiriaControlPlane(runtime)

    async def list_plugins() -> list[object]:
        return expected_plugins

    plugin_management_service = SimpleNamespace(
        list_plugins=list_plugins,
        can_package_update=lambda candidate: candidate is expected_plugins[0],
    )
    monkeypatch.setitem(
        sys.modules,
        "apeiria.app.plugins.management",
        SimpleNamespace(plugin_management_service=plugin_management_service),
    )

    plugins = asyncio.run(control_plane.list_plugin_catalog_entries())

    assert plugins == expected_plugins
    assert control_plane.can_plugin_package_update(expected_plugins[0]) is True


def test_access_reads_delegate_to_access_management_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected_users = [("user-1", "group-1", 3)]
    expected_rules = [object()]
    runtime = _build_runtime()
    control_plane = ApeiriaControlPlane(runtime)

    async def list_user_levels() -> list[tuple[str, str, int]]:
        return expected_users

    async def list_access_rules() -> list[object]:
        return expected_rules

    access_management_service = SimpleNamespace(
        list_user_levels=list_user_levels,
        list_access_rules=list_access_rules,
    )
    monkeypatch.setitem(
        sys.modules,
        "apeiria.app.access.management",
        SimpleNamespace(access_management_service=access_management_service),
    )

    users = asyncio.run(control_plane.list_access_user_levels())
    rules = asyncio.run(control_plane.list_access_rules())

    assert users == expected_users
    assert rules == expected_rules


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


def test_dashboard_events_route_reads_through_control_plane(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event = SimpleNamespace(
        timestamp="2026-05-05T10:00:00Z",
        level="warning",
        source="runtime",
        message="event",
    )

    runtime = _build_runtime()
    control_plane = ApeiriaControlPlane(runtime)
    monkeypatch.setattr(control_plane, "get_dashboard_events", lambda: [event])
    runtime.control_plane = control_plane
    monkeypatch.setattr(dashboard, "get_current_runtime", lambda: runtime)

    response = asyncio.run(dashboard.get_events(None))

    assert response.items[0].message == "event"


def test_dashboard_webui_build_status_route_reads_through_control_plane(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    status = SimpleNamespace(
        is_built=True,
        is_stale=False,
        can_build=True,
        build_tool="pnpm",
        detail="ready",
    )

    runtime = _build_runtime()
    control_plane = ApeiriaControlPlane(runtime)
    monkeypatch.setattr(control_plane, "get_web_ui_build_status", lambda: status)
    runtime.control_plane = control_plane
    monkeypatch.setattr(dashboard, "get_current_runtime", lambda: runtime)

    response = asyncio.run(dashboard.get_webui_build_status(None))

    assert response.build_tool == "pnpm"
    assert response.detail == "ready"


def test_plugin_list_route_reads_through_control_plane(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plugin_catalog = _load_plugin_catalog(monkeypatch)
    plugin = SimpleNamespace(
        governance_state=SimpleNamespace(can_uninstall=True),
        package_binding=SimpleNamespace(installed_package=object()),
    )

    async def list_plugin_catalog_entries() -> list[object]:
        return [plugin]

    runtime = _build_runtime()
    control_plane = ApeiriaControlPlane(runtime)
    monkeypatch.setattr(
        control_plane,
        "list_plugin_catalog_entries",
        list_plugin_catalog_entries,
    )
    monkeypatch.setattr(control_plane, "can_plugin_package_update", lambda _: True)
    runtime.control_plane = control_plane
    monkeypatch.setattr(plugin_catalog, "get_current_runtime", lambda: runtime)
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


def test_access_list_routes_read_through_control_plane(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    access = _load_access(monkeypatch)
    access_rule = SimpleNamespace(
        subject_type="user",
        subject_id="user-1",
        plugin_module="plugins.alpha",
        effect="allow",
        note="note",
    )

    async def list_access_user_levels() -> list[tuple[str, str, int]]:
        return [("user-1", "group-1", EXPECTED_USER_LEVEL)]

    async def list_access_rules() -> list[object]:
        return [access_rule]

    runtime = _build_runtime()
    control_plane = ApeiriaControlPlane(runtime)
    monkeypatch.setattr(
        control_plane,
        "list_access_user_levels",
        list_access_user_levels,
    )
    monkeypatch.setattr(control_plane, "list_access_rules", list_access_rules)
    runtime.control_plane = control_plane
    monkeypatch.setattr(access, "get_current_runtime", lambda: runtime)

    users = asyncio.run(access.list_users(None))
    rules = asyncio.run(access.list_access_rules(None))

    assert users[0].user_id == "user-1"
    assert users[0].group_id == "group-1"
    assert users[0].level == EXPECTED_USER_LEVEL
    assert rules[0].plugin_module == "plugins.alpha"


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
        (
            "list_plugins",
            "plugin_catalog",
            None,
        ),
        (
            "list_users",
            "access",
            None,
        ),
    ],
)
def test_migrated_routes_raise_controlled_http_exception_when_runtime_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    route_name: str,
    module_name: str,
    runtime: ApeiriaRuntime | None,
) -> None:
    if module_name == "dashboard":
        module = dashboard
    elif module_name == "access":
        module = _load_access(monkeypatch)
    else:
        module = _load_plugin_catalog(monkeypatch)
    route_func = getattr(module, route_name)
    monkeypatch.setattr(module, "get_current_runtime", lambda: runtime)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(route_func(None))

    assert exc_info.value.status_code == RUNTIME_UNAVAILABLE_STATUS
    assert exc_info.value.detail == RUNTIME_UNAVAILABLE_DETAIL
