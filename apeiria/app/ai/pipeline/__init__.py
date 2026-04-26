"""Runtime boundary exports with lazy side-effectful loading."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

from .composer import (
    AIRuntimeComposeInput,
    compose_pre_tool_reply_prompt,
    compose_reply_prompt,
    compose_roleplay_reply_prompt,
)

if TYPE_CHECKING:
    from .memory_steps import recall_memories, store_extracted_memories
    from .relationship_steps import (
        build_relationship_target,
        load_relationship_context,
        update_relationship_state,
    )
    from .service import AIRuntimeService, AITraceContext, ai_runtime_service

__all__ = [
    "AIRuntimeComposeInput",
    "AIRuntimeService",
    "AITraceContext",
    "ai_runtime_service",
    "build_relationship_target",
    "compose_pre_tool_reply_prompt",
    "compose_reply_prompt",
    "compose_roleplay_reply_prompt",
    "load_relationship_context",
    "recall_memories",
    "store_extracted_memories",
    "update_relationship_state",
]

_LAZY_EXPORTS = {
    "recall_memories": ".memory_steps",
    "store_extracted_memories": ".memory_steps",
    "build_relationship_target": ".relationship_steps",
    "load_relationship_context": ".relationship_steps",
    "update_relationship_state": ".relationship_steps",
    "AITraceContext": ".service",
    "AIRuntimeService": ".service",
    "ai_runtime_service": ".service",
}


def __getattr__(name: str) -> Any:
    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(name)
    module = import_module(module_name, __name__)
    return getattr(module, name)
