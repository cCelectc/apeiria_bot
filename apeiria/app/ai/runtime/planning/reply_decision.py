"""Reply-decision planning boundary."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apeiria.ai.model import AIModelTaskClass


def select_pre_tool_reply_task_class(*, has_tools: bool) -> "AIModelTaskClass":
    """Choose the task class for the first reply model call."""

    return "tool_orchestration" if has_tools else "reply_default"


def select_post_tool_reply_task_class() -> "AIModelTaskClass":
    """Choose the task class for the final answer after tool execution."""

    return "reply_roleplay"


__all__ = [
    "select_post_tool_reply_task_class",
    "select_pre_tool_reply_task_class",
]
