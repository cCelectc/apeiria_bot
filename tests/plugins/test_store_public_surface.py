from __future__ import annotations

import importlib
import sys

import pytest


def test_environment_store_service_uses_app_plugin_store_service() -> None:
    for module_name in (
        "apeiria.environment",
        "apeiria.app.plugins.store.service",
    ):
        sys.modules.pop(module_name, None)

    environment = importlib.import_module("apeiria.environment")
    store_service_module = importlib.import_module("apeiria.app.plugins.store.service")

    assert environment.StoreService is store_service_module.StoreService
    assert environment.store_service is store_service_module.store_service


def test_cli_nb_store_helpers_use_app_plugin_store_module() -> None:
    for module_name in (
        "apeiria.cli.nb",
        "apeiria.app.plugins.store.nb_cli",
    ):
        sys.modules.pop(module_name, None)

    cli_nb = importlib.import_module("apeiria.cli.nb")
    store_nb_cli = importlib.import_module("apeiria.app.plugins.store.nb_cli")

    assert cli_nb.MODULE_TYPE == store_nb_cli.MODULE_TYPE
    assert (
        cli_nb.search_store_packages_async is store_nb_cli.search_store_packages_async
    )
    assert cli_nb.find_exact_store_package is store_nb_cli.find_exact_store_package


@pytest.mark.parametrize(
    "module_name",
    [
        "apeiria.plugins.store",
        "apeiria.plugins.store.models",
        "apeiria.plugins.store.service",
        "apeiria.plugins.store.sources",
        "apeiria.plugins.store.tasks",
        "apeiria.plugins.store.update_check",
        "apeiria.plugins.store.nb_cli",
    ],
)
def test_legacy_plugin_store_modules_are_removed(module_name: str) -> None:
    sys.modules.pop(module_name, None)

    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(module_name)
