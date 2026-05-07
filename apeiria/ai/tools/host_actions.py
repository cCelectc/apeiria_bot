"""Host-neutral action registry for plugin-backed AI capabilities."""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from apeiria.ai.capabilities.bindings import (
    AICapabilityBinding,
    AICapabilityBindingType,
    create_host_action_binding,
)
from apeiria.ai.capabilities.contracts import (
    AICapabilityContract,
    AICapabilityKind,
    AICapabilityOrigin,
    AICapabilitySafety,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    HostActionHandler = Callable[[dict[str, Any]], Any | Awaitable[Any]]

AIHostActionStatus = Literal["ready", "incomplete", "disabled"]


@dataclass(frozen=True)
class AIHostActionContractInput:
    """Create payload for an executable host-action contract."""

    name: str
    description: str
    input_schema: dict[str, Any] | None = None
    read_only: bool = True
    risk_level: str = "low"
    concurrency_safe: bool = True
    origin: AICapabilityOrigin = AICapabilityOrigin.BUILTIN
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class AIHostActionRecord:
    """One registered host action and its capability contract status."""

    action_name: str
    handler: "HostActionHandler"
    status: AIHostActionStatus
    contract: AICapabilityContract | None = None
    binding: AICapabilityBinding | None = None
    reason: str | None = None


@dataclass(frozen=True)
class AIHostActionSnapshot:
    """Immutable host-action registry read model."""

    records: tuple[AIHostActionRecord, ...]

    @property
    def ready_actions(self) -> tuple[AIHostActionRecord, ...]:
        return tuple(record for record in self.records if record.status == "ready")

    @property
    def incomplete_actions(self) -> tuple[AIHostActionRecord, ...]:
        return tuple(record for record in self.records if record.status == "incomplete")


class HostActionNotAllowedError(RuntimeError):
    """Raised when an unavailable or incomplete host action is requested."""

    def __init__(self, action_name: str) -> None:
        super().__init__(f"host action '{action_name}' is not registered")


class HostActionPolicyDeniedError(RuntimeError):
    """Raised when policy rejects a selected host action."""

    def __init__(self, action_name: str, reason: str) -> None:
        super().__init__(f"host action '{action_name}' denied: {reason}")


class AIHostActionRegistry:
    """Registry for host/plugin action handlers and complete contracts."""

    def __init__(self) -> None:
        self._records: dict[str, AIHostActionRecord] = {}

    def register_handler(
        self,
        action_name: str,
        handler: "HostActionHandler",
    ) -> AIHostActionRecord:
        """Register a diagnostic-only handler without a complete contract."""

        record = AIHostActionRecord(
            action_name=action_name,
            handler=handler,
            status="incomplete",
            reason="missing capability contract",
        )
        self._records[action_name] = record
        return record

    def register_contract(
        self,
        contract: AICapabilityContract,
    ) -> AIHostActionRecord:
        """Register contract metadata without an executable handler."""

        _validate_host_action_contract(contract)
        record = AIHostActionRecord(
            action_name=contract.name,
            handler=_missing_host_action_handler,
            status="incomplete",
            contract=contract,
            reason="missing host-action handler",
        )
        self._records[contract.name] = record
        return record

    def register_action(
        self,
        *,
        contract: AICapabilityContract,
        handler: "HostActionHandler",
    ) -> AIHostActionRecord:
        """Register a complete executable host action."""

        _validate_host_action_contract(contract)
        binding = create_host_action_binding(
            contract_name=contract.name,
            binding_key=f"host:{contract.name}",
            action_name=contract.name,
            handler=handler,
        )
        record = AIHostActionRecord(
            action_name=contract.name,
            handler=handler,
            status="ready",
            contract=contract,
            binding=binding,
        )
        self._records[contract.name] = record
        return record

    def list_actions(self) -> list[str]:
        """Return registered host action names."""

        return sorted(self._records)

    def can_handle(self, action_name: str) -> bool:
        """Return whether a complete host action can be invoked."""

        record = self._records.get(action_name)
        return record is not None and record.status == "ready"

    async def invoke(
        self,
        action_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> Any:
        """Invoke one complete host action."""

        record = self._records.get(action_name)
        if record is None or record.status != "ready":
            raise HostActionNotAllowedError(action_name)
        result = record.handler(arguments or {})
        if inspect.isawaitable(result):
            return await result
        return result

    def snapshot(self) -> AIHostActionSnapshot:
        """Return a deterministic read snapshot."""

        return AIHostActionSnapshot(
            records=tuple(self._records[name] for name in sorted(self._records))
        )


def _validate_host_action_contract(contract: AICapabilityContract) -> None:
    if contract.kind is not AICapabilityKind.EXECUTABLE:
        msg = "host actions require executable capability contracts"
        raise ValueError(msg)


def _missing_host_action_handler(_: dict[str, Any]) -> Any:
    msg = "host action handler is not registered"
    raise HostActionNotAllowedError(msg)


def host_action_contract(
    create_input: AIHostActionContractInput,
) -> AICapabilityContract:
    """Build a complete executable host-action contract."""

    return AICapabilityContract(
        name=create_input.name,
        kind=AICapabilityKind.EXECUTABLE,
        origin=create_input.origin,
        description=create_input.description,
        input_schema=create_input.input_schema or {},
        safety=AICapabilitySafety(
            read_only=create_input.read_only,
            risk_level=create_input.risk_level,  # type: ignore[arg-type]
            concurrency_safe=create_input.concurrency_safe,
        ),
        tags=create_input.tags,
    )


async def invoke_host_action_with_policy(
    *,
    registry: "AIToolRegistry",
    host_actions: AIHostActionRegistry,
    action_name: str,
    arguments: dict[str, Any] | None,
    policy: "AIToolPolicy",
) -> Any:
    """Invoke one host action only after capability policy evaluation succeeds."""

    from apeiria.ai.tools.policy import evaluate_tool_policy

    tool = registry.get(action_name)
    if tool is None:
        raise HostActionNotAllowedError(action_name)

    decision = evaluate_tool_policy(
        tool,
        policy,
        binding_type=AICapabilityBindingType.HOST_ACTION,
    )
    if not decision.allowed:
        raise HostActionPolicyDeniedError(action_name, decision.reason)

    return await host_actions.invoke(action_name, arguments)


if TYPE_CHECKING:
    from apeiria.ai.tools.models import AIToolPolicy
    from apeiria.ai.tools.registry import AIToolRegistry


__all__ = [
    "AIHostActionContractInput",
    "AIHostActionRecord",
    "AIHostActionRegistry",
    "AIHostActionSnapshot",
    "AIHostActionStatus",
    "HostActionNotAllowedError",
    "HostActionPolicyDeniedError",
    "host_action_contract",
    "invoke_host_action_with_policy",
]
