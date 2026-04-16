"""Type hints → JSON Schema converter for AI tool parameters."""

from __future__ import annotations

import inspect
from typing import Any, Literal, Union, get_args, get_origin, get_type_hints

_MISSING = object()

_PYTHON_TYPE_TO_JSON: dict[type, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    dict: "object",
    list: "array",
}

_SKIP_PARAMS = frozenset({"self", "context", "return"})


def build_parameters_from_signature(
    func: Any,
) -> tuple[tuple[str, str, str, bool, tuple[str, ...] | None, Any], ...]:
    """Extract parameter specs from a function's type hints.

    Returns tuples of ``(name, json_type, description, required, enum, default)``.
    The *description* is auto-generated from the parameter name when no docstring
    parsing is available (handlers should use the ``@ai_tool`` *description*
    kwarg on the decorator for the tool-level blurb; per-parameter descriptions
    come from the ``Annotated[..., Desc("...")]`` pattern or fall back to the
    parameter name).
    """

    sig = inspect.signature(func)
    hints = get_type_hints(func, include_extras=True)

    params: list[tuple[str, str, str, bool, tuple[str, ...] | None, Any]] = []
    for name, param in sig.parameters.items():
        if name in _SKIP_PARAMS:
            continue
        if param.kind in {param.VAR_POSITIONAL, param.VAR_KEYWORD}:
            continue
        # keyword-only params after `*` are context injections — skip those
        # named "context" (already in _SKIP_PARAMS)

        annotation = hints.get(name, str)
        description, json_type, enum_values, is_nullable = _resolve_annotation(
            name, annotation
        )

        has_default = param.default is not inspect.Parameter.empty
        required = not has_default and not is_nullable
        default = param.default if has_default else _MISSING

        params.append((name, json_type, description, required, enum_values, default))

    return tuple(params)


def build_json_schema(
    params: tuple[tuple[str, str, str, bool, tuple[str, ...] | None, Any], ...],
) -> dict[str, Any]:
    """Build an OpenAI-compatible JSON Schema ``parameters`` object."""

    properties: dict[str, Any] = {}
    required: list[str] = []

    for name, json_type, description, is_required, enum_values, _default in params:
        prop: dict[str, Any] = {"type": json_type, "description": description}
        if enum_values is not None:
            prop["enum"] = list(enum_values)
        properties[name] = prop
        if is_required:
            required.append(name)

    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
    }
    if required:
        schema["required"] = required
    return schema


def _resolve_annotation(
    name: str,
    annotation: Any,
) -> tuple[str, str, tuple[str, ...] | None, bool]:
    """Resolve a type annotation into (description, json_type, enum, nullable).

    Handles ``Optional[X]``, ``X | None``, ``Literal[...]``, ``Annotated[...]``.
    """

    description = _humanize_param_name(name)
    is_nullable = False

    annotation, description, is_nullable = _unwrap_annotation(
        annotation, description, is_nullable=is_nullable
    )

    return _classify_annotation(annotation, description, is_nullable=is_nullable)


def _unwrap_annotation(
    annotation: Any,
    description: str,
    *,
    is_nullable: bool,
) -> tuple[Any, str, bool]:
    """Strip ``Annotated`` and ``Optional``/``Union[..., None]`` wrappers."""

    origin = get_origin(annotation)

    # Unwrap Annotated if present — extract description from metadata
    if origin is not None and _is_annotated(origin):
        args = get_args(annotation)
        annotation = args[0]
        for meta in args[1:]:
            if isinstance(meta, str):
                description = meta
                break
        origin = get_origin(annotation)

    # Unwrap Optional / Union with None
    if origin is Union or _is_union_type(annotation):
        args = get_args(annotation)
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1:
            is_nullable = True
            annotation = non_none[0]
        elif len(args) != len(non_none):
            is_nullable = True

    return annotation, description, is_nullable


def _classify_annotation(
    annotation: Any,
    description: str,
    *,
    is_nullable: bool,
) -> tuple[str, str, tuple[str, ...] | None, bool]:
    """Map a (possibly unwrapped) annotation to JSON Schema type info."""

    origin = get_origin(annotation)

    # Literal
    if origin is Literal:
        literal_args = get_args(annotation)
        if all(isinstance(a, str) for a in literal_args):
            return description, "string", tuple(literal_args), is_nullable
        if all(isinstance(a, int) for a in literal_args):
            enum = tuple(str(a) for a in literal_args)
            return description, "integer", enum, is_nullable
        enum = tuple(str(a) for a in literal_args)
        return description, "string", enum, is_nullable

    # dict / list
    if origin is dict or annotation is dict:
        return description, "object", None, is_nullable
    if origin is list or annotation is list:
        return description, "array", None, is_nullable

    # Primitive types
    json_type = _PYTHON_TYPE_TO_JSON.get(annotation, "string")
    return description, json_type, None, is_nullable


def _humanize_param_name(name: str) -> str:
    """Convert snake_case parameter name into a readable description."""

    return name.replace("_", " ").capitalize()


def _is_annotated(origin: Any) -> bool:
    """Check if an origin type is ``Annotated``."""

    from typing import Annotated

    return origin is Annotated


def _is_union_type(annotation: Any) -> bool:
    """Check for PEP 604 ``X | Y`` union types (Python 3.10+)."""

    import types

    return isinstance(annotation, types.UnionType)
