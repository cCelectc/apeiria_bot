from __future__ import annotations

import ast
import importlib.util
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from apeiria.plugins.metadata.declarations import (
    FieldDeclaration,
    _literal_eval,
    declaration_from_ast_annotation,
    register_config_from_declaration,
)

if TYPE_CHECKING:
    from apeiria.plugins.metadata.api import RegisterConfig


@dataclass
class ScannedPluginConfig:
    plugin_name: str
    section: str
    configs: list[RegisterConfig] = field(default_factory=list)
    is_apeiria_plugin: bool = False
    has_config_model: bool = False


@dataclass
class _ScannedField:
    key: str
    declaration: FieldDeclaration
    default: Any
    help: str = ""


@dataclass
class _ModuleScanState:
    base_model_aliases: set[str] = field(default_factory=lambda: {"BaseModel"})
    field_aliases: set[str] = field(default_factory=lambda: {"Field"})
    get_plugin_config_aliases: set[str] = field(
        default_factory=lambda: {"get_plugin_config"}
    )
    plugin_metadata_aliases: set[str] = field(
        default_factory=lambda: {"PluginMetadata"},
    )
    plugin_extra_aliases: set[str] = field(default_factory=lambda: {"PluginExtraData"})
    config_model_names: set[str] = field(default_factory=set)
    apeiria_metadata: bool = False
    class_fields: dict[str, list[_ScannedField]] = field(default_factory=dict)


def _read_python_sources(module_name: str) -> list[Path]:
    spec = importlib.util.find_spec(module_name)
    if (spec is None or spec.origin is None) and "." not in module_name:
        spec = importlib.util.find_spec(f"nonebot.plugins.{module_name}")
    if spec is None or spec.origin is None:
        return []

    origin = Path(spec.origin)
    if spec.submodule_search_locations:
        package_dir = origin.parent
        return sorted(package_dir.rglob("*.py"))
    return [origin]


def _python_sources_from_origin(origin: Path) -> list[Path]:
    if origin.name == "__init__.py":
        return sorted(origin.parent.rglob("*.py"))
    return [origin]


def _collect_import_aliases(tree: ast.AST, state: _ModuleScanState) -> None:
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                local_name = alias.asname or alias.name
                if alias.name == "BaseModel":
                    state.base_model_aliases.add(local_name)
                elif alias.name == "Field":
                    state.field_aliases.add(local_name)
                elif alias.name == "get_plugin_config":
                    state.get_plugin_config_aliases.add(local_name)
                elif alias.name == "PluginMetadata":
                    state.plugin_metadata_aliases.add(local_name)
                elif alias.name == "PluginExtraData":
                    state.plugin_extra_aliases.add(local_name)


def _is_named(node: ast.AST, names: set[str]) -> bool:
    return isinstance(node, ast.Name) and node.id in names


def _is_base_model(node: ast.expr, names: set[str]) -> bool:
    if _is_named(node, names):
        return True
    return isinstance(node, ast.Attribute) and node.attr in names


def _field_default(call: ast.Call) -> Any:
    if call.args:
        return _literal_eval(call.args[0])

    for keyword in call.keywords:
        if keyword.arg == "default":
            return _literal_eval(keyword.value)
        if keyword.arg != "default_factory":
            continue
        factory_value = _field_default_factory(keyword.value)
        if factory_value is not None:
            return factory_value
    return None


def _field_default_factory(node: ast.AST) -> Any:
    if isinstance(node, ast.Name):
        defaults = {
            "list": [],
            "set": set(),
            "dict": {},
        }
        return defaults.get(node.id)
    if isinstance(node, ast.Lambda):
        return _literal_eval(node.body)
    return None


def _extract_help_from_field(
    value: ast.Call,
    next_node: ast.stmt | None,
) -> str:
    for keyword in value.keywords:
        if keyword.arg == "description":
            extracted = _literal_eval(keyword.value)
            return extracted if isinstance(extracted, str) else ""
    if isinstance(next_node, ast.Expr):
        text = _literal_eval(next_node.value)
        if isinstance(text, str):
            return text
    return ""


def _scan_class_fields(
    class_node: ast.ClassDef,
    state: _ModuleScanState,
) -> list[_ScannedField]:
    fields: list[_ScannedField] = []
    body = class_node.body
    for index, node in enumerate(body):
        next_node = body[index + 1] if index + 1 < len(body) else None
        if not isinstance(node, ast.AnnAssign) or not isinstance(node.target, ast.Name):
            continue

        default = _literal_eval(node.value) if node.value is not None else None
        help_text = ""
        if isinstance(node.value, ast.Call) and _is_named(
            node.value.func,
            state.field_aliases,
        ):
            default = _field_default(node.value)
            help_text = _extract_help_from_field(node.value, next_node)
        elif isinstance(next_node, ast.Expr):
            literal = _literal_eval(next_node.value)
            if isinstance(literal, str):
                help_text = literal

        declaration = declaration_from_ast_annotation(node.annotation, default)
        fields.append(
            _ScannedField(
                key=node.target.id,
                declaration=declaration,
                default=default,
                help=help_text,
            )
        )
    return fields


def _collect_config_signals(tree: ast.AST, state: _ModuleScanState) -> None:
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if (
                _is_get_plugin_config_call(
                    node,
                    state.get_plugin_config_aliases,
                )
                and node.args
            ):
                model_name = _config_model_reference_name(node.args[0])
                if model_name is not None:
                    state.config_model_names.add(model_name)

            if _is_plugin_metadata_call(node.func, state.plugin_metadata_aliases):
                for keyword in node.keywords:
                    if keyword.arg == "config":
                        model_name = _config_model_reference_name(keyword.value)
                        if model_name is not None:
                            state.config_model_names.add(model_name)
                    if keyword.arg == "extra" and _is_apeiria_extra(
                        keyword.value,
                        state,
                    ):
                        state.apeiria_metadata = True


def _is_get_plugin_config_call(node: ast.Call, aliases: set[str]) -> bool:
    if isinstance(node.func, ast.Name):
        return node.func.id in aliases
    return isinstance(node.func, ast.Attribute) and node.func.attr in aliases


def _is_plugin_metadata_call(node: ast.AST, aliases: set[str]) -> bool:
    if isinstance(node, ast.Name):
        return node.id in aliases
    return isinstance(node, ast.Attribute) and node.attr in aliases


def _config_model_reference_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _is_apeiria_extra(node: ast.AST, state: _ModuleScanState) -> bool:
    if isinstance(node, ast.Dict):
        for key, value in zip(node.keys, node.values, strict=False):
            if key is None:
                continue
            if _literal_eval(key) == "_apeiria" and _literal_eval(value) is True:
                return True
        return False
    return isinstance(node, ast.Call) and (
        isinstance(node.func, ast.Attribute)
        and node.func.attr == "to_dict"
        and isinstance(node.func.value, ast.Call)
        and _is_named(node.func.value.func, state.plugin_extra_aliases)
    )


def _scan_source(path: Path) -> _ModuleScanState:
    state = _ModuleScanState()
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return state

    _collect_import_aliases(tree, state)
    _collect_config_signals(tree, state)

    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        if not any(
            _is_base_model(base, state.base_model_aliases) for base in node.bases
        ):
            continue
        state.class_fields[node.name] = _scan_class_fields(node, state)
    return state


def scan_plugin_config(plugin_name: str) -> ScannedPluginConfig:
    sources = _read_python_sources(plugin_name)
    return _scan_plugin_config_from_sources(plugin_name, sources)


def scan_plugin_config_from_origin(
    plugin_name: str,
    origin: Path,
) -> ScannedPluginConfig:
    return _scan_plugin_config_from_sources(
        plugin_name,
        _python_sources_from_origin(origin),
    )


def _scan_plugin_config_from_sources(
    plugin_name: str,
    sources: list[Path],
) -> ScannedPluginConfig:
    if not sources:
        return ScannedPluginConfig(
            plugin_name=plugin_name,
            section=plugin_name.rsplit(".", maxsplit=1)[-1],
        )

    combined = _ModuleScanState()
    for source in sources:
        state = _scan_source(source)
        combined.config_model_names.update(state.config_model_names)
        combined.apeiria_metadata = combined.apeiria_metadata or state.apeiria_metadata
        combined.class_fields.update(state.class_fields)

    configs: list[RegisterConfig] = []
    for model_name in sorted(combined.config_model_names):
        configs.extend(
            register_config_from_declaration(
                key=scanned_field.key,
                declaration=scanned_field.declaration,
                default=scanned_field.default,
                help_text=scanned_field.help,
            )
            for scanned_field in combined.class_fields.get(model_name, [])
        )

    unique_configs: dict[str, RegisterConfig] = {}
    for config in configs:
        unique_configs[config.key] = config

    return ScannedPluginConfig(
        plugin_name=plugin_name,
        section=plugin_name.rsplit(".", maxsplit=1)[-1],
        configs=list(unique_configs.values()),
        is_apeiria_plugin=combined.apeiria_metadata,
        has_config_model=bool(unique_configs),
    )
