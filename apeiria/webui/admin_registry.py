from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from apeiria.webui.admin_service import GenericAdminService

_registry: dict[str, "GenericAdminService[Any, Any, Any]"] = {}


def register(
    resource_type: str,
    svc: "GenericAdminService[Any, Any, Any]",
) -> None:
    _registry[resource_type] = svc


def get(resource_type: str) -> "GenericAdminService[Any, Any, Any]":
    if resource_type not in _registry:
        raise KeyError(resource_type)
    return _registry[resource_type]


def list_types() -> list[str]:
    return sorted(_registry.keys())
