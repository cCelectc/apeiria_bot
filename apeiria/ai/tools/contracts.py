"""Public operation contracts for AI tool services."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AIToolExecutionCreateInput:
    """Create payload for one persisted tool execution record."""

    session_id: str
    tool_name: str
    status: str
    trace_id: str | None = None
    input_payload: Any | None = None
    output_payload: Any | None = None
