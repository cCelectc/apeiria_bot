from __future__ import annotations

import builtins
import importlib
import sys
from pathlib import Path

import pytest


def test_import_ai_control_admin_service_is_safe_without_nonebot_plugin_orm() -> None:
    original_import = builtins.__import__

    def guarded_import(
        name: str,
        globalns: dict[str, object] | None = None,
        localns: dict[str, object] | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> object:
        if name == "nonebot_plugin_orm":
            raise AssertionError(name)
        return original_import(name, globalns, localns, fromlist, level)

    sys.modules.pop("apeiria.app.ai.admin.control_service", None)
    builtins.__import__ = guarded_import
    try:
        module = importlib.import_module("apeiria.app.ai.admin.control_service")
    finally:
        builtins.__import__ = original_import

    assert module.__name__ == "apeiria.app.ai.admin.control_service"


@pytest.mark.parametrize(
    "module_name",
    [
        "apeiria.ai.admin",
        "apeiria.ai.admin.control_service",
        "apeiria.ai.admin.runtime_service",
        "apeiria.ai.admin.service",
        "apeiria.ai.webui",
        "apeiria.ai.webui.routes",
        "apeiria.ai.webui.routes.sessions",
    ],
)
def test_legacy_ai_admin_modules_are_gone(module_name: str) -> None:
    sys.modules.pop(module_name, None)

    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(module_name)


def test_app_ai_admin_package_no_longer_re_exports_legacy_service() -> None:
    module = importlib.import_module("apeiria.app.ai.admin")

    assert not hasattr(module, "AIAdminService")
    assert not hasattr(module, "ai_admin_service")


def test_control_plane_route_files_import_control_service() -> None:
    project_root = Path(__file__).resolve().parents[2]
    expected = {
        "apeiria/webui/routes/ai/sources.py": "ai_control_admin_service",
        "apeiria/webui/routes/ai/models.py": "ai_control_admin_service",
        "apeiria/webui/routes/ai/personas.py": "ai_control_admin_service",
        "apeiria/webui/routes/ai/tools.py": "ai_control_admin_service",
        "apeiria/webui/routes/ai/__init__.py": "ai_control_admin_service",
        "apeiria/webui/routes/ai/future_tasks.py": "ai_runtime_admin_service",
        "apeiria/webui/routes/ai/memories.py": "ai_runtime_admin_service",
        "apeiria/webui/routes/ai/person_profiles.py": "ai_runtime_admin_service",
        "apeiria/webui/routes/ai/relationships.py": "ai_runtime_admin_service",
        "apeiria/webui/routes/ai/traces.py": "ai_runtime_admin_service",
        "apeiria/webui/routes/ai/sessions.py": "ai_session_read_service",
    }

    for relative_path, symbol in expected.items():
        content = (project_root / relative_path).read_text(encoding="utf-8")
        assert symbol in content


def test_import_webui_ai_routes_package_exposes_router() -> None:
    for module_name in (
        "apeiria.webui.routes.ai",
        "apeiria.webui.routes.ai.future_tasks",
    ):
        sys.modules.pop(module_name, None)

    module = importlib.import_module("apeiria.webui.routes.ai")

    assert module.__name__ == "apeiria.webui.routes.ai"
    assert module.__all__ == ["router"]
