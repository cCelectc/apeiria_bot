"""Long-term memory domain exports with lazy service loading."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

from .models import (
    AIMemoryAnchorType,
    AIMemoryBeliefAction,
    AIMemoryDefinition,
    AIMemoryExtractionCandidate,
    AIMemoryExtractionResult,
    AIMemoryGovernanceDecision,
    AIMemoryKind,
    AIMemoryLayer,
    AIMemoryLifecycleState,
    AIMemoryQuery,
    AIMemoryRetrievalDiagnostics,
    AIMemoryRetrievalSelection,
    AIMemoryScopeHint,
    AIMemoryTargetScope,
    AIMemoryUseMode,
    AIMessageSentiment,
    AIObservationLevel,
)

if TYPE_CHECKING:
    from .contracts import (
        AIMemoryCreateInput,
        AIMemoryStateUpdateInput,
        AIMemoryUpdateInput,
    )
    from .service import (
        AIMemoryService,
        ai_memory_service,
    )

__all__ = [
    "AIMemoryAnchorType",
    "AIMemoryBeliefAction",
    "AIMemoryCreateInput",
    "AIMemoryDefinition",
    "AIMemoryExtractionCandidate",
    "AIMemoryExtractionResult",
    "AIMemoryGovernanceDecision",
    "AIMemoryKind",
    "AIMemoryLayer",
    "AIMemoryLifecycleState",
    "AIMemoryQuery",
    "AIMemoryRetrievalDiagnostics",
    "AIMemoryRetrievalSelection",
    "AIMemoryScopeHint",
    "AIMemoryService",
    "AIMemoryStateUpdateInput",
    "AIMemoryTargetScope",
    "AIMemoryUpdateInput",
    "AIMemoryUseMode",
    "AIMessageSentiment",
    "AIObservationLevel",
    "ai_memory_service",
]

_LAZY_EXPORTS = {
    "AIMemoryCreateInput": ".contracts",
    "AIMemoryService": ".service",
    "AIMemoryStateUpdateInput": ".contracts",
    "AIMemoryUpdateInput": ".contracts",
    "ai_memory_service": ".service",
}


def __getattr__(name: str) -> Any:
    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(name)
    module = import_module(module_name, __name__)
    return getattr(module, name)
