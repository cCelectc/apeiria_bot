"""AI domain status helpers used by the builtin AI plugin shell."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from apeiria.ai.model.routing.models import AIModelRouteQuery

if TYPE_CHECKING:
    from apeiria.ai.model import AIModelBindingTarget, AISelectedModel


@dataclass(frozen=True)
class AIServiceStatus:
    """Status payload for the currently loaded AI runtime."""

    phase: str
    summary: str
    ready: bool
    next_step: str | None = None
    dependencies: tuple["AIRuntimeDependencyStatus", ...] = ()


@dataclass(frozen=True)
class AIRuntimeDependencyStatus:
    """Read-only readiness state for one production AI runtime dependency."""

    key: str
    available: bool
    detail: str
    next_step: str | None = None


class _ModelGateway(Protocol):
    async def select_model(
        self,
        *,
        query: AIModelRouteQuery | None = None,
        target: "AIModelBindingTarget | None" = None,
    ) -> "AISelectedModel | None": ...


class _RuntimeReadinessProbe(Protocol):
    def inspect(self) -> tuple[AIRuntimeDependencyStatus, ...]: ...


class AIService:
    """Service for reporting the current AI runtime status."""

    def __init__(
        self,
        model_gateway: _ModelGateway | None = None,
        runtime_readiness_probe: _RuntimeReadinessProbe | None = None,
    ) -> None:
        self._model_gateway = model_gateway
        self._runtime_readiness_probe = (
            runtime_readiness_probe or _default_runtime_readiness_probe()
        )

    async def get_status(self) -> AIServiceStatus:
        selected = await self._resolve_default_reply_model()
        dependencies = self._runtime_readiness_probe.inspect()
        dependency_summary = _format_dependency_summary(dependencies)
        degraded_dependencies = [
            dependency for dependency in dependencies if not dependency.available
        ]
        if selected is None:
            next_step = (
                "Configure or enable a chat model in AI Management, then make it "
                "available to the default reply path."
            )
            return AIServiceStatus(
                phase="runtime_degraded",
                ready=False,
                summary=(
                    "AI runtime is degraded. Reply runtime is degraded. "
                    f"{dependency_summary}. {next_step}"
                ),
                next_step=next_step,
                dependencies=dependencies,
            )

        if degraded_dependencies:
            next_step = degraded_dependencies[0].next_step
            return AIServiceStatus(
                phase="runtime_degraded",
                ready=False,
                summary=(
                    "AI runtime is degraded. "
                    "AI reply generation has a selectable model: "
                    f"{_format_selected_model(selected)}. {dependency_summary}."
                ),
                next_step=next_step,
                dependencies=dependencies,
            )

        return AIServiceStatus(
            phase="runtime_ready",
            ready=True,
            summary=(
                "AI reply generation has a selectable model: "
                f"{_format_selected_model(selected)}. {dependency_summary}."
            ),
            dependencies=dependencies,
        )

    async def _resolve_default_reply_model(self) -> "AISelectedModel | None":
        gateway = self._model_gateway
        if gateway is None:
            from apeiria.ai.model import model_gateway

            gateway = model_gateway
        return await gateway.select_model(
            query=AIModelRouteQuery(task_class="reply_default"),
            target=None,
        )


def _format_selected_model(selected: "AISelectedModel") -> str:
    model_name = selected.resolved_model_name or selected.profile.model_id
    return f"{selected.source.source_id}:{model_name}"


def _format_dependency_summary(
    dependencies: tuple[AIRuntimeDependencyStatus, ...],
) -> str:
    labels = {
        "future_task_storage": "future-task storage",
        "delivery_attempt_storage": "delivery attempt storage",
        "scheduler_recovery": "scheduler recovery",
        "tool_registry": "tool registry",
        "skill_catalog": "skill catalog",
        "capability_bridge": "capability bridge",
        "delivery_gateway": "delivery gateway",
        "trace_storage": "trace storage",
    }
    parts = []
    for dependency in dependencies:
        label = labels.get(dependency.key, dependency.key.replace("_", " "))
        if dependency.available and dependency.key == "scheduler_recovery":
            detail = "registered"
        elif dependency.available:
            detail = "available"
        elif dependency.key in {
            "future_task_storage",
            "delivery_attempt_storage",
            "delivery_gateway",
            "trace_storage",
        }:
            detail = "unavailable"
        else:
            detail = dependency.detail
        parts.append(f"{label} {detail}")
    return "; ".join(parts)


def _default_runtime_readiness_probe() -> _RuntimeReadinessProbe:
    from apeiria.app.ai.diagnostics.readiness import AIRuntimeReadinessProbe

    return AIRuntimeReadinessProbe()


ai_service = AIService()
