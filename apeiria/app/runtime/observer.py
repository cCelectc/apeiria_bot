"""Runtime matcher observation shell."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from apeiria.app.runtime.diagnostics import (
    RuntimeDiagnostic,
    runtime_diagnostic_recorder,
)
from apeiria.app.runtime.effect import (
    bind_effect_queue,
    reset_effect_queue,
)
from apeiria.app.runtime.models import (
    DispatchRequest,
    ExecutionReport,
    InvocationDisposition,
    RuntimeFrame,
)
from apeiria.app.runtime.normalize import runtime_ingress_normalizer

if TYPE_CHECKING:
    from collections.abc import Iterator

    from nonebot.adapters import Bot, Event
    from nonebot.matcher import Matcher


_current_frame: ContextVar[RuntimeFrame | None] = ContextVar(
    "apeiria_runtime_frame",
    default=None,
)


@dataclass
class _MatcherBinding:
    """Per-matcher observer bookkeeping tied to one in-flight run."""

    frame: RuntimeFrame
    effect_token: Any = field(default=None)
    frame_token: Any = field(default=None)


@dataclass(frozen=True)
class MatcherObservation:
    """Final observation report emitted after a matcher run."""

    request: DispatchRequest
    report: ExecutionReport


def current_frame() -> RuntimeFrame | None:
    """Return the matcher-scoped runtime frame, if any."""

    return _current_frame.get()


def current_request_id() -> str | None:
    frame = _current_frame.get()
    return frame.request.request_id if frame else None


@contextmanager
def _frame_scope(frame: RuntimeFrame) -> "Iterator[RuntimeFrame]":
    token = _current_frame.set(frame)
    try:
        yield frame
    finally:
        _current_frame.reset(token)


class RuntimeMatcherObserver:
    """Build and seal `DispatchRequest` / `ExecutionReport` for matcher runs."""

    def __init__(self) -> None:
        self._bindings: dict[int, _MatcherBinding] = {}

    def observe_pre_run(
        self,
        matcher: Matcher,
        bot: Bot,
        event: Event,
    ) -> RuntimeFrame:
        request = runtime_ingress_normalizer.build_native_dispatch_request(bot, event)
        frame = RuntimeFrame(request=request)
        binding = _MatcherBinding(
            frame=frame,
            effect_token=bind_effect_queue(frame.effect_queue),
            frame_token=_current_frame.set(frame),
        )
        self._bindings[id(matcher)] = binding
        runtime_diagnostic_recorder.record(
            "ingress",
            source="runtime.matcher_observer",
            message="dispatch_request_created",
            request_id=request.request_id,
            data={
                "subject_kind": request.subject_kind,
                "ingress_kind": request.ingress_kind,
                "plugin": matcher.plugin.module_name if matcher.plugin else None,
                "scene_kind": request.scene.scene_kind if request.scene else None,
            },
        )
        return frame

    def observe_post_run(
        self,
        matcher: Matcher,
        exception: Exception | None,
    ) -> MatcherObservation | None:
        binding = self._bindings.pop(id(matcher), None)
        if binding is None:
            return None
        frame = binding.frame

        try:
            plugin_module = matcher.plugin.module_name if matcher.plugin else None
            if exception is not None:
                disposition: InvocationDisposition = "failed"
                runtime_diagnostic_recorder.record(
                    "handler.error",
                    source="runtime.matcher_observer",
                    message=str(exception),
                    request_id=frame.request.request_id,
                    plugin_module=plugin_module,
                    data={"exception_type": type(exception).__name__},
                )
            else:
                disposition = self._disposition_from_frame(frame)

            report = ExecutionReport(
                request_id=frame.request.request_id,
                subject_kind=frame.request.subject_kind,
                ingress_kind=frame.request.ingress_kind,
                disposition=disposition,
                started_at=frame.request.created_at,
                finished_at=datetime.now(timezone.utc),
                diagnostics=tuple(frame.diagnostics),
                phase_notes=dict(frame.phase_notes),
                effects=frame.effect_queue.snapshot(),
                error_code=type(exception).__name__ if exception else None,
                error_message=str(exception) if exception else None,
            )
            return MatcherObservation(request=frame.request, report=report)
        finally:
            reset_effect_queue(binding.effect_token)
            _current_frame.reset(binding.frame_token)

    @contextmanager
    def frame_scope(self, frame: RuntimeFrame) -> "Iterator[RuntimeFrame]":
        """Bind ``frame`` as the current runtime frame within the block."""

        effect_token = bind_effect_queue(frame.effect_queue)
        try:
            with _frame_scope(frame) as active:
                yield active
        finally:
            reset_effect_queue(effect_token)

    @staticmethod
    def attach_diagnostic(
        frame: RuntimeFrame | None,
        diagnostic: RuntimeDiagnostic,
    ) -> None:
        if frame is None:
            return
        frame.diagnostics.append(diagnostic)

    @staticmethod
    def note_phase(frame: RuntimeFrame | None, phase: str, note: Any) -> None:
        if frame is None:
            return
        frame.phase_notes[phase] = note
        frame.current_phase = phase

    def _disposition_from_frame(self, frame: RuntimeFrame) -> InvocationDisposition:
        for diagnostic in frame.diagnostics:
            if diagnostic.kind == "permission.denied":
                return "denied"
            if diagnostic.kind == "degradation":
                return "degraded"
        return "completed"


runtime_matcher_observer = RuntimeMatcherObserver()
