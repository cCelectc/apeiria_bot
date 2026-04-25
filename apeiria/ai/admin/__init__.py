"""Admin boundary for AI management surfaces."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from apeiria.ai.admin.service import AIAdminService, ai_admin_service

__all__ = ["AIAdminService", "ai_admin_service"]


def __getattr__(name: str) -> Any:
    if name in {"AIAdminService", "ai_admin_service"}:
        module = import_module("apeiria.ai.admin.service")
        return getattr(module, name)
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
