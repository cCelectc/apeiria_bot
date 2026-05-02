"""AI plugin startup lifecycle coordination."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, Protocol

from nonebot.log import logger

from apeiria.ai.contributions import (
    AIPluginContributionRegistry,
    ai_plugin_contributions,
)
from apeiria.app.ai.tooling import load_app_ai_tool_modules

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from pathlib import Path

    from apeiria.ai.tools import AIToolSpec
    from apeiria.app.ai.future_task.service import AIFutureTaskRecoveryResult

    AICapabilityHandler = Callable[[dict[str, Any]], Any | Awaitable[Any]]

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
    diagnostics: tuple[str, ...] = ()


class _ToolRegistry(Protocol):
    def register(self, tool: "AIToolSpec") -> None: ...

    def list_tools(self) -> list["AIToolSpec"]: ...

    def register_pending_tools(self) -> int: ...


class _CapabilityBridge(Protocol):
    def register(
        self,
        capability_name: str,
        handler: "AICapabilityHandler",
    ) -> None: ...

    def list_capabilities(self) -> list[str]: ...


class _ToolService(Protocol):
    @property
    def registry(self) -> _ToolRegistry: ...

    @property
    def capability_bridge(self) -> _CapabilityBridge: ...


class _SkillService(Protocol):
    def ensure_initialized(
        self,
        *,
        skill_sources: tuple["Path", ...] = (),
    ) -> None: ...


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
                tool_service.registry.register(tool)
            for contribution in contributions.capability_handlers:
                tool_service.capability_bridge.register(
                    contribution.capability_name,
                    contribution.handler,
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
            from apeiria.app.ai.future_task import ai_future_task_service

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
            _not_initialized_component("capability_bridge"),
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
        _failed_component("capability_bridge", detail),
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
    capability_count = len(tool_service.capability_bridge.list_capabilities())
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
            key="capability_bridge",
            available=True,
            detail=f"{capability_count}_capabilities",
        ),
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
        diagnostics=snapshot.diagnostics,
    )


def _bounded_detail(exc: Exception) -> str:
    return f"{type(exc).__name__}: {str(exc)[:160]}"


ai_lifecycle_coordinator = AIPluginLifecycleCoordinator()


__all__ = [
    "AIFutureTaskRecoveryDiagnostics",
    "AILifecycleComponentStatus",
    "AILifecycleSnapshot",
    "AIPluginLifecycleCoordinator",
    "ai_lifecycle_coordinator",
    "ensure_ai_runtime_support_initialized",
]
