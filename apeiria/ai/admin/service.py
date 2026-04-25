"""Compatibility admin entrypoint for AI management surfaces."""

from __future__ import annotations

from importlib import import_module
from typing import Any

from apeiria.ai.admin.control_service import (
    AIAdminModelNotFoundError,
    AISourceDeleteBlockedError,
    AISourceModelDeleteBlockedError,
    AISourceModelFetchConfigError,
    AISourceModelFetchUpstreamError,
    AISourceModelTestConfigError,
    AISourceModelTestUpstreamError,
)


def _control_service():
    module = import_module("apeiria.ai.admin.control_service")
    return module.ai_control_admin_service


def _runtime_service():
    module = import_module("apeiria.ai.admin.runtime_service")
    return module.ai_runtime_admin_service


class AIAdminService:
    """Backward-compatible proxy over control-plane and runtime admin services."""

    def __getattr__(self, name: str) -> Any:
        control_service = _control_service()
        if hasattr(control_service, name):
            return getattr(control_service, name)
        runtime_service = _runtime_service()
        if hasattr(runtime_service, name):
            return getattr(runtime_service, name)
        msg = f"{type(self).__name__!r} has no attribute {name!r}"
        raise AttributeError(msg)


ai_admin_service = AIAdminService()

__all__ = [
    "AIAdminModelNotFoundError",
    "AIAdminService",
    "AISourceDeleteBlockedError",
    "AISourceModelDeleteBlockedError",
    "AISourceModelFetchConfigError",
    "AISourceModelFetchUpstreamError",
    "AISourceModelTestConfigError",
    "AISourceModelTestUpstreamError",
    "ai_admin_service",
]
