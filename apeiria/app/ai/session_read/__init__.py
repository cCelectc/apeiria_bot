"""AI session-read application package."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

from .models import (
    AIRecentTarget,
    AISessionPromptChannels,
    AISessionPromptPreview,
    AISessionPromptSection,
)

if TYPE_CHECKING:
    from .facade import AISessionReadService, ai_session_read_service

__all__ = [
    "AIRecentTarget",
    "AISessionPromptChannels",
    "AISessionPromptPreview",
    "AISessionPromptSection",
    "AISessionReadService",
    "ai_session_read_service",
]

_LAZY_EXPORTS = {
    "AISessionReadService": ".facade",
    "ai_session_read_service": ".facade",
}


def __getattr__(name: str) -> Any:
    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(name)
    module = import_module(module_name, __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value
