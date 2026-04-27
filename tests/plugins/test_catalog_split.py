from __future__ import annotations

import importlib
from pathlib import Path


def test_plugin_catalog_delegates_runtime_state_discovery() -> None:
    project_root = Path(__file__).resolve().parents[2]
    catalog_source = (project_root / "apeiria" / "plugins" / "catalog.py").read_text(
        encoding="utf-8"
    )

    module = importlib.import_module("apeiria.plugins.catalog_state")

    assert hasattr(module, "PluginCatalogStateBuilder")
    assert "import nonebot" not in catalog_source
    assert "packages_distributions" not in catalog_source
    assert "iter_builtin_plugin_modules" not in catalog_source
    assert "get_pending_uninstall_plugin_modules" not in catalog_source
