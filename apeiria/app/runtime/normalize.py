"""Ingress normalization for the Runtime Kernel observation layer."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from apeiria.app.runtime.models import (
    DeliveryTarget,
    DispatchRequest,
    IngressKind,
    MessageContent,
    MessageEvent,
    PrincipalRef,
    PrincipalRefKind,
    SceneKind,
    SceneRef,
    SessionRef,
    SubjectKind,
)

if TYPE_CHECKING:
    from nonebot.adapters import Bot, Event

_ADAPTER_ROLE_SUPERUSER = 0


def _scene_kind_from_conversation(conversation_type: str) -> SceneKind:
    if conversation_type == "group":
        return "group"
    if conversation_type == "private":
        return "private"
    return "unknown"


def _session_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    return f"session_{digest}"


def _native_envelope(bot: Bot, event: Event) -> dict[str, Any]:
    return {
        "adapter": _adapter_name(bot),
        "event_type": type(event).__name__,
        "event_name": _safe_event_name(event),
        "session_id": _safe_session_id(event),
    }


def _adapter_name(bot: Bot) -> str:
    adapter = getattr(bot, "adapter", None)
    get_name = getattr(adapter, "get_name", None)
    if callable(get_name):
        try:
            return str(get_name())
        except Exception:  # noqa: BLE001
            return ""
    return ""


def _safe_event_name(event: Event) -> str:
    try:
        return event.get_event_name()
    except Exception:  # noqa: BLE001
        return ""


def _safe_session_id(event: Event) -> str:
    try:
        return event.get_session_id()
    except Exception:  # noqa: BLE001
        return ""


def _safe_plaintext(event: Event) -> str:
    try:
        return event.get_plaintext()
    except Exception:  # noqa: BLE001
        return ""


def _adapter_role_level(event: Event) -> int:
    sender = getattr(event, "sender", None)
    sender_role = getattr(sender, "role", None)
    role = sender_role if isinstance(sender_role, str) else getattr(event, "role", None)
    if role == "owner":
        return 6
    if role == "admin":
        return 5
    return 0


def _driver_superusers() -> set[str]:
    try:
        from nonebot import get_driver

        raw = getattr(get_driver().config, "superusers", set())
    except Exception:  # noqa: BLE001
        return set()
    return {str(item) for item in raw}


class RuntimeIngressNormalizer:
    """Translate ingress inputs into formal runtime objects."""

    def build_message_event_from_native(
        self,
        bot: Bot,
        event: Event,
    ) -> MessageEvent | None:
        """Build a `MessageEvent` from a NoneBot bot/event pair.

        Returns `None` when the event does not expose a user id (e.g.
        meta events). Callers decide whether to still create a
        `DispatchRequest` for such cases.
        """

        from apeiria.app.access.runtime import (
            group_id_from_event,
            resolve_conversation_type,
        )

        try:
            user_id = event.get_user_id()
        except Exception:  # noqa: BLE001
            return None

        user_id = str(user_id)
        group_id = group_id_from_event(event)
        conversation_type = resolve_conversation_type(event, user_id, group_id)
        scene_kind = _scene_kind_from_conversation(conversation_type)
        platform = str(bot.type)
        bot_id = str(bot.self_id)

        scene_id = group_id if group_id is not None else user_id
        scene = SceneRef(
            scene_kind=scene_kind,
            scene_id=scene_id,
            platform=platform,
            bot_id=bot_id,
            metadata={"conversation_type": conversation_type},
        )
        session = SessionRef(
            session_id=_session_hash(
                {
                    "platform": platform,
                    "bot_id": bot_id,
                    "scene_kind": scene_kind,
                    "scene_id": scene_id,
                },
            ),
            anchor_facts={
                "platform": platform,
                "bot_id": bot_id,
                "scene_kind": scene_kind,
                "scene_id": scene_id,
            },
        )
        delivery_target = DeliveryTarget(
            scope_kind=scene_kind,
            scope_id=scene_id,
            platform=platform,
            bot_id=bot_id,
            user_id=user_id if scene_kind == "private" else None,
            route_facts={"source": "reply"},
        )
        is_superuser = user_id in _driver_superusers()
        principal = PrincipalRef(
            principal_kind="adapter_user",
            principal_id=user_id,
            display_name=user_id,
            is_superuser=is_superuser,
            adapter_role_level=(
                _ADAPTER_ROLE_SUPERUSER if is_superuser else _adapter_role_level(event)
            ),
            metadata={"platform": platform, "bot_id": bot_id},
        )
        content = MessageContent(
            text=_safe_plaintext(event),
            native_summary=_safe_event_name(event),
        )
        return MessageEvent(
            principal=principal,
            scene=scene,
            session=session,
            delivery_target=delivery_target,
            content=content,
            native_envelope=_native_envelope(bot, event),
        )

    def build_native_dispatch_request(
        self,
        bot: Bot,
        event: Event,
    ) -> DispatchRequest:
        """Build a native-ingress `DispatchRequest` for matcher observation."""

        message_event = self.build_message_event_from_native(bot, event)
        ingress_kind = self._infer_native_ingress_kind(bot)
        return DispatchRequest(
            request_id=_new_request_id(),
            subject_kind="message",
            ingress_kind=ingress_kind,
            created_at=datetime.now(timezone.utc),
            principal=message_event.principal if message_event else None,
            scene=message_event.scene if message_event else None,
            session=message_event.session if message_event else None,
            delivery_target=message_event.delivery_target if message_event else None,
            message_event=message_event,
        )

    def build_dispatch_request(  # noqa: PLR0913
        self,
        *,
        subject_kind: SubjectKind,
        ingress_kind: IngressKind,
        principal: PrincipalRef | None = None,
        scene: SceneRef | None = None,
        session: SessionRef | None = None,
        delivery_target: DeliveryTarget | None = None,
        message_event: MessageEvent | None = None,
        labels: tuple[str, ...] = (),
    ) -> DispatchRequest:
        """Build a non-native `DispatchRequest` (AI / scheduled / internal)."""

        return DispatchRequest(
            request_id=_new_request_id(),
            subject_kind=subject_kind,
            ingress_kind=ingress_kind,
            created_at=datetime.now(timezone.utc),
            principal=principal,
            scene=scene,
            session=session,
            delivery_target=delivery_target,
            message_event=message_event,
            labels=labels,
        )

    def build_principal_ref(  # noqa: PLR0913
        self,
        *,
        principal_kind: PrincipalRefKind,
        principal_id: str,
        display_name: str | None = None,
        is_superuser: bool = False,
        adapter_role_level: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> PrincipalRef:
        return PrincipalRef(
            principal_kind=principal_kind,
            principal_id=principal_id,
            display_name=display_name or principal_id,
            is_superuser=is_superuser,
            adapter_role_level=adapter_role_level,
            metadata=dict(metadata or {}),
        )

    def _infer_native_ingress_kind(self, bot: Bot) -> IngressKind:
        adapter = _adapter_name(bot).lower()
        if "webchat" in adapter or "webui" in adapter or "web_chat" in adapter:
            return "web_chat_message"
        return "native_message"


def _new_request_id() -> str:
    return f"req_{uuid4().hex}"


runtime_ingress_normalizer = RuntimeIngressNormalizer()
