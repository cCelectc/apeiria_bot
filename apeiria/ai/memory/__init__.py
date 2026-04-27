"""Long-term memory domain exports with lazy service loading."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

from .models import (
    AIMemoryAnchorType,
    AIMemoryDefinition,
    AIMemoryExtractionCandidate,
    AIMemoryExtractionResult,
    AIMemoryKind,
    AIMemoryLayer,
    AIMemoryQuery,
    AIMessageSentiment,
)
from .ranking import rank_memory_items

if TYPE_CHECKING:
    from .contracts import AIMemoryCreateInput, AIMemoryUpdateInput
    from .service import (
        AIMemoryService,
        ai_memory_service,
    )

__all__ = [
    "AIMemoryAnchorType",
    "AIMemoryCreateInput",
    "AIMemoryDefinition",
    "AIMemoryExtractionCandidate",
    "AIMemoryExtractionResult",
    "AIMemoryKind",
    "AIMemoryLayer",
    "AIMemoryQuery",
    "AIMemoryService",
    "AIMemoryUpdateInput",
    "AIMessageSentiment",
    "ai_memory_service",
    "rank_memory_items",
]

_LAZY_EXPORTS = {
    "AIMemoryCreateInput": ".contracts",
    "AIMemoryService": ".service",
    "AIMemoryUpdateInput": ".contracts",
    "ai_memory_service": ".service",
}


def __getattr__(name: str) -> Any:
    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(name)
    module = import_module(module_name, __name__)
    return getattr(module, name)
