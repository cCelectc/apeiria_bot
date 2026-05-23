from __future__ import annotations

import ast
from dataclasses import dataclass, field
from datetime import timedelta
from enum import Enum
from pathlib import Path
from types import UnionType
from typing import Any, Union, get_args, get_origin

from pydantic import BaseModel

from apeiria.plugins.metadata.api import RegisterConfig

MIN_MAPPING_TYPE_ARGS = 2
VARIADIC_TUPLE_TYPE_ARGS = 2
BUILTIN_ANNOTATION_TYPES: dict[str, object] = {
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "list": list,
    "set": set,
    "dict": dict,
    "Path": Path,
    "timedelta": timedelta,
}


@dataclass(frozen=True)
class FieldDeclaration:
    type: object
    choices: list[Any]
    item_type: object | None = None
    key_type: object | None = None
    allows_null: bool = False
    fields: list["NestedFieldDeclaration"] = field(default_factory=list)
    item_declaration: "FieldDeclaration | None" = None
    key_declaration: "FieldDeclaration | None" = None
    value_declaration: "FieldDeclaration | None" = None


@dataclass(frozen=True)
class NestedFieldDeclaration:
    key: str
    default: Any
    help: str
    declaration: FieldDeclaration


def register_config_from_runtime_annotation(
    *,
    key: str,
    annotation: object,
    default: Any,
    help_text: str,
) -> RegisterConfig:
    declaration = declaration_from_runtime_annotation(annotation, default)
    return _register_config_from_declaration(
        key=key,
        default=default,
        help_text=help_text,
        declaration=declaration,
    )


def declaration_from_runtime_annotation(
    annotation: object,
    default: Any,
    _seen_models: set[type[BaseModel]] | None = None,
) -> FieldDeclaration:
    seen_models = _seen_models or set()
    normalized_annotation, allows_null = _unwrap_runtime_optional(annotation)
    origin = get_origin(normalized_annotation)
    args = get_args(normalized_annotation)

    if origin in {list, set, tuple}:
        collection_type = list if origin is tuple else origin
        item_annotation = _sequence_runtime_item_annotation(args)
        item_declaration = (
            declaration_from_runtime_annotation(item_annotation, None, seen_models)
            if item_annotation is not None
            else _declaration_from_default(_default_collection_default_value(default))
        )
        return FieldDeclaration(
            type=collection_type,
            choices=[],
            item_type=item_declaration.type or str,
            allows_null=allows_null,
            item_declaration=item_declaration,
        )

    if origin is dict:
        key_declaration = _declaration_from_default("")
        value_declaration = _declaration_from_default(
            _default_mapping_value(default),
        )
        if args:
            key_declaration = declaration_from_runtime_annotation(
                args[0],
                None,
                seen_models,
            )
            value_declaration = declaration_from_runtime_annotation(
                args[1],
                None,
                seen_models,
            )
        return FieldDeclaration(
            type=dict,
            choices=[],
            item_type=value_declaration.type,
            key_type=key_declaration.type,
            allows_null=allows_null,
            key_declaration=key_declaration,
            value_declaration=value_declaration,
        )

    if origin is not None and str(origin).endswith("Literal"):
        literal_choices = [item for item in args if item is not type(None)]
        return FieldDeclaration(
            type=type(literal_choices[0]) if literal_choices else str,
            choices=list(literal_choices),
            allows_null=allows_null,
        )

    normalized_type = _normalize_runtime_scalar_annotation(
        normalized_annotation,
        default,
    )
    if isinstance(normalized_annotation, type) and issubclass(
        normalized_annotation, BaseModel
    ):
        if normalized_annotation in seen_models:
            return FieldDeclaration(
                type=normalized_annotation,
                choices=[],
                allows_null=allows_null,
            )
        next_seen = {*seen_models, normalized_annotation}
        return FieldDeclaration(
            type=normalized_annotation,
            choices=[],
            allows_null=allows_null,
            fields=_runtime_model_field_declarations(normalized_annotation, next_seen),
        )
    choices: list[Any] = []
    if isinstance(normalized_annotation, type) and issubclass(
        normalized_annotation,
        Enum,
    ):
        choices = [member.value for member in normalized_annotation]
        normalized_type = type(choices[0]) if choices else str

    return FieldDeclaration(
        type=normalized_type,
        choices=choices,
        allows_null=allows_null,
    )


def declaration_from_ast_annotation(
    annotation: ast.AST,
    default: Any,
) -> FieldDeclaration:
    if _is_ast_none(annotation):
        return FieldDeclaration(type=type(None), choices=[])

    if isinstance(annotation, ast.Name):
        return _declaration_from_ast_name(annotation, default)

    if isinstance(annotation, ast.Subscript):
        return _declaration_from_ast_subscript(annotation, default)

    if isinstance(annotation, ast.BinOp) and isinstance(annotation.op, ast.BitOr):
        return _declaration_from_ast_union(_flatten_ast_union(annotation), default)

    if isinstance(annotation, ast.Attribute) and annotation.attr == "Path":
        return FieldDeclaration(type=Path, choices=[])

    return _declaration_from_default(default)


def register_config_from_declaration(
    *,
    key: str,
    declaration: FieldDeclaration,
    default: Any,
    help_text: str,
) -> RegisterConfig:
    return _register_config_from_declaration(
        key=key,
        default=default,
        help_text=help_text,
        declaration=declaration,
    )


def _unwrap_runtime_optional(annotation: object) -> tuple[object, bool]:
    origin = get_origin(annotation)
    if origin not in {Union, UnionType}:
        return annotation, False

    args = tuple(arg for arg in get_args(annotation) if arg is not type(None))
    if len(args) != len(get_args(annotation)) and args:
        return args[0], True
    return annotation, False


def _normalize_runtime_scalar_annotation(annotation: object, default: Any) -> object:
    if isinstance(annotation, type):
        if issubclass(annotation, Enum):
            members = list(annotation)
            if members:
                return type(members[0].value)
            return str
        return annotation
    if default is not None:
        return type(default)
    return str


def _sequence_runtime_item_annotation(args: tuple[object, ...]) -> object | None:
    if not args:
        return None
    if len(args) == VARIADIC_TUPLE_TYPE_ARGS and args[1] is Ellipsis:
        return args[0]
    return args[0]


def _default_collection_item_type(default: Any) -> object | None:
    if isinstance(default, list | set | tuple) and default:
        return type(next(iter(default)))
    return None


def _default_collection_default_value(default: Any) -> Any:
    if isinstance(default, list | tuple) and default:
        return default[0]
    if isinstance(default, set) and default:
        return next(iter(default))
    return None


def _default_mapping_types(default: Any) -> tuple[object | None, object | None]:
    if isinstance(default, dict) and default:
        key, value = next(iter(default.items()))
        return type(key), type(value)
    return None, None


def _default_mapping_value(default: Any) -> Any:
    if isinstance(default, dict) and default:
        return next(iter(default.values()))
    return None


def _ast_value_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _literal_choices(annotation: ast.AST) -> list[Any]:
    if isinstance(annotation, ast.Tuple):
        return [
            value
            for node in annotation.elts
            if (value := _literal_eval(node)) is not None
        ]
    value = _literal_eval(annotation)
    return [value] if value is not None else []


def _literal_eval(node: ast.AST) -> Any:
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
        return None


def _is_ast_none(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and node.value is None


def _declaration_from_ast_name(
    annotation: ast.Name,
    default: Any,
) -> FieldDeclaration:
    if default is not None:
        return FieldDeclaration(type=type(default), choices=[])
    return FieldDeclaration(
        type=BUILTIN_ANNOTATION_TYPES.get(annotation.id, str),
        choices=[],
    )


def _declaration_from_ast_subscript(
    annotation: ast.Subscript,
    default: Any,
) -> FieldDeclaration:
    value_name = _ast_value_name(annotation.value)
    if value_name in {"list", "List", "Sequence", "tuple", "Tuple"}:
        return _sequence_declaration(list, annotation.slice)
    if value_name in {"set", "Set"}:
        return _sequence_declaration(set, annotation.slice)
    if value_name in {"dict", "Dict", "Mapping"}:
        return _mapping_declaration(annotation.slice)
    if value_name == "Literal":
        return _literal_declaration(annotation.slice)
    if value_name == "Optional":
        declaration = declaration_from_ast_annotation(annotation.slice, default)
        return _clone_declaration(declaration, allows_null=True)
    return _declaration_from_default(default)


def _flatten_ast_union(annotation: ast.AST) -> list[ast.AST]:
    if isinstance(annotation, ast.BinOp) and isinstance(annotation.op, ast.BitOr):
        return [
            *_flatten_ast_union(annotation.left),
            *_flatten_ast_union(annotation.right),
        ]
    return [annotation]


def _declaration_from_ast_union(
    annotations: list[ast.AST],
    default: Any,
) -> FieldDeclaration:
    allows_null = any(_is_ast_none(item) for item in annotations)
    non_null_items = [item for item in annotations if not _is_ast_none(item)]
    if not non_null_items:
        return FieldDeclaration(type=object, choices=[], allows_null=True)

    declarations = [
        declaration_from_ast_annotation(item, default) for item in non_null_items
    ]
    merged = _merge_union_declarations(declarations)
    return _clone_declaration(merged, allows_null=allows_null)


def _merge_union_declarations(
    declarations: list[FieldDeclaration],
) -> FieldDeclaration:
    if len(declarations) == 1:
        return declarations[0]

    choice_declaration = _merge_choice_declarations(declarations)
    if choice_declaration is not None:
        return choice_declaration

    first = declarations[0]
    if all(
        declaration.type == first.type
        and declaration.item_type == first.item_type
        and declaration.key_type == first.key_type
        and declaration.choices == first.choices
        for declaration in declarations[1:]
    ):
        return first

    return FieldDeclaration(type=object, choices=[])


def _merge_choice_declarations(
    declarations: list[FieldDeclaration],
) -> FieldDeclaration | None:
    if not declarations or not all(declaration.choices for declaration in declarations):
        return None

    choice_type = declarations[0].type
    if any(declaration.type != choice_type for declaration in declarations[1:]):
        return None

    merged_choices: list[Any] = []
    for declaration in declarations:
        for choice in declaration.choices:
            if choice not in merged_choices:
                merged_choices.append(choice)

    return FieldDeclaration(type=choice_type, choices=merged_choices)


def _sequence_declaration(
    collection_type: type[list[Any] | set[Any]],
    annotation: ast.AST,
) -> FieldDeclaration:
    declaration = declaration_from_ast_annotation(annotation, None)
    return FieldDeclaration(
        type=collection_type,
        choices=[],
        item_type=declaration.type,
        item_declaration=declaration,
    )


def _mapping_declaration(annotation: ast.AST) -> FieldDeclaration:
    if not isinstance(annotation, ast.Tuple) or (
        len(annotation.elts) < MIN_MAPPING_TYPE_ARGS
    ):
        return FieldDeclaration(type=dict, choices=[], key_type=str)

    key_decl = declaration_from_ast_annotation(annotation.elts[0], None)
    value_decl = declaration_from_ast_annotation(annotation.elts[1], None)
    return FieldDeclaration(
        type=dict,
        choices=[],
        item_type=value_decl.type,
        key_type=key_decl.type,
        key_declaration=key_decl,
        value_declaration=value_decl,
    )


def _literal_declaration(annotation: ast.AST) -> FieldDeclaration:
    choices = _literal_choices(annotation)
    return FieldDeclaration(
        type=type(choices[0]) if choices else str,
        choices=choices,
    )


def _declaration_from_default(default: Any) -> FieldDeclaration:
    if default is None:
        return FieldDeclaration(type=str, choices=[])

    return FieldDeclaration(
        type=type(default),
        choices=[],
        item_type=_default_collection_item_type(default),
        key_type=_default_mapping_key_type(default),
    )


def _default_mapping_key_type(default: Any) -> object | None:
    if isinstance(default, dict) and default:
        return type(next(iter(default.keys())))
    return None


def _clone_declaration(
    declaration: FieldDeclaration,
    *,
    allows_null: bool,
) -> FieldDeclaration:
    return FieldDeclaration(
        type=declaration.type,
        choices=declaration.choices,
        item_type=declaration.item_type,
        key_type=declaration.key_type,
        allows_null=allows_null,
        fields=list(declaration.fields),
        item_declaration=declaration.item_declaration,
        key_declaration=declaration.key_declaration,
        value_declaration=declaration.value_declaration,
    )


def _register_config_from_declaration(
    *,
    key: str,
    default: Any,
    help_text: str,
    declaration: FieldDeclaration,
) -> RegisterConfig:
    return RegisterConfig(
        key=key,
        default=default,
        help=help_text,
        type=declaration.type,
        choices=list(declaration.choices),
        item_type=declaration.item_type,
        key_type=declaration.key_type,
        allows_null=declaration.allows_null,
        fields=[
            _register_config_from_declaration(
                key=item.key,
                default=item.default,
                help_text=item.help,
                declaration=item.declaration,
            )
            for item in declaration.fields
        ],
        item_schema=(
            _register_config_from_declaration(
                key="item",
                default=None,
                help_text="",
                declaration=declaration.item_declaration,
            )
            if declaration.item_declaration is not None
            else None
        ),
        key_schema=(
            _register_config_from_declaration(
                key="key",
                default=None,
                help_text="",
                declaration=declaration.key_declaration,
            )
            if declaration.key_declaration is not None
            else None
        ),
        value_schema=(
            _register_config_from_declaration(
                key="value",
                default=None,
                help_text="",
                declaration=declaration.value_declaration,
            )
            if declaration.value_declaration is not None
            else None
        ),
        label="",
        order=99,
        secret=False,
    )


def _runtime_model_field_declarations(
    model: type[BaseModel],
    seen_models: set[type[BaseModel]],
) -> list[NestedFieldDeclaration]:
    result: list[NestedFieldDeclaration] = []
    for key, field_info in model.model_fields.items():
        default = (
            None
            if field_info.is_required()
            else field_info.get_default(call_default_factory=True)
        )
        result.append(
            NestedFieldDeclaration(
                key=key,
                default=default,
                help=field_info.description or "",
                declaration=declaration_from_runtime_annotation(
                    field_info.annotation,
                    default,
                    seen_models,
                ),
            )
        )
    return result
