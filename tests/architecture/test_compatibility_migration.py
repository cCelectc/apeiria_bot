from __future__ import annotations

import ast
import importlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

_ALLOWED_RETIRED_TOKEN_FILES = {
    Path("apeiria/environment/compatibility.py"),
    Path("apeiria/runtime/compatibility.py"),
}

_RETIRED_RUNTIME_TOKENS = (
    "web_ui_token_expire_days",
    "legacy_flatten",
    "legacy_global",
    "html_to_pic",
    "template_to_pic",
    "url_to_pic",
    "markdown_to_pic",
)


def test_compatibility_inventory_names_removed_surfaces() -> None:
    inventory = importlib.import_module("apeiria.runtime.compatibility")
    keys = {surface.key for surface in inventory.RETIRED_COMPATIBILITY_SURFACES}

    assert {
        "root_bot_script",
        "bootstrap_facade",
        "user_bot_nonebot_argument",
        "web_ui_token_expire_days",
        "web_ui_auth_legacy_schema",
        "plugin_config_flattening",
        "render_pic_aliases",
    } <= keys


def test_compatibility_inventory_excludes_product_fallback_terms() -> None:
    inventory = importlib.import_module("apeiria.runtime.compatibility")

    assert {
        "openai_compatible",
        "anthropic_compatible",
        "model_fallback_chain",
        "policy_fallback",
        "ui_default_fallback",
    } <= set(inventory.NON_MIGRATION_COMPATIBILITY_TERMS)


def test_startup_compatibility_files_are_removed() -> None:
    assert not (REPO_ROOT / "apeiria" / "bootstrap.py").exists()


def test_root_bot_script_is_retained_only_for_nb_run_compatibility() -> None:
    source = (REPO_ROOT / "bot.py").read_text(encoding="utf-8")

    assert "NoneBot `nb run`" in source
    assert "apeiria.bot.entry" in source


def test_production_imports_do_not_reference_bootstrap_facade() -> None:
    offenders: list[str] = []
    for path in _iter_python_files(REPO_ROOT / "apeiria"):
        module_name = _module_name_for_path(path)
        offenders.extend(
            f"{path.relative_to(REPO_ROOT)} -> {imported}"
            for imported in _iter_imported_modules(module_name, path)
            if imported == "apeiria.bootstrap"
            or imported.startswith("apeiria.bootstrap.")
        )

    assert not offenders


def test_retired_runtime_tokens_only_live_in_diagnostics_or_inventory() -> None:
    offenders: list[str] = []
    for path in _iter_runtime_text_files():
        relative = path.relative_to(REPO_ROOT)
        if relative in _ALLOWED_RETIRED_TOKEN_FILES:
            continue
        text = path.read_text(encoding="utf-8")
        offenders.extend(
            f"{relative}: {token}" for token in _RETIRED_RUNTIME_TOKENS if token in text
        )

    assert not offenders


def _iter_runtime_text_files() -> list[Path]:
    roots = [REPO_ROOT / "apeiria", REPO_ROOT / "web" / "src"]
    files: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        files.extend(
            path
            for path in root.rglob("*")
            if path.suffix in {".py", ".ts", ".vue", ".yaml"}
        )
    for path in (
        REPO_ROOT / "README.md",
        REPO_ROOT / "user_bot.example.py",
    ):
        files.extend([path] if path.exists() else [])
    return sorted(files)


def _iter_python_files(root: Path) -> list[Path]:
    return sorted(
        path for path in root.rglob("*.py") if "__pycache__" not in path.parts
    )


def _module_name_for_path(path: Path) -> str:
    relative = path.relative_to(REPO_ROOT).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _iter_imported_modules(module_name: str, path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    current_package = (
        module_name if path.name == "__init__.py" else module_name.rsplit(".", 1)[0]
    )
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported = _resolve_import_from(node, current_package)
            if imported is not None:
                imports.append(imported)
    return imports


def _resolve_import_from(node: ast.ImportFrom, current_package: str) -> str | None:
    if node.level == 0:
        return node.module
    try:
        from importlib.util import resolve_name

        relative = "." * node.level
        if node.module is not None:
            relative += node.module
        return resolve_name(relative, current_package)
    except ImportError:
        return None
