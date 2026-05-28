"""AI application flows and workbench orchestration."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .application import AIApplication, ai_application

__all__ = ["AIApplication", "ai_application"]

_LAZY_EXPORTS = {
    "AIApplication": ".application",
    "ai_application": ".application",
}


def __getattr__(name: str) -> Any:
    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(name)
    module = import_module(module_name, __name__)
    return getattr(module, name)
