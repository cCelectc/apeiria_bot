"""Runtime boundary for AI message handling."""

from .composer import AIRuntimeComposeInput, compose_reply_prompt
from .memory_steps import recall_memories, store_extracted_memories
from .relationship_steps import (
    build_relationship_target,
    load_relationship_context,
    update_relationship_state,
)
from .service import AIRuntimeService, ai_runtime_service

__all__ = [
    "AIRuntimeComposeInput",
    "AIRuntimeService",
    "ai_runtime_service",
    "build_relationship_target",
    "compose_reply_prompt",
    "load_relationship_context",
    "recall_memories",
    "store_extracted_memories",
    "update_relationship_state",
]
