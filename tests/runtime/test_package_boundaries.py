from __future__ import annotations

import ast
from importlib import import_module
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STABLE_PACKAGES = ("apeiria/access", "apeiria/conversation")
FORBIDDEN_STABLE_IMPORTS = (
    "apeiria.bot",
    "fastapi",
    "nonebot",
)


def test_access_and_conversation_do_not_import_surface_frameworks() -> None:
    violations: list[str] = []
    for package in STABLE_PACKAGES:
        for path in _python_files(PROJECT_ROOT / package):
            violations.extend(
                f"{path.relative_to(PROJECT_ROOT)} imports {imported_name}"
                for imported_name in _imported_names(path)
                if imported_name.startswith(FORBIDDEN_STABLE_IMPORTS)
            )

    assert violations == []


def test_access_package_root_exports_only_domain_types() -> None:
    access = import_module("apeiria.access")

    assert "audit_service" not in access.__all__
    assert "PermissionDecision" in access.__all__
    assert "PluginPolicy" in access.__all__


def test_bot_package_remains_nonebot_surface() -> None:
    bot_imports: set[str] = set()
    for path in _python_files(PROJECT_ROOT / "apeiria/bot"):
        bot_imports.update(_imported_names(path))

    assert any(name.startswith("nonebot") for name in bot_imports)
    assert "apeiria.access.level" in bot_imports
    assert "apeiria.conversation.identity" in bot_imports


def _python_files(root: Path) -> list[Path]:
    return sorted(
        path for path in root.rglob("*.py") if "__pycache__" not in path.parts
    )


def _imported_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names
