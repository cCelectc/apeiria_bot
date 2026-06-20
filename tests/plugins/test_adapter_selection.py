from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar

from apeiria.plugins.adapter_selection import AdapterSelectionService
from apeiria.plugins.registry import (
    AdapterConfigState,
    AdapterConfigStatus,
    PluginRegistrationConfigService,
)
from apeiria.plugins.store.models import StoreItem, StorePage
from apeiria.webui.routes.adapter_selection import (
    disable_adapter,
    enable_adapter,
    require_auth,
)
from apeiria.webui.routes.adapter_selection import (
    router as adapter_selection_router,
)

if TYPE_CHECKING:
    from collections.abc import Coroutine

    from pytest import MonkeyPatch

T = TypeVar("T")
ENABLED_ADAPTER_TOTAL = 2


def test_selection_marks_importable_store_adapter_installed_but_not_enabled(
    monkeypatch: MonkeyPatch,
) -> None:
    service = AdapterSelectionService()
    _patch_config_state(monkeypatch, [])
    _patch_project_config(monkeypatch)
    _patch_store_page(
        monkeypatch,
        [
            _store_item(
                module_name="example.adapters.console",
                package_requirement="nonebot-adapter-console",
            )
        ],
    )
    _patch_importability(monkeypatch, {"example.adapters.console": True})
    _patch_configurability(monkeypatch, {})

    state = _run(service.get_selection())

    assert state.summary.enabled == 0
    candidate = state.candidates[0]
    assert candidate.module_name == "example.adapters.console"
    assert candidate.is_installed is True
    assert candidate.is_enabled is False
    assert candidate.state == "installed"


def test_selection_summarizes_enabled_pending_restart_and_unavailable(
    monkeypatch: MonkeyPatch,
) -> None:
    service = AdapterSelectionService()
    _patch_config_state(
        monkeypatch,
        [
            AdapterConfigStatus(
                name="example.adapters.one",
                is_loaded=False,
                is_importable=True,
            ),
            AdapterConfigStatus(
                name="example.adapters.missing",
                is_loaded=False,
                is_importable=False,
            ),
        ],
    )
    _patch_project_config(
        monkeypatch,
        {
            "example-adapter-one": ["example.adapters.one"],
        },
    )
    _patch_store_page(
        monkeypatch,
        [
            _store_item(
                module_name="example.adapters.one",
                package_requirement="example-adapter-one",
            )
        ],
    )
    _patch_configurability(monkeypatch, {"example.adapters.one": True})

    state = _run(service.get_selection())

    assert state.summary.enabled == ENABLED_ADAPTER_TOTAL
    assert state.summary.loaded == 0
    assert state.summary.unavailable == 1
    assert state.summary.restart_required == 1
    assert [item.state for item in state.enabled_adapters] == [
        "enabled_pending_restart",
        "unavailable",
    ]
    assert state.enabled_adapters[0].is_configurable is True


def test_enable_and_disable_adapter_update_project_modules(
    monkeypatch: MonkeyPatch,
) -> None:
    service = AdapterSelectionService()
    registration = PluginRegistrationConfigService()
    written: list[list[str]] = []
    current_modules = ["example.adapters.one"]

    def read_config():
        return {"modules": list(current_modules), "packages": {}}

    def write_config(config, config_path=None):  # noqa: ANN001,ARG001
        current_modules[:] = list(config["modules"])
        written.append(list(config["modules"]))

    monkeypatch.setattr(
        "apeiria.plugins.registry.adapter_config_service.read_project_adapter_config",
        read_config,
    )
    monkeypatch.setattr(
        "apeiria.plugins.registry.adapter_config_service.write_project_adapter_config",
        write_config,
    )
    monkeypatch.setattr(
        registration,
        "_build_adapter_config_items",
        lambda modules: [
            AdapterConfigStatus(
                name=module,
                is_loaded=False,
                is_importable=True,
            )
            for module in modules
        ],
    )
    monkeypatch.setattr(
        "apeiria.plugins.adapter_selection.plugin_registration_config_service",
        registration,
    )
    _patch_configurability(monkeypatch, {})

    enabled = service.enable_adapter("example.adapters.two")
    disabled = service.disable_adapter("example.adapters.one")

    assert enabled.module_name == "example.adapters.two"
    assert enabled.is_enabled is True
    assert disabled is not None
    assert disabled.is_enabled is False
    assert written == [
        ["example.adapters.one", "example.adapters.two"],
        ["example.adapters.two"],
    ]


def test_adapter_selection_write_routes_require_auth_dependency() -> None:
    assert require_auth in _route_dependencies(enable_adapter)
    assert require_auth in _route_dependencies(disable_adapter)


def _patch_config_state(
    monkeypatch: "MonkeyPatch",
    items: list[AdapterConfigStatus],
) -> None:
    monkeypatch.setattr(
        "apeiria.plugins.adapter_selection.plugin_registration_config_service.get_adapter_config",
        lambda: AdapterConfigState(modules=items),
    )


def _patch_project_config(
    monkeypatch: "MonkeyPatch",
    packages: dict[str, list[str]] | None = None,
) -> None:
    monkeypatch.setattr(
        "apeiria.plugins.adapter_selection.adapter_config_service.read_project_adapter_config",
        lambda: {
            "modules": [],
            "packages": packages or {},
        },
    )


def _patch_store_page(
    monkeypatch: "MonkeyPatch",
    items: list[StoreItem],
) -> None:
    async def list_items(_request):  # noqa: ANN001
        return StorePage(
            items=items,
            total=len(items),
            page=1,
            page_size=16,
        )

    monkeypatch.setattr(
        "apeiria.plugins.adapter_selection.package_store_workflow.list_items",
        list_items,
    )


def _patch_importability(
    monkeypatch: "MonkeyPatch",
    values: dict[str, bool],
) -> None:
    monkeypatch.setattr(
        "apeiria.plugins.adapter_selection._module_is_importable",
        lambda module_name: values.get(module_name, False),
    )


def _patch_configurability(
    monkeypatch: "MonkeyPatch",
    values: dict[str, bool],
) -> None:
    monkeypatch.setattr(
        "apeiria.plugins.adapter_selection._module_is_configurable",
        lambda module_name: values.get(module_name, False),
    )


def _store_item(
    *,
    module_name: str,
    package_requirement: str,
) -> StoreItem:
    return StoreItem(
        source_id="official-nonebot",
        item_id=module_name,
        type="adapter",
        name=module_name.rsplit(".", maxsplit=1)[-1],
        module_name=module_name,
        package_requirement=package_requirement,
        source_label="Official",
    )


def _route_dependencies(route_handler: object) -> list[object]:
    for route in adapter_selection_router.routes:
        if getattr(route, "endpoint", None) is route_handler:
            return [dependency.call for dependency in route.dependant.dependencies]
    msg = "route handler is not registered"
    raise AssertionError(msg)


def _run(coro: "Coroutine[Any, Any, T]") -> T:
    import asyncio

    return asyncio.run(coro)
