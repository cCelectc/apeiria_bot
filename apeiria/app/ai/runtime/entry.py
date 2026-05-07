"""Runtime entrypoints for live AI turns."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import TYPE_CHECKING, NoReturn, Protocol
from uuid import uuid4

if TYPE_CHECKING:
    from collections.abc import Mapping


@dataclass(frozen=True, slots=True)
class RuntimeTraceContext:
    """Bounded labels supplied by runtime surface entrypoints."""

    kind: str
    trigger: str


@dataclass(frozen=True, slots=True)
class RuntimeInput:
    """Normalized source input accepted by the runtime ingress stage."""

    source_type: str
    message_text: str
    session_id: str
    user_id: str
    sender_id: str
    source_message_id: str | None = None
    runtime_mode: str = "message"
    priority: str = "normal"
    dedupe_key: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", _read_only_mapping(self.metadata))


@dataclass(frozen=True, slots=True)
class AcceptedTurn:
    """Session-accepted turn identity shared by later runtime stages."""

    turn_id: str
    input: RuntimeInput
    lifecycle_state: str
    accepted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    diagnostics: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "diagnostics",
            _read_only_mapping(self.diagnostics),
        )

    @property
    def session_id(self) -> str:
        """Return the accepted turn's session id."""

        return self.input.session_id

    @property
    def runtime_mode(self) -> str:
        """Return the accepted turn's runtime mode."""

        return self.input.runtime_mode


@dataclass(frozen=True, slots=True)
class TurnContextMaterials:
    """Read-only materials assembled for planning one accepted turn."""

    summary: str | None = None
    messages: tuple[object, ...] = ()
    memories: tuple[object, ...] = ()
    persona: object | None = None
    relationship: object | None = None
    tools: tuple[object, ...] = ()
    diagnostics: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "diagnostics",
            _read_only_mapping(self.diagnostics),
        )


@dataclass(frozen=True, slots=True)
class TurnPlan:
    """Bounded plan consumed by runtime execution and commit."""

    reply_decision: str
    model_selection: object | None = None
    fallback_models: tuple[object, ...] = ()
    prompt_messages: tuple[object, ...] = ()
    prompt_diagnostics: Mapping[str, object] = field(default_factory=dict)
    skill_selection: object | None = None
    tool_exposure: object | None = None
    execution_mode: str = "direct"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "prompt_diagnostics",
            _read_only_mapping(self.prompt_diagnostics),
        )


@dataclass(frozen=True, slots=True)
class TurnExecutionResult:
    """Provider-neutral result produced by runtime execution."""

    reply_text: str | None = None
    model_attempts: tuple[object, ...] = ()
    tool_attempts: tuple[object, ...] = ()
    finish_reason: str | None = None
    response_source: str | None = None
    diagnostics: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "diagnostics",
            _read_only_mapping(self.diagnostics),
        )


@dataclass(frozen=True, slots=True)
class CommitResult:
    """Commit and delivery outcome returned by the runtime commit stage."""

    reply_text: str
    commit_status: str = "committed"
    delivery_status: str | None = None
    substeps: Mapping[str, str] = field(default_factory=dict)
    diagnostics: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "substeps", _read_only_mapping(self.substeps))
        object.__setattr__(
            self,
            "diagnostics",
            _read_only_mapping(self.diagnostics),
        )


@dataclass(frozen=True, slots=True)
class TurnTrace:
    """Compact terminal trace projection for one runtime turn."""

    turn_id: str
    terminal_status: str
    runtime_mode: str
    commit_status: str | None = None
    delivery_status: str | None = None
    diagnostics: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "diagnostics",
            _read_only_mapping(self.diagnostics),
        )


def _read_only_mapping(value: Mapping[str, object]) -> MappingProxyType[str, object]:
    return MappingProxyType(dict(value))


@dataclass(frozen=True, slots=True)
class RuntimeTraceRecordInput:
    """Terminal trace data produced by the runtime entry."""

    accepted_turn: AcceptedTurn | None
    trace: RuntimeTraceContext
    context: TurnContextMaterials | None = None
    plan: TurnPlan | None = None
    execution: TurnExecutionResult | None = None
    commit: CommitResult | None = None


class RuntimeIngressStage(Protocol):
    """Normalize external message and future-task sources."""

    async def accept_message(self, bot: object, event: object) -> RuntimeInput: ...

    async def accept_future_task(self, task_id: str) -> RuntimeInput: ...


class RuntimeSessionStage(Protocol):
    """Accept or terminate a normalized runtime input."""

    async def accept(
        self,
        runtime_input: RuntimeInput,
        *,
        trace_id: str,
    ) -> AcceptedTurn | None: ...


class RuntimeContextStage(Protocol):
    """Assemble read context for an accepted turn."""

    async def assemble(self, accepted_turn: AcceptedTurn) -> TurnContextMaterials: ...


class RuntimePlanningStage(Protocol):
    """Plan reply execution from accepted turn and context."""

    async def plan(
        self,
        accepted_turn: AcceptedTurn,
        context: TurnContextMaterials,
    ) -> TurnPlan | None: ...


class RuntimeExecutionStage(Protocol):
    """Execute one planned runtime turn."""

    async def execute(
        self,
        accepted_turn: AcceptedTurn,
        plan: TurnPlan,
    ) -> TurnExecutionResult: ...


class RuntimeCommitStage(Protocol):
    """Commit side effects for one executed runtime turn."""

    async def commit(
        self,
        accepted_turn: AcceptedTurn,
        context: TurnContextMaterials,
        plan: TurnPlan,
        execution: TurnExecutionResult,
    ) -> CommitResult: ...


class RuntimeTraceStage(Protocol):
    """Record terminal runtime trace projections."""

    def record(self, trace_input: RuntimeTraceRecordInput) -> object: ...


class RuntimeStageNotConfiguredError(RuntimeError):
    """Raised when AIRuntimeEntry is used before runtime stages are installed."""


class _UnavailableRuntimeStages:
    def _raise(self) -> NoReturn:
        raise RuntimeStageNotConfiguredError

    async def accept_message(self, bot: object, event: object) -> RuntimeInput:
        del bot, event
        self._raise()

    async def accept_future_task(self, task_id: str) -> RuntimeInput:
        del task_id
        self._raise()

    async def accept(
        self,
        runtime_input: RuntimeInput,
        *,
        trace_id: str,
    ) -> AcceptedTurn | None:
        del runtime_input, trace_id
        self._raise()

    async def assemble(self, accepted_turn: AcceptedTurn) -> TurnContextMaterials:
        del accepted_turn
        self._raise()

    async def plan(
        self,
        accepted_turn: AcceptedTurn,
        context: TurnContextMaterials,
    ) -> TurnPlan | None:
        del accepted_turn, context
        self._raise()

    async def execute(
        self,
        accepted_turn: AcceptedTurn,
        plan: TurnPlan,
    ) -> TurnExecutionResult:
        del accepted_turn, plan
        self._raise()

    async def commit(
        self,
        accepted_turn: AcceptedTurn,
        context: TurnContextMaterials,
        plan: TurnPlan,
        execution: TurnExecutionResult,
    ) -> CommitResult:
        del accepted_turn, context, plan, execution
        self._raise()

    def record(self, trace_input: RuntimeTraceRecordInput) -> object:
        del trace_input
        self._raise()


@dataclass(frozen=True, slots=True)
class AIRuntimeEntry:
    """Application entry for message and future-task AI turns."""

    ingress: RuntimeIngressStage = field(default_factory=_UnavailableRuntimeStages)
    session: RuntimeSessionStage = field(default_factory=_UnavailableRuntimeStages)
    context: RuntimeContextStage = field(default_factory=_UnavailableRuntimeStages)
    planning: RuntimePlanningStage = field(default_factory=_UnavailableRuntimeStages)
    execution: RuntimeExecutionStage = field(default_factory=_UnavailableRuntimeStages)
    commit: RuntimeCommitStage = field(default_factory=_UnavailableRuntimeStages)
    trace: RuntimeTraceStage = field(default_factory=_UnavailableRuntimeStages)

    async def handle_message(
        self,
        bot: object,
        event: object,
        *,
        trace: RuntimeTraceContext | None = None,
    ) -> str | None:
        """Handle one platform message through the new runtime stage order."""

        runtime_input = await self.ingress.accept_message(bot, event)
        result = await self._run_turn(
            runtime_input,
            trace=trace
            or RuntimeTraceContext(kind="conversation", trigger="nonebot_message"),
        )
        return result.reply_text if result is not None else None

    async def handle_future_task(
        self,
        task_id: str,
        *,
        trace: RuntimeTraceContext | None = None,
    ) -> CommitResult | None:
        """Handle one due future task through the new runtime stage order."""

        runtime_input = await self.ingress.accept_future_task(task_id)
        return await self._run_turn(
            runtime_input,
            trace=trace
            or RuntimeTraceContext(kind="conversation", trigger="ai_future_task"),
        )

    async def _run_turn(
        self,
        runtime_input: RuntimeInput,
        *,
        trace: RuntimeTraceContext,
    ) -> CommitResult | None:
        trace_id = f"ai_trace_{uuid4().hex}"
        accepted_turn = await self.session.accept(runtime_input, trace_id=trace_id)
        if accepted_turn is None:
            self.trace.record(RuntimeTraceRecordInput(None, trace=trace))
            return None

        context = await self.context.assemble(accepted_turn)
        plan = await self.planning.plan(accepted_turn, context)
        if plan is None:
            self.trace.record(
                RuntimeTraceRecordInput(
                    accepted_turn,
                    trace=trace,
                    context=context,
                )
            )
            return None

        execution = await self.execution.execute(accepted_turn, plan)
        commit = await self.commit.commit(accepted_turn, context, plan, execution)
        self.trace.record(
            RuntimeTraceRecordInput(
                accepted_turn,
                trace=trace,
                context=context,
                plan=plan,
                execution=execution,
                commit=commit,
            )
        )
        return commit


__all__ = [
    "AIRuntimeEntry",
    "AcceptedTurn",
    "CommitResult",
    "RuntimeCommitStage",
    "RuntimeContextStage",
    "RuntimeExecutionStage",
    "RuntimeIngressStage",
    "RuntimeInput",
    "RuntimePlanningStage",
    "RuntimeSessionStage",
    "RuntimeStageNotConfiguredError",
    "RuntimeTraceContext",
    "RuntimeTraceRecordInput",
    "RuntimeTraceStage",
    "TurnContextMaterials",
    "TurnExecutionResult",
    "TurnPlan",
    "TurnTrace",
]
