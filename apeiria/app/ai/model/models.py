"""Model routing domain models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

AIModelTaskClass = Literal[
    "planner_light",
    "reply_default",
    "reasoning_heavy",
    "memory_extraction",
    "tool_orchestration",
]


@dataclass(frozen=True)
class AIModelProfileDefinition:
    """One configured model profile."""

    profile_id: str
    name: str
    model_id: str
    task_class: AIModelTaskClass
    priority: int
    enabled: bool = True
    fallback_profile_id: str | None = None


@dataclass(frozen=True)
class AIModelRouteQuery:
    """Input for model profile resolution."""

    task_class: AIModelTaskClass
