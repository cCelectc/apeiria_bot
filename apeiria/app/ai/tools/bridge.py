"""Whitelist-based NoneBot tool bridge."""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any

from apeiria.app.ai.tools.policy import evaluate_tool_policy

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from apeiria.app.ai.tools.models import AINoneBotCapabilityRequest, AIToolPolicy
    from apeiria.app.ai.tools.registry import AIToolRegistry

    CapabilityHandler = Callable[[dict[str, Any]], Any | Awaitable[Any]]


class CapabilityNotAllowedError(RuntimeError):
    """Raised when an unregistered capability is requested."""

    def __init__(self, capability_name: str) -> None:
        super().__init__(f"capability '{capability_name}' is not registered")


class ToolPolicyDeniedError(RuntimeError):
    """Raised when skill policy rejects a bridge capability."""

    def __init__(self, capability_name: str, reason: str) -> None:
        super().__init__(f"capability '{capability_name}' denied: {reason}")


SkillNotAllowedError = CapabilityNotAllowedError
SkillPolicyDeniedError = ToolPolicyDeniedError


class AINoneBotSkillBridge:
    """Small registry for explicit NoneBot capability handlers."""

    def __init__(self) -> None:
        self._handlers: dict[str, CapabilityHandler] = {}

    def register(
        self,
        capability_name: str,
        handler: CapabilityHandler,
    ) -> None:
        self._handlers[capability_name] = handler

    def list_capabilities(self) -> list[str]:
        return sorted(self._handlers)

    def can_handle(self, capability_name: str) -> bool:
        return capability_name in self._handlers

    async def invoke(self, request: "AINoneBotCapabilityRequest") -> Any:
        handler = self._handlers.get(request.capability_name)
        if handler is None:
            raise CapabilityNotAllowedError(request.capability_name)
        result = handler(request.arguments)
        if inspect.isawaitable(result):
            return await result
        return result


async def invoke_skill_with_policy(
    *,
    registry: "AIToolRegistry",
    bridge: AINoneBotSkillBridge,
    request: "AINoneBotCapabilityRequest",
    policy: "AIToolPolicy",
) -> Any:
    """Invoke one capability only after pure policy evaluation succeeds."""

    tool = registry.get(request.capability_name)
    if tool is None:
        tool = registry.get("plugin.capability")
    if tool is None:
        raise CapabilityNotAllowedError(request.capability_name)

    decision = evaluate_tool_policy(tool, policy)
    if not decision.allowed:
        raise ToolPolicyDeniedError(request.capability_name, decision.reason)

    return await bridge.invoke(request)


__all__ = [
    "AINoneBotSkillBridge",
    "CapabilityNotAllowedError",
    "SkillNotAllowedError",
    "SkillPolicyDeniedError",
    "ToolPolicyDeniedError",
    "invoke_skill_with_policy",
]
