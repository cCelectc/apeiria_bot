"""Model routing domain models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

AIModelTaskClass = Literal[
    "planner_light",
    "reply_default",
    "reply_roleplay",
    "reasoning_heavy",
    "memory_extraction",
    "tool_orchestration",
]
AIModelRouteMode = Literal["primary_fallback", "load_balance"]
AIModelRouteAlgorithm = Literal["ordered", "weighted_random"]
AIModelRouteScopeType = Literal["global", "group", "user", "conversation"]


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


@dataclass(frozen=True)
class AIModelRouteDefinition:
    """One owner-managed model route policy."""

    route_id: str
    name: str
    task_class: AIModelTaskClass
    mode: AIModelRouteMode
    algorithm: AIModelRouteAlgorithm
    fallback_on_failure: bool = True
    enabled: bool = True


@dataclass(frozen=True)
class AIModelRouteMemberDefinition:
    """One profile member in a model route."""

    route_member_id: str
    route_id: str
    profile_id: str
    position: int
    weight: int = 1
    enabled: bool = True


@dataclass(frozen=True)
class AIModelRouteBindingSpec:
    """One scoped route binding for a task class."""

    binding_id: str
    scope_type: AIModelRouteScopeType
    scope_id: str
    task_class: AIModelTaskClass
    route_id: str
