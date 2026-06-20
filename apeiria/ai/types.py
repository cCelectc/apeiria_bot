from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolResult:
    success: bool
    content: str | None = None
    error: str | None = None


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    execute: Callable[..., Any]


@dataclass
class Message:
    role: str
    content: str
    user_id: str | None = None
    name: str | None = None
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None


class StreamEventType(Enum):
    TEXT_DELTA = "text_delta"
    TOOL_CALL_START = "tool_call_start"
    TOOL_CALL_DELTA = "tool_call_delta"
    TOOL_CALL_END = "tool_call_end"
    USAGE = "usage"
    END = "end"
    ERROR = "error"


@dataclass
class StreamEvent:
    type: StreamEventType
    text: str | None = None
    tool_call: ToolCall | None = None
    usage: TokenUsage | None = None
    error: str | None = None


@dataclass
class PromptFragment:
    role: str
    content: str
    placement: str = "first"


@dataclass
class RerankResult:
    index: int
    score: float
    text: str | None = None


@dataclass
class SessionContext:
    session_id: str
    platform: str
    scene_type: str
    scene_id: str
    user_id: str | None = None
    messages: list[Message] = field(default_factory=list)


@dataclass
class TurnResult:
    has_reply: bool
    reply_text: str | None = None
    error: str | None = None
    usage: TokenUsage | None = None


@dataclass
class SessionRhythmState:
    session_id: str
    messages: list[Any] = field(default_factory=list)
    message_counter: int = 0
    last_message_at: float | None = None
    last_reply_at: float | None = None
    no_action_count: int = 0
    next_tick_at: float = 0.0
    recent_reply_timestamps: list[float] = field(default_factory=list)
