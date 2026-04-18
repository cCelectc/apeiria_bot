"""AI runtime ingress observation shell."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from apeiria.app.runtime import (
    DeliveryTarget,
    DispatchRequest,
    ExecutionReport,
    InvocationDisposition,
    PrincipalRef,
    SceneKind,
    SceneRef,
    SessionRef,
    runtime_diagnostic_recorder,
    runtime_ingress_normalizer,
)

if TYPE_CHECKING:
    from apeiria.app.ai.conversation.models import ChatSessionIdentity
    from apeiria.app.ai.future_task.models import AIFutureTaskDefinition


@dataclass
class AIRuntimeObservation:
    """Runtime observation state held for the lifetime of one AI run."""

    request: DispatchRequest
    disposition: InvocationDisposition = "completed"
    error_code: str | None = None
    error_message: str | None = None


def _scene_kind_for_identity(scene_type: str) -> SceneKind:
    if scene_type == "group":
        return "group"
    if scene_type == "private":
        return "private"
    return "unknown"


def _build_principal_from_identity(
    identity: "ChatSessionIdentity",
    *,
    user_id: str,
    principal_kind: str,
) -> PrincipalRef:
    return runtime_ingress_normalizer.build_principal_ref(
        principal_kind=principal_kind,  # type: ignore[arg-type]
        principal_id=user_id,
        display_name=user_id,
        metadata={
            "platform": identity.platform,
            "bot_id": identity.bot_id,
            "session_id": identity.session_id,
        },
    )


def _build_scene_from_identity(identity: "ChatSessionIdentity") -> SceneRef:
    return SceneRef(
        scene_kind=_scene_kind_for_identity(identity.scene_type),
        scene_id=identity.scene_id,
        platform=identity.platform,
        bot_id=identity.bot_id,
        metadata={"source": "ai_runtime"},
    )


def _build_session_from_identity(identity: "ChatSessionIdentity") -> SessionRef:
    return SessionRef(
        session_id=identity.session_id,
        anchor_facts={
            "platform": identity.platform,
            "bot_id": identity.bot_id,
            "scene_type": identity.scene_type,
            "scene_id": identity.scene_id,
        },
    )


def _build_delivery_target(
    identity: "ChatSessionIdentity",
    *,
    user_id: str,
) -> DeliveryTarget:
    return DeliveryTarget(
        scope_kind=_scene_kind_for_identity(identity.scene_type),
        scope_id=identity.scene_id,
        platform=identity.platform,
        bot_id=identity.bot_id,
        user_id=identity.subject_id or user_id,
        route_facts={"source": "ai_runtime"},
    )


def build_message_observation(
    identity: "ChatSessionIdentity",
    *,
    user_id: str,
    is_tome: bool,
) -> AIRuntimeObservation:
    """Build an observation shell for an AI message pipeline run."""

    principal = _build_principal_from_identity(
        identity,
        user_id=user_id,
        principal_kind="adapter_user",
    )
    scene = _build_scene_from_identity(identity)
    session = _build_session_from_identity(identity)
    delivery_target = _build_delivery_target(identity, user_id=user_id)
    request = runtime_ingress_normalizer.build_dispatch_request(
        subject_kind="ai_reply",
        ingress_kind="ai_message",
        principal=principal,
        scene=scene,
        session=session,
        delivery_target=delivery_target,
        labels=("ai.tome",) if is_tome else (),
    )
    runtime_diagnostic_recorder.record(
        "ingress",
        source="ai.runtime_service",
        message="ai_message_dispatch_created",
        request_id=request.request_id,
        data={
            "scene_kind": scene.scene_kind,
            "session_id": session.session_id,
        },
    )
    return AIRuntimeObservation(request=request)


def build_future_task_observation(
    identity: "ChatSessionIdentity",
    *,
    task: "AIFutureTaskDefinition",
    user_id: str,
) -> AIRuntimeObservation:
    """Build an observation shell for a future-task AI pipeline run."""

    principal = runtime_ingress_normalizer.build_principal_ref(
        principal_kind="scheduled_task",
        principal_id=task.task_id,
        display_name=task.title,
        metadata={
            "platform": identity.platform,
            "bot_id": identity.bot_id,
            "target_user_id": user_id,
        },
    )
    scene = _build_scene_from_identity(identity)
    session = _build_session_from_identity(identity)
    delivery_target = _build_delivery_target(identity, user_id=user_id)
    request = runtime_ingress_normalizer.build_dispatch_request(
        subject_kind="future_task",
        ingress_kind="ai_future_task",
        principal=principal,
        scene=scene,
        session=session,
        delivery_target=delivery_target,
        labels=(f"task:{task.task_id}",),
    )
    runtime_diagnostic_recorder.record(
        "ingress",
        source="ai.runtime_service",
        message="ai_future_task_dispatch_created",
        request_id=request.request_id,
        data={
            "task_id": task.task_id,
            "status": task.status,
        },
    )
    return AIRuntimeObservation(request=request)


def finalize_observation(
    observation: AIRuntimeObservation | None,
    *,
    disposition: InvocationDisposition = "completed",
    exception: Exception | None = None,
    note: dict[str, object] | None = None,
) -> ExecutionReport | None:
    """Seal the observation into an `ExecutionReport`."""

    if observation is None:
        return None
    final_disposition = disposition
    error_code: str | None = None
    error_message: str | None = None
    if exception is not None:
        final_disposition = "failed"
        error_code = type(exception).__name__
        error_message = str(exception)
        runtime_diagnostic_recorder.record(
            "handler.error",
            source="ai.runtime_service",
            message=error_message,
            request_id=observation.request.request_id,
            data={"exception_type": error_code},
        )
    return ExecutionReport(
        request_id=observation.request.request_id,
        subject_kind=observation.request.subject_kind,
        ingress_kind=observation.request.ingress_kind,
        disposition=final_disposition,
        started_at=observation.request.created_at,
        finished_at=datetime.now(timezone.utc),
        phase_notes=dict(note or {}),
        error_code=error_code,
        error_message=error_message,
    )
