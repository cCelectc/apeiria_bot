"""Public operation contracts for AI tool services."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from apeiria.ai.tools.models import AIToolExecutionStatus


@dataclass(frozen=True)
class AIToolObservationCreateInput:
    """Create payload for one persisted tool observation record."""

    session_id: str
    tool_name: str
    status: "AIToolExecutionStatus"
    trace_id: str | None = None
    call_id: str | None = None
    reason: str | None = None
    input_payload: Any | None = None
    output_payload: Any | None = None
