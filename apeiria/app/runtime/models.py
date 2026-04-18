"""Formal Runtime Kernel objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from datetime import datetime

PrincipalRefKind = Literal[
    "adapter_user",
    "webui_account",
    "bot_subject",
    "system_actor",
    "host_operator",
    "scheduled_task",
]

SceneKind = Literal[
    "private",
    "group",
    "channel",
    "web_session",
    "scheduled_task",
    "unknown",
]

IngressKind = Literal[
    "native_message",
    "web_chat_message",
    "ai_message",
    "ai_future_task",
    "scheduled_task",
    "internal",
]

SubjectKind = Literal[
    "message",
    "ai_reply",
    "scheduled_task",
    "future_task",
    "internal",
]

InvocationDisposition = Literal[
    "completed",
    "denied",
    "degraded",
    "failed",
    "skipped",
]


@dataclass(frozen=True)
class PrincipalRef:
    """Runtime-side principal reference.

    Distinct from governance `Principal`: this is the lightweight handle
    runtime carries through a dispatch, not the governance identity. The
    governance principal is resolvable via `principal_id` + `principal_kind`.
    """

    principal_kind: PrincipalRefKind
    principal_id: str
    display_name: str
    is_superuser: bool = False
    adapter_role_level: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SceneRef:
    """Runtime-side scene reference.

    `scene_id` semantics depends on `scene_kind`:

    - `private` → peer user id
    - `group`   → group id
    - `channel` → channel id
    - `web_session` → WebChat session id
    - `scheduled_task` → task id
    """

    scene_kind: SceneKind
    scene_id: str
    platform: str
    bot_id: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SessionRef:
    """Runtime-side session anchor.

    Always carries a canonical `session_id` (stable hash). `anchor_facts`
    records the inputs used to compute the hash for audit / attribution.
    """

    session_id: str
    anchor_facts: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DeliveryTarget:
    """Normalized outbound delivery target."""

    scope_kind: SceneKind
    scope_id: str
    platform: str
    bot_id: str
    user_id: str | None = None
    route_facts: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MessageContent:
    """Normalized message content."""

    text: str
    native_summary: str = ""
    segments: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class MessageEvent:
    """Normalized inbound message event."""

    principal: PrincipalRef
    scene: SceneRef
    session: SessionRef
    delivery_target: DeliveryTarget
    content: MessageContent
    native_envelope: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DispatchRequest:
    """Root request object entering the Runtime Kernel.

    Subject-first: `subject_kind` is what runtime is about to process; the
    message event is only populated for `subject_kind="message"`.
    """

    request_id: str
    subject_kind: SubjectKind
    ingress_kind: IngressKind
    created_at: datetime
    principal: PrincipalRef | None = None
    scene: SceneRef | None = None
    session: SessionRef | None = None
    delivery_target: DeliveryTarget | None = None
    message_event: MessageEvent | None = None
    labels: tuple[str, ...] = ()


@dataclass
class RuntimeFrame:
    """Mutable per-request frame visible only to runtime core."""

    request: DispatchRequest
    diagnostics: list[Any] = field(default_factory=list)
    phase_notes: dict[str, Any] = field(default_factory=dict)
    current_phase: str | None = None


@dataclass(frozen=True)
class ExecutionReport:
    """Summary of one dispatch after runtime observation."""

    request_id: str
    subject_kind: SubjectKind
    ingress_kind: IngressKind
    disposition: InvocationDisposition
    started_at: datetime
    finished_at: datetime
    diagnostics: tuple[Any, ...] = ()
    phase_notes: dict[str, Any] = field(default_factory=dict)
    error_code: str | None = None
    error_message: str | None = None
