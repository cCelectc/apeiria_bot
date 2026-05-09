"""Shared AI turn attempt records used across model and tool boundaries."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from apeiria.ai.model import AIModelGenerateResponse, AISelectedModel
    from apeiria.ai.model.runtime.capability_sources import (
        AIModelCapabilityObservation,
    )


ModelAttemptStatus = Literal["success", "failed"]
ToolAttemptStatus = Literal["success", "error", "timeout", "skipped"]


@dataclass(frozen=True)
class PromptSafeObservation:
    """Tool observation content after applying the model-visible budget."""

    content: str
    truncated: bool = False
    original_length: int = 0


@dataclass(frozen=True)
class ModelAttempt:
    """One model invocation attempt inside an AI turn."""

    attempt_index: int
    model_ref: str
    status: ModelAttemptStatus
    response_source: str
    reason: str | None = None
    diagnostic: str | None = None
    reasoning_diagnostics: dict[str, Any] = field(default_factory=dict)
    capability_observation: "AIModelCapabilityObservation | None" = None


@dataclass(frozen=True)
class ToolAttempt:
    """One requested tool call and its model-visible observation."""

    tool_call_id: str
    tool_name: str
    status: ToolAttemptStatus
    arguments_summary: str
    observation: PromptSafeObservation
    repetition_count: int = 1
    repeated: bool = False
    diagnostic: str | None = None
    native_observation: Any = None


def model_ref(selected: "AISelectedModel") -> str:
    """Build a stable source:model display reference for attempt records."""

    model_name = str(selected.resolved_model_name or "").strip() or "?"
    return f"{selected.source.source_id}:{model_name}"


def sanitize_model_diagnostic(message: str) -> str:
    """Remove obvious credential material from model diagnostics."""

    sanitized = _SECRET_ASSIGNMENT_RE.sub(r"\1\2<redacted>", message)
    sanitized = _BEARER_RE.sub("Bearer <redacted>", sanitized)
    return sanitized or "model request failed"


def is_empty_model_response(response: "AIModelGenerateResponse | None") -> bool:
    """Return whether a provider response has no useful content or tool calls."""

    if response is None:
        return True
    return not response.text_content.strip() and not response.tool_calls


_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(api[_-]?key|token|secret|authorization)(\s*=\s*)([^\s,;]+)"
)
_BEARER_RE = re.compile(r"(?i)\bbearer\s+[a-z0-9._~+/=-]+")
