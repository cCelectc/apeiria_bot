"""AI orchestration package exports."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .prompting import (
    AIReplyPromptChannels,
    build_reply_prompt_channels,
    render_reply_prompt,
)

if TYPE_CHECKING:
    from .service import AIOrchestrationService, ai_orchestration_service

__all__ = [
    "AIOrchestrationService",
    "AIReplyPromptChannels",
    "ai_orchestration_service",
    "build_reply_prompt_channels",
    "render_reply_prompt",
]


def __getattr__(name: str):
    if name in {"AIOrchestrationService", "ai_orchestration_service"}:
        from .service import AIOrchestrationService, ai_orchestration_service

        return {
            "AIOrchestrationService": AIOrchestrationService,
            "ai_orchestration_service": ai_orchestration_service,
        }[name]
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
