"""AI plugin startup lifecycle coordination."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, Protocol

from nonebot.log import logger

from apeiria.ai.capabilities import (
    AICapabilityBindingSnapshot,
    AICapabilityBindingType,
    AICapabilityContract,
    AICapabilityContractSnapshot,
    capability_contract_from_skill_definition,
)
from apeiria.ai.contributions import (
    AIPluginContributionRegistry,
    ai_plugin_contributions,
)
from apeiria.app.ai.tooling import load_app_ai_tool_modules

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from pathlib import Path

    from apeiria.ai.capabilities import AICapabilityBinding
    from apeiria.ai.skills import AISkillMetadata
    from apeiria.ai.tools.host_actions import (
        AIHostActionRecord,
        AIHostActionSnapshot,
    )
    from apeiria.app.ai.future_tasks.service import AIFutureTaskRecoveryResult

    AIHostActionHandler = Callable[[dict[str, Any]], Any | Awaitable[Any]]

AILifecycleSource = Literal[
    "startup",
    "runtime_fallback",
    "admin_fallback",
    "not_initialized",
    "failed",
]

_STARTUP_NEXT_STEP = "Load the AI plugin startup lifecycle hook."


@dataclass(frozen=True)
class AILifecycleComponentStatus:
    """Read-only status for one startup-prepared AI support component."""

    key: str
    available: bool
    detail: str
    next_step: str | None = None


@dataclass(frozen=True)
class AICapabilityInventoryRecord:
    """Unified admin read model for one AI capability contract."""

    name: str
    kind: str
    origin: str
    description: str
    input_schema: dict[str, Any]
    read_only: bool
    concurrency_safe: bool
    risk_level: str
    tags: tuple[str, ...]
    version: int
    display_name: str | None = None
    binding_key: str | None = None
    binding_type: str | None = None
    availability: Literal["ready", "incomplete", "disabled"] = "incomplete"
    policy_status: str = "not_evaluated"
    diagnostics: tuple[str, ...] = ()
    required_capabilities: tuple[str, ...] = ()


@dataclass(frozen=True)
class _InventoryBindingFacts:
    binding_key: str | None
    binding_type: str | None
    availability: Literal["ready", "incomplete", "disabled"]
    diagnostics: tuple[str, ...] = ()
    required_capabilities: tuple[str, ...] = ()


@dataclass(frozen=True)
class AIFutureTaskRecoveryDiagnostics:
    """Bounded diagnostics for future-task startup recovery."""

    attempted: bool
    rescheduled_count: int = 0
    failed_count: int = 0
    detail: str = "not_attempted"


@dataclass(frozen=True)
class AILifecycleSnapshot:
    """Read-only lifecycle state projected to readiness and admin surfaces."""

    initialized: bool
    initialization_source: AILifecycleSource
    components: tuple[AILifecycleComponentStatus, ...]
    recovery: AIFutureTaskRecoveryDiagnostics | None = None
    capabilities: tuple[AICapabilityInventoryRecord, ...] = ()
    diagnostics: tuple[str, ...] = ()


class _ToolRegistry(Protocol):
    def register_contract_and_binding(
        self,
        *,
        contract: AICapabilityContract,
        binding: "AICapabilityBinding",
    ) -> None: ...

    def list_tools(self) -> list[AICapabilityContract]: ...

    def register_pending_tools(self) -> int: ...

    def contract_snapshot(self) -> AICapabilityContractSnapshot: ...

    def binding_snapshot(self) -> AICapabilityBindingSnapshot: ...


class _HostActionRegistry(Protocol):
    def register_contract(
        self,
        contract: AICapabilityContract,
    ) -> "AIHostActionRecord": ...

    def register_action(
        self,
        *,
        contract: AICapabilityContract,
        handler: "AIHostActionHandler",
    ) -> "AIHostActionRecord": ...

    def register_handler(
        self,
        action_name: str,
        handler: "AIHostActionHandler",
    ) -> "AIHostActionRecord": ...

    def list_actions(self) -> list[str]: ...

    def snapshot(self) -> "AIHostActionSnapshot": ...


class _ToolService(Protocol):
    @property
    def registry(self) -> _ToolRegistry: ...

    @property
    def host_action_registry(self) -> _HostActionRegistry: ...


class _SkillService(Protocol):
    def ensure_initialized(
        self,
        *,
        skill_sources: tuple["Path", ...] = (),
    ) -> None: ...

    def list_skills(self) -> list["AISkillMetadata"]: ...


class _FutureTaskService(Protocol):
    async def recover_scheduled_tasks(self) -> "AIFutureTaskRecoveryResult": ...


class AIPluginLifecycleCoordinator:
    """Prepare process-level AI support state for the builtin AI plugin."""

    def __init__(
        self,
        *,
        contribution_registry: AIPluginContributionRegistry | None = None,
        tool_service: _ToolService | None = None,
        skill_service: _SkillService | None = None,
        future_task_service: _FutureTaskService | None = None,
        app_tool_loader: "Callable[[], None] | None" = None,
    ) -> None:
        self._contribution_registry = contribution_registry or ai_plugin_contributions
        self._tool_service = tool_service
        self._skill_service = skill_service
        self._future_task_service = future_task_service
        self._app_tool_loader = app_tool_loader or load_app_ai_tool_modules
        self._snapshot = _not_initialized_snapshot()
        self._recovery: AIFutureTaskRecoveryDiagnostics | None = None
        self._future_recovery_attempted = False

    async def startup(self) -> AILifecycleSnapshot:
        """Run the AI plugin startup lifecycle after user plugins are loaded."""

        snapshot = self.ensure_runtime_support_initialized(source="startup")
        if snapshot.initialized and not self._future_recovery_attempted:
            await self._recover_future_tasks()
        return self.inspect()

    def ensure_runtime_support_initialized(
        self,
        *,
        source: AILifecycleSource = "runtime_fallback",
    ) -> AILifecycleSnapshot:
        """Prepare AI registries and skill catalog idempotently."""

        tool_service = self._get_tool_service()
        skill_service = self._get_skill_service()
        try:
            self._app_tool_loader()
            pending_tool_count = tool_service.registry.register_pending_tools()
            contributions = self._contribution_registry.snapshot()
            for tool in contributions.tools:
                tool_service.registry.register_contract_and_binding(
                    contract=tool.contract,
                    binding=tool.binding,
                )
            for contribution in contributions.host_actions:
                tool_service.host_action_registry.register_action(
                    contract=contribution.contract,
                    handler=contribution.handler,
                )
            for contribution in contributions.host_action_handlers:
                tool_service.host_action_registry.register_handler(
                    contribution.action_name,
                    contribution.handler,
                )
            for contribution in contributions.capability_contracts:
                if contribution.contract.name in {
                    item.contract.name for item in contributions.host_actions
                }:
                    continue
                tool_service.host_action_registry.register_contract(
                    contribution.contract
                )
            skill_sources = tuple(source.path for source in contributions.skill_sources)
            skill_service.ensure_initialized(skill_sources=skill_sources)
        except Exception as exc:  # noqa: BLE001
            detail = _bounded_detail(exc)
            logger.opt(exception=exc).warning("AI plugin lifecycle failed: {}", detail)
            self._snapshot = AILifecycleSnapshot(
                initialized=False,
                initialization_source="failed",
                components=_failed_components(detail),
                recovery=self._recovery,
                capabilities=(),
                diagnostics=(detail,),
            )
            return self._snapshot

        effective_source = _effective_source(
            requested=source,
            current=self._snapshot.initialization_source,
        )
        self._snapshot = AILifecycleSnapshot(
            initialized=True,
            initialization_source=effective_source,
            components=_ready_components(
                tool_service=tool_service,
                skill_source_count=len(skill_sources),
                pending_tool_count=pending_tool_count,
            ),
            recovery=self._recovery,
            capabilities=_build_capability_inventory(
                tool_service=tool_service,
                skill_service=skill_service,
            ),
        )
        return self._snapshot

    def inspect(self) -> AILifecycleSnapshot:
        """Return lifecycle state without initializing or importing handlers."""

        return self._snapshot

    def _get_tool_service(self) -> _ToolService:
        if self._tool_service is None:
            from apeiria.ai.tools import ai_tool_service

            return ai_tool_service
        return self._tool_service

    def _get_skill_service(self) -> _SkillService:
        if self._skill_service is None:
            from apeiria.ai.skills import ai_skill_service

            return ai_skill_service
        return self._skill_service

    def _get_future_task_service(self) -> _FutureTaskService:
        if self._future_task_service is None:
            from apeiria.app.ai.future_tasks import ai_future_task_service

            return ai_future_task_service
        return self._future_task_service

    async def _recover_future_tasks(self) -> None:
        self._future_recovery_attempted = True
        try:
            result = await self._get_future_task_service().recover_scheduled_tasks()
        except Exception as exc:  # noqa: BLE001
            detail = _bounded_detail(exc)
            logger.opt(exception=exc).warning(
                "AI future-task recovery failed during plugin startup: {}",
                detail,
            )
            self._recovery = AIFutureTaskRecoveryDiagnostics(
                attempted=True,
                detail=detail,
            )
            self._snapshot = _with_recovery(self._snapshot, self._recovery)
            return

        rescheduled_count = len(result.rescheduled_task_ids)
        failed_count = len(result.failed_task_ids)
        if result.rescheduled_task_ids or result.failed_task_ids:
            logger.info(
                "Recovered AI future tasks: rescheduled={} failed={}",
                rescheduled_count,
                failed_count,
            )
        self._recovery = AIFutureTaskRecoveryDiagnostics(
            attempted=True,
            rescheduled_count=rescheduled_count,
            failed_count=failed_count,
            detail="recovered",
        )
        self._snapshot = _with_recovery(self._snapshot, self._recovery)


def ensure_ai_runtime_support_initialized(
    *,
    source: AILifecycleSource = "runtime_fallback",
) -> AILifecycleSnapshot:
    """Fallback entry for focused tests and partial runtime use."""

    return ai_lifecycle_coordinator.ensure_runtime_support_initialized(source=source)


def _not_initialized_snapshot() -> AILifecycleSnapshot:
    return AILifecycleSnapshot(
        initialized=False,
        initialization_source="not_initialized",
        components=(
            _not_initialized_component("tool_registry"),
            _not_initialized_component("skill_catalog"),
            _not_initialized_component("host_action_registry"),
        ),
    )


def _not_initialized_component(key: str) -> AILifecycleComponentStatus:
    return AILifecycleComponentStatus(
        key=key,
        available=False,
        detail="not_initialized",
        next_step=_STARTUP_NEXT_STEP,
    )


def _failed_components(detail: str) -> tuple[AILifecycleComponentStatus, ...]:
    return (
        _failed_component("tool_registry", detail),
        _failed_component("skill_catalog", detail),
        _failed_component("host_action_registry", detail),
    )


def _failed_component(key: str, detail: str) -> AILifecycleComponentStatus:
    return AILifecycleComponentStatus(
        key=key,
        available=False,
        detail=detail,
        next_step=_STARTUP_NEXT_STEP,
    )


def _ready_components(
    *,
    tool_service: _ToolService,
    skill_source_count: int,
    pending_tool_count: int,
) -> tuple[AILifecycleComponentStatus, ...]:
    tool_count = len(tool_service.registry.list_tools())
    host_action_count = len(tool_service.host_action_registry.list_actions())
    return (
        AILifecycleComponentStatus(
            key="tool_registry",
            available=True,
            detail=f"{tool_count}_tools",
        ),
        AILifecycleComponentStatus(
            key="skill_catalog",
            available=True,
            detail=(
                f"initialized; skill_sources={skill_source_count}; "
                f"pending_tools={pending_tool_count}"
            ),
        ),
        AILifecycleComponentStatus(
            key="host_action_registry",
            available=True,
            detail=f"{host_action_count}_host_actions",
        ),
    )


def _build_capability_inventory(
    *,
    tool_service: _ToolService,
    skill_service: _SkillService,
) -> tuple[AICapabilityInventoryRecord, ...]:
    records: dict[str, AICapabilityInventoryRecord] = {}

    contract_snapshot = tool_service.registry.contract_snapshot()
    binding_snapshot = tool_service.registry.binding_snapshot()
    for contract in contract_snapshot.contracts:
        binding = binding_snapshot.by_contract.get(contract.name)
        records[contract.name] = _inventory_record(
            contract=contract,
            binding=_InventoryBindingFacts(
                binding_key=binding.binding_key if binding is not None else None,
                binding_type=(
                    binding.binding_type.value if binding is not None else None
                ),
                availability="ready" if binding is not None else "incomplete",
                diagnostics=() if binding is not None else ("missing binding",),
            ),
        )

    host_snapshot = tool_service.host_action_registry.snapshot()
    for host_action in host_snapshot.records:  # type: ignore[attr-defined]
        contract = host_action.contract
        if contract is None:
            records[host_action.action_name] = AICapabilityInventoryRecord(
                name=host_action.action_name,
                kind="executable",
                origin="plugin",
                description="Host action handler without a capability contract.",
                input_schema={
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
                read_only=False,
                concurrency_safe=False,
                risk_level="high",
                tags=(),
                version=1,
                availability="incomplete",
                diagnostics=(host_action.reason or "missing capability contract",),
            )
            continue
        binding = host_action.binding
        records[contract.name] = _inventory_record(
            contract=contract,
            binding=_InventoryBindingFacts(
                binding_key=binding.binding_key if binding is not None else None,
                binding_type=(
                    binding.binding_type.value if binding is not None else None
                ),
                availability="ready" if binding is not None else "incomplete",
                diagnostics=(
                    ()
                    if binding is not None
                    else (host_action.reason or "missing binding",)
                ),
            ),
        )

    for skill in skill_service.list_skills():
        if skill.origin != "file":  # type: ignore[attr-defined]
            continue
        contract, binding = capability_contract_from_skill_definition(
            skill,  # type: ignore[arg-type]
            load_prompt=lambda: "",
        )
        records[contract.name] = _inventory_record(
            contract=contract,
            binding=_InventoryBindingFacts(
                binding_key=binding.binding_key,
                binding_type=AICapabilityBindingType.PROMPT_SKILL.value,
                availability="ready",
                required_capabilities=binding.required_capabilities,
            ),
        )

    return tuple(records[name] for name in sorted(records))


def _inventory_record(
    *,
    contract: object,
    binding: _InventoryBindingFacts,
) -> AICapabilityInventoryRecord:
    safety = contract.safety  # type: ignore[attr-defined]
    return AICapabilityInventoryRecord(
        name=contract.name,  # type: ignore[attr-defined]
        kind=contract.kind.value,  # type: ignore[attr-defined]
        origin=contract.origin.value,  # type: ignore[attr-defined]
        description=contract.description,  # type: ignore[attr-defined]
        input_schema=dict(contract.input_schema),  # type: ignore[attr-defined]
        read_only=safety.read_only,
        concurrency_safe=safety.concurrency_safe,
        risk_level=safety.risk_level,
        tags=contract.tags,  # type: ignore[attr-defined]
        version=contract.version,  # type: ignore[attr-defined]
        display_name=contract.display_name,  # type: ignore[attr-defined]
        binding_key=binding.binding_key,
        binding_type=binding.binding_type,
        availability=binding.availability,
        policy_status="not_evaluated",
        diagnostics=binding.diagnostics,
        required_capabilities=binding.required_capabilities,
    )


def _effective_source(
    *,
    requested: AILifecycleSource,
    current: AILifecycleSource,
) -> AILifecycleSource:
    if current == "startup" and requested != "startup":
        return "startup"
    if requested in {"startup", "runtime_fallback", "admin_fallback"}:
        return requested
    return "runtime_fallback"


def _with_recovery(
    snapshot: AILifecycleSnapshot,
    recovery: AIFutureTaskRecoveryDiagnostics,
) -> AILifecycleSnapshot:
    return AILifecycleSnapshot(
        initialized=snapshot.initialized,
        initialization_source=snapshot.initialization_source,
        components=snapshot.components,
        recovery=recovery,
        capabilities=snapshot.capabilities,
        diagnostics=snapshot.diagnostics,
    )


def _bounded_detail(exc: Exception) -> str:
    return f"{type(exc).__name__}: {str(exc)[:160]}"


ai_lifecycle_coordinator = AIPluginLifecycleCoordinator()


__all__ = [
    "AICapabilityInventoryRecord",
    "AIFutureTaskRecoveryDiagnostics",
    "AILifecycleComponentStatus",
    "AILifecycleSnapshot",
    "AIPluginLifecycleCoordinator",
    "ai_lifecycle_coordinator",
    "ensure_ai_runtime_support_initialized",
]
