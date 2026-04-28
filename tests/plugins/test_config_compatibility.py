from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_plugin_config_contracts_do_not_expose_flattening_state() -> None:
    targets = {
        "apeiria/plugins/metadata/registry.py": {
            "PluginConfigRegistration",
            "RegisterPluginConfigOptions",
        },
        "apeiria/plugins/metadata/contracts.py": {"ConfigNamespaceContract"},
        "apeiria/plugins/settings_support.py": {"PluginDeclaredConfig"},
        "apeiria/plugins/settings.py": {"ConfigView"},
    }

    for relative_path, class_names in targets.items():
        classes = _dataclass_field_names(REPO_ROOT / relative_path)
        for class_name in class_names:
            assert "legacy_flatten" not in classes[class_name]


def test_register_config_does_not_expose_legacy_key_state() -> None:
    classes = _dataclass_field_names(REPO_ROOT / "apeiria/plugins/metadata/api.py")

    assert "legacy_key" not in classes["RegisterConfig"]


def _dataclass_field_names(path: Path) -> dict[str, set[str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    result: dict[str, set[str]] = {}
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        result[node.name] = {
            statement.target.id
            for statement in node.body
            if isinstance(statement, ast.AnnAssign)
            if isinstance(statement.target, ast.Name)
        }
    return result
