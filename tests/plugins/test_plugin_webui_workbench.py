from __future__ import annotations

from dataclasses import dataclass
from types import ModuleType
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apeiria.plugins.models import (
    PluginCatalogEntry,
    PluginDescriptor,
    PluginGovernanceState,
    PluginPackageBinding,
    PluginRuntimeState,
)
from apeiria.webui.auth import require_control_panel, require_owner

HTTP_OK = 200
HTTP_NOT_FOUND = 404
PLUGIN_SUMMARY_TOTAL = 5

if TYPE_CHECKING:
    import pytest


@dataclass(frozen=True)
class _ToggleResult:
    module_name: str
    enabled: bool
    affected_modules: list[str]


class _ControlPlane:
    def __init__(self, plugins: list[PluginCatalogEntry]) -> None:
        self.plugins = plugins
        self.update_check_called = False

    async def list_plugin_catalog_entries(self) -> list[PluginCatalogEntry]:
        return self.plugins

    def can_plugin_package_update(self, plugin: PluginCatalogEntry) -> bool:
        return bool(plugin.package_binding.installed_package)

    async def get_plugin_workbench(self) -> Any:
        from apeiria.app.plugins.management import plugin_management_service

        return await plugin_management_service.build_plugin_workbench(
            plugins=self.plugins,
            can_package_update=self.can_plugin_package_update,
        )


def _plugin(  # noqa: PLR0913
    module_name: str,
    *,
    loaded: bool = True,
    enabled: bool = True,
    protected: bool = False,
    pending_uninstall: bool = False,
    explicit: bool = True,
    package: str | None = None,
    source: str = "external",
) -> PluginCatalogEntry:
    # Mirror the full catalog row shape, so tests can specify only relevant state.
    return PluginCatalogEntry(
        descriptor=PluginDescriptor(
            module_name=module_name,
            name=module_name.rsplit(".", 1)[-1],
            description=None,
            homepage=None,
            source=source,
            plugin_type="normal",
        ),
        runtime_state=PluginRuntimeState(
            is_loaded=loaded,
            is_pending_uninstall=pending_uninstall,
        ),
        governance_state=PluginGovernanceState(
            is_global_enabled=enabled,
            is_protected=protected,
            protected_reason="required" if protected else None,
            is_explicit=explicit,
            can_edit_config=True,
            can_view_readme=True,
            can_enable_disable=not protected,
            can_uninstall=explicit and not protected,
        ),
        package_binding=PluginPackageBinding(
            installed_package=package,
            installed_module_names=[module_name] if package else [],
        ),
    )


def _client() -> TestClient:
    import nonebot

    try:
        nonebot.get_driver()
    except ValueError:
        nonebot.init()

    from apeiria.webui.routes.router import router

    app = FastAPI()

    def _allow() -> object:
        return object()

    app.dependency_overrides[require_control_panel] = _allow
    app.dependency_overrides[require_owner] = _allow
    app.include_router(router, prefix="/api")
    return TestClient(app)


def test_plugin_workbench_maps_runtime_policy_and_startup_state(
    monkeypatch: "pytest.MonkeyPatch",
) -> None:
    import nonebot

    try:
        nonebot.get_driver()
    except ValueError:
        nonebot.init()

    plugins = [
        _plugin("plugins.active", loaded=True, enabled=True),
        _plugin("plugins.blocked", loaded=True, enabled=False),
        _plugin("plugins.not_loaded", loaded=False, enabled=True),
        _plugin("plugins.protected", protected=True),
        _plugin("plugins.pending", pending_uninstall=True),
    ]
    control_plane = _ControlPlane(plugins)

    monkeypatch.setattr(
        "apeiria.webui.routes.plugin_catalog._require_runtime_control_plane",
        lambda: control_plane,
    )

    async def _empty_orphan_configs() -> list[object]:
        return []

    monkeypatch.setattr(
        "apeiria.app.plugins.management.plugin_management_service.list_orphan_plugin_configs",
        _empty_orphan_configs,
    )

    response = _client().get("/api/plugins/workbench")

    assert response.status_code == HTTP_OK
    payload = response.json()
    rows = {item["module_name"]: item for item in payload["plugins"]}
    assert rows["plugins.active"]["effective_state"] == "active"
    assert rows["plugins.blocked"]["runtime"]["loaded"] is True
    assert rows["plugins.blocked"]["runtime"]["execution_blocked"] is True
    assert rows["plugins.blocked"]["startup"]["will_load"] is False
    assert rows["plugins.blocked"]["effective_state"] == "execution_blocked"
    assert rows["plugins.not_loaded"]["effective_state"] == "not_loaded"
    assert rows["plugins.protected"]["policy"]["can_change"] is False
    assert rows["plugins.pending"]["effective_state"] == "pending_uninstall"
    assert payload["summary"]["total"] == PLUGIN_SUMMARY_TOTAL
    assert payload["summary"]["blocked"] == 1


def test_workbench_allows_switching_unprotected_builtin_plugins() -> None:
    plugin = _plugin("apeiria.builtin_plugins.ai", source="builtin")

    from apeiria.webui.schemas.plugin_workbench import to_plugin_workbench_response

    response = to_plugin_workbench_response(
        type(
            "State",
            (),
            {
                "plugin_rows": [(plugin, False)],
                "orphan_config_count": 0,
                "active_package_task": None,
            },
        )()
    )

    row = response.plugins[0]
    assert row.source == "builtin"
    assert row.policy.can_change is True
    assert row.capabilities.can_enable_disable is True


def test_catalog_keeps_dependent_builtin_application_plugin_switchable() -> None:
    from nonebot.plugin import Plugin

    from apeiria.plugins.catalog import PluginGovernanceService
    from apeiria.plugins.catalog_state import PluginItemFacts, PluginListContext
    from apeiria.utils.plugin_introspection import OFFICIAL_PLUGIN_ROOT

    module = ModuleType("apeiria.builtin_plugins.ai")
    module.__file__ = str(OFFICIAL_PLUGIN_ROOT / "ai" / "__init__.py")
    plugin = Plugin(
        name="ai",
        module=module,
        module_name="apeiria.builtin_plugins.ai",
        manager=object(),
    )

    entry = PluginGovernanceService()._build_loaded_plugin_entry(
        plugin=plugin,
        context=PluginListContext(
            enabled_map={},
            info_map={},
            package_bindings={},
            pending_uninstall_modules=set(),
            top_level_packages={},
        ),
        facts=PluginItemFacts(
            is_explicit=False,
            is_dependency=False,
            required_plugins=[],
            dependent_plugins=["Help"],
        ),
        access_mode="default_allow",
    )

    assert entry is not None
    assert entry.descriptor.source == "builtin"
    assert entry.governance_state.dependent_plugins == ["Help"]
    assert entry.governance_state.is_protected is False
    assert entry.governance_state.protected_reason is None
    assert entry.governance_state.can_enable_disable is True


def test_catalog_keeps_control_panel_builtin_protected() -> None:
    from nonebot.plugin import Plugin

    from apeiria.plugins.catalog import PluginGovernanceService
    from apeiria.plugins.catalog_state import PluginItemFacts, PluginListContext
    from apeiria.utils.plugin_introspection import OFFICIAL_PLUGIN_ROOT

    module = ModuleType("apeiria.builtin_plugins.web_ui")
    module.__file__ = str(OFFICIAL_PLUGIN_ROOT / "web_ui" / "__init__.py")
    plugin = Plugin(
        name="web_ui",
        module=module,
        module_name="apeiria.builtin_plugins.web_ui",
        manager=object(),
    )

    entry = PluginGovernanceService()._build_loaded_plugin_entry(
        plugin=plugin,
        context=PluginListContext(
            enabled_map={},
            info_map={},
            package_bindings={},
            pending_uninstall_modules=set(),
            top_level_packages={},
        ),
        facts=PluginItemFacts(
            is_explicit=False,
            is_dependency=False,
            required_plugins=[],
            dependent_plugins=[],
        ),
        access_mode="default_allow",
    )

    assert entry is not None
    assert entry.descriptor.source == "builtin"
    assert entry.governance_state.is_protected is True
    assert entry.governance_state.protected_reason
    assert entry.governance_state.can_enable_disable is False


def test_policy_route_returns_runtime_and_startup_effects(
    monkeypatch: "pytest.MonkeyPatch",
) -> None:
    import nonebot

    try:
        nonebot.get_driver()
    except ValueError:
        nonebot.init()

    async def fake_apply(module_name: str, *, enabled: bool, cascade: bool):
        assert module_name == "plugins.blocked"
        assert enabled is False
        assert cascade is True
        return _ToggleResult(
            module_name=module_name,
            enabled=enabled,
            affected_modules=[module_name],
        )

    monkeypatch.setattr(
        "apeiria.webui.routes.plugin_management.plugin_management_service.apply_plugin_toggle",
        fake_apply,
    )

    response = _client().patch(
        "/api/plugins/plugins.blocked/policy",
        json={"enabled": False, "cascade": True},
    )

    assert response.status_code == HTTP_OK
    assert response.json() == {
        "module_name": "plugins.blocked",
        "policy": {"enabled": False},
        "affected_modules": ["plugins.blocked"],
        "runtime_effect": "execution_blocked",
        "startup_effect": "skip_loading_on_next_start",
        "restart_required": True,
    }


def test_install_resolve_requirement_uses_module_candidates(
    monkeypatch: "pytest.MonkeyPatch",
) -> None:
    import nonebot

    try:
        nonebot.get_driver()
    except ValueError:
        nonebot.init()

    monkeypatch.setattr(
        "apeiria.webui.routes.plugin_management.resolve_plugin_install_source",
        lambda payload: {
            "source": payload.source,
            "status": "resolved",
            "candidates": [
                {
                    "module_name": "nonebot_plugin_foo",
                    "kind": "module",
                    "confidence": "high",
                    "reason": "requirement",
                    "already_registered": False,
                    "already_loaded": False,
                }
            ],
            "default_action": {
                "kind": "install_package",
                "requirement": "nonebot-plugin-foo",
                "module_name": "nonebot_plugin_foo",
            },
            "warnings": [],
        },
    )

    response = _client().post(
        "/api/plugins/install/resolve",
        json={"source": {"kind": "requirement", "value": "nonebot-plugin-foo"}},
    )

    assert response.status_code == HTTP_OK
    payload = response.json()
    assert payload["status"] == "resolved"
    assert payload["candidates"][0]["module_name"] == "nonebot_plugin_foo"
    assert payload["default_action"]["kind"] == "install_package"


def test_new_config_namespaces_are_routed(
    monkeypatch: "pytest.MonkeyPatch",
) -> None:
    import nonebot

    try:
        nonebot.get_driver()
    except ValueError:
        nonebot.init()

    def _core_view() -> object:
        return type(
            "View",
            (),
            {
                "module_name": "__core__",
                "section": "core",
                "config_source": "none",
                "has_config_model": False,
                "fields": [],
            },
        )()

    def _adapter_config() -> object:
        return type("AdapterState", (), {"modules": []})()

    def _driver_config() -> object:
        return type("DriverState", (), {"builtin": []})()

    monkeypatch.setattr(
        "apeiria.webui.routes.core_config.plugin_management_service.get_core_view",
        _core_view,
    )
    monkeypatch.setattr(
        "apeiria.webui.routes.adapter_config.plugin_management_service.get_adapter_config",
        _adapter_config,
    )
    monkeypatch.setattr(
        "apeiria.webui.routes.driver_config.plugin_management_service.get_driver_config",
        _driver_config,
    )

    client = _client()

    assert client.get("/api/core/settings").status_code == HTTP_OK
    assert client.get("/api/adapters/config").status_code == HTTP_OK
    assert client.get("/api/drivers/config").status_code == HTTP_OK


def test_legacy_plugin_config_namespaces_are_not_routed(
    monkeypatch: "pytest.MonkeyPatch",
) -> None:
    import nonebot

    try:
        nonebot.get_driver()
    except ValueError:
        nonebot.init()

    monkeypatch.setattr(
        "apeiria.webui.routes.plugin_catalog._require_runtime_control_plane",
        lambda: _ControlPlane([]),
    )

    async def _empty_orphan_configs() -> list[object]:
        return []

    monkeypatch.setattr(
        "apeiria.app.plugins.management.plugin_management_service.list_orphan_plugin_configs",
        _empty_orphan_configs,
    )

    client = _client()

    assert client.get("/api/plugins/core/settings").status_code == HTTP_NOT_FOUND
    assert client.get("/api/plugins/adapters/config").status_code == HTTP_NOT_FOUND
    assert client.get("/api/plugins/drivers/config").status_code == HTTP_NOT_FOUND
    assert client.get("/api/plugins/config").status_code == HTTP_NOT_FOUND
    assert client.get("/api/plugins/local-sources").status_code == HTTP_OK
